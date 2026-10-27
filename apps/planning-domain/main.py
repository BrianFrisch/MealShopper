import os
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)

from typing import Optional
from uuid import UUID
from fastapi import FastAPI, Header, HTTPException, status

from src.config import PLANNER_DATABASE_URL
from src.models import (
    AddShoppingListItemRequest,
    AssociateMealPlanRecipeRequest,
    CreateMealPlanRequest,
    MealPlanRecordResponse,
    MealPlanIngredientResponse,
    MealPlanRequest,
    MealPlanResponse,
    RemoveShoppingListItemResponse,
    UpdateMealPlanNameRequest,
    UpdateIngredientPurchaseRequest,
)
from src.services.gemini_planner import GeminiPlannerService
from src.services.mock_planner import MockMealPlannerService
from src.services.recipe_service import RecipeService

# from models import MealPlanRequest, MealPlanResponse
# from src.services.planner_service import MealPlannerService

planner_service = GeminiPlannerService()
mock_planner_service = MockMealPlannerService()
recipe_service = RecipeService(PLANNER_DATABASE_URL)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    await recipe_service.connect()
    logger.info("Planning domain started")
    try:
        yield
    finally:
        await recipe_service.close()
        logger.info("Planning domain stopped")


app = FastAPI(title="MealShopper - Planning Domain Service", lifespan=lifespan)


def _is_generation_service_busy(error: Exception) -> bool:
    error_code = getattr(error, "code", None)
    error_status = str(getattr(error, "status", "") or "").upper()
    error_message = str(error).lower()

    return (
        error_code in {429, 503}
        or error_status in {"RESOURCE_EXHAUSTED", "UNAVAILABLE", "OVERLOADED"}
        or any(
            phrase in error_message
            for phrase in (
                "busy",
                "overloaded",
                "temporarily unavailable",
                "resource exhausted",
            )
        )
    )


# # Enable CORS for local development
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# planner_service = MealPlannerService()


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "planning-domain"}

@app.post("/v1/planner/generate", response_model=MealPlanResponse)
async def generate_plan(request: MealPlanRequest) -> MealPlanResponse:
    use_mock = os.getenv("PLANNER_USE_MOCK", "false").lower() == "true"

    if use_mock:
        logger.info("Using mock meal plan generator.")
        plan = await mock_planner_service.generate_mock_plan(request)
    elif not planner_service.client:
        logger.error("Cannot generate meal plan because the Gemini client is not configured.")
        raise HTTPException(
            status_code=503,
            detail="Meal generation is unavailable because the planning provider is not configured.",
        )
    else:
        try:
            logger.info("Generating meal plan via %s...", planner_service.model_name)
            plan = await planner_service.generate_plan(
                cuisines=request.preferred_cuisines,
                avoid_ingredients=request.avoid_ingredients,
                top_deals=request.scored_deals,
                days_count=request.target_meal_count or 3,
                dietary_restrictions=request.dietary_restrictions,
                servings_count=request.household_size,
                main_ingredient=request.main_ingredient
            )
        except Exception as ex:
            logger.exception("Meal plan generation failed.")
            if _is_generation_service_busy(ex):
                raise HTTPException(
                    status_code=503,
                    detail="The meal generation service is busy or temporarily unavailable. Please try again shortly.",
                ) from ex
            raise HTTPException(
                status_code=502,
                detail="Meal plan generation failed because the planning provider returned an error.",
            ) from ex

    await recipe_service.persist_meal_plan(request.user_id, plan)
    return plan


def _resolve_request_user_id(
    x_user_id: Optional[str],
    body_user_id: Optional[UUID] = None,
) -> UUID:
    if x_user_id:
        try:
            return UUID(x_user_id.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-User-Id header.",
            ) from exc
    if body_user_id is not None:
        return body_user_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authenticated user ID is required.",
    )


@app.post(
    "/v1/planner/meal-plans",
    response_model=MealPlanRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_meal_plan(
    request: CreateMealPlanRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> MealPlanRecordResponse:
    user_id = _resolve_request_user_id(x_user_id, request.user_id)
    meal_plan_name = request.meal_plan_name.strip()
    if not meal_plan_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="meal_plan_name cannot be empty.",
        )

    meal_plan_id = await recipe_service.create_meal_plan(
        user_id=user_id,
        meal_plan_name=meal_plan_name,
        meal_plan_id=request.meal_plan_id,
    )
    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is not None:
        return MealPlanRecordResponse(**stored)

    return MealPlanRecordResponse(
        meal_plan_id=str(meal_plan_id),
        meal_plan_name=meal_plan_name,
        user_id=str(user_id),
    )


@app.post("/v1/planner/meal-plans/{meal_plan_id}/recipes")
async def associate_recipe_to_meal_plan(
    meal_plan_id: UUID,
    request: AssociateMealPlanRecipeRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> dict[str, str]:
    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this meal plan.",
        )

    await recipe_service.associate_meal_plan_with_recipe(
        meal_plan_id=meal_plan_id,
        recipe_id=request.recipe_id,
    )
    return {
        "status": "associated",
        "meal_plan_id": str(meal_plan_id),
        "recipe_id": str(request.recipe_id),
    }


@app.delete("/v1/planner/meal-plans/{meal_plan_id}/recipes/{recipe_id}")
async def remove_recipe_from_meal_plan(
    meal_plan_id: UUID,
    recipe_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> dict[str, str]:
    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this meal plan.",
        )

    await recipe_service.remove_recipe_from_meal_plan(
        meal_plan_id=meal_plan_id,
        recipe_id=recipe_id,
    )
    return {
        "status": "removed",
        "meal_plan_id": str(meal_plan_id),
        "recipe_id": str(recipe_id),
    }


@app.put(
    "/v1/planner/meal-plans/{meal_plan_id}",
    response_model=MealPlanRecordResponse,
)
@app.patch(
    "/v1/planner/meal-plans/{meal_plan_id}",
    response_model=MealPlanRecordResponse,
)
async def update_meal_plan_name(
    meal_plan_id: UUID,
    request: UpdateMealPlanNameRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> MealPlanRecordResponse:
    meal_plan_name = request.meal_plan_name.strip()
    if not meal_plan_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="meal_plan_name cannot be empty.",
        )

    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this meal plan.",
        )

    await recipe_service.update_meal_plan(
        meal_plan_id=meal_plan_id,
        meal_plan_name=meal_plan_name,
        is_archived=(
            request.is_archived
            if request.is_archived is not None
            else stored.get("is_archived", False)
        ),
    )
    updated = await recipe_service.get_meal_plan(meal_plan_id)
    if updated is not None:
        return MealPlanRecordResponse(**updated)

    return MealPlanRecordResponse(
        meal_plan_id=str(meal_plan_id),
        meal_plan_name=meal_plan_name,
        user_id=stored["user_id"],
        is_archived=stored.get("is_archived", False),
        created_at=stored.get("created_at"),
    )


@app.get(
    "/v1/planner/meal-plans",
    response_model=list[MealPlanRecordResponse],
)
async def list_meal_plans_for_user(
    user_id: Optional[UUID] = None,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> list[MealPlanRecordResponse]:
    resolved_user_id = _resolve_request_user_id(x_user_id, user_id)
    plans = await recipe_service.get_meal_plans_for_user(resolved_user_id)
    results: list[MealPlanRecordResponse] = []
    for plan in plans:
        plan_data = dict(plan)
        if "recipe_count" not in plan_data and hasattr(recipe_service, "get_recipes_for_meal_plan"):
            recipes = await recipe_service.get_recipes_for_meal_plan(UUID(str(plan_data["meal_plan_id"])))
            plan_data["recipe_count"] = len(recipes)
        results.append(MealPlanRecordResponse(**plan_data))
    return results


@app.get(
    "/v1/planner/meal-plans/{meal_plan_id}",
    response_model=MealPlanRecordResponse,
)
async def get_meal_plan_by_id(
    meal_plan_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> MealPlanRecordResponse:
    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this meal plan.",
        )
    plan_data = dict(stored)
    if "recipe_count" not in plan_data and hasattr(recipe_service, "get_recipes_for_meal_plan"):
        recipes = await recipe_service.get_recipes_for_meal_plan(meal_plan_id)
        plan_data["recipe_count"] = len(recipes)
    return MealPlanRecordResponse(**plan_data)


@app.get("/v1/planner/recipes/{recipe_id}")
async def get_recipe_by_id(
    recipe_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> dict[str, object]:
    user_id = _resolve_request_user_id(x_user_id)
    recipe = await recipe_service.get_recipe_for_user(recipe_id, user_id)
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe {recipe_id} not found.",
        )
    return dict(recipe)


@app.get("/v1/planner/meal-plans/{meal_plan_id}/recipes")
async def list_recipes_for_meal_plan(
    meal_plan_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> list[dict[str, object]]:
    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this meal plan.",
        )
    recipes = await recipe_service.get_recipes_for_meal_plan(meal_plan_id)
    return [dict(recipe) for recipe in recipes]


@app.get(
    "/v1/planner/meal-plans/{meal_plan_id}/shopping-list",
    response_model=list[MealPlanIngredientResponse],
)
async def get_meal_plan_shopping_list(
    meal_plan_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> list[MealPlanIngredientResponse]:
    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this meal plan.",
        )
    ingredients = await recipe_service.get_meal_plan_ingredients(meal_plan_id)
    return [MealPlanIngredientResponse(**ingredient) for ingredient in ingredients]


@app.patch(
    "/v1/planner/meal-plans/{meal_plan_id}/shopping-list/{ingredient_id}",
    response_model=MealPlanIngredientResponse,
)
async def update_meal_plan_ingredient_purchase(
    meal_plan_id: UUID,
    ingredient_id: UUID,
    request: UpdateIngredientPurchaseRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> MealPlanIngredientResponse:
    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this meal plan.",
        )

    updated = await recipe_service.update_meal_plan_ingredient_purchase(
        meal_plan_id,
        ingredient_id,
        request.is_purchased,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} was not found in meal plan {meal_plan_id}.",
        )

    ingredients = await recipe_service.get_meal_plan_ingredients(meal_plan_id)
    ingredient = next(
        (item for item in ingredients if item["meal_plan_ingredient_id"] == str(ingredient_id)),
        None,
    )
    if ingredient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} was not found in meal plan {meal_plan_id}.",
        )
    return MealPlanIngredientResponse(**ingredient)


@app.post(
    "/v1/planner/meal-plans/{meal_plan_id}/shopping-list/items",
    response_model=MealPlanIngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_meal_plan_shopping_list_item(
    meal_plan_id: UUID,
    request: AddShoppingListItemRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> MealPlanIngredientResponse:
    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this meal plan.",
        )

    ingredient_name = request.ingredient_name.strip()
    ingredient_quantity = request.ingredient_quantity.strip()
    if not ingredient_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingredient name is required.",
        )
    if not ingredient_quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingredient quantity is required.",
        )

    added = await recipe_service.add_shopping_list_item(
        meal_plan_id=meal_plan_id,
        ingredient_name=ingredient_name,
        ingredient_quantity=ingredient_quantity,
    )
    if added is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to add shopping list item.",
        )
    return MealPlanIngredientResponse(**added)


@app.delete(
    "/v1/planner/meal-plans/{meal_plan_id}/shopping-list/items/{ingredient_id}",
    response_model=RemoveShoppingListItemResponse,
)
async def remove_meal_plan_shopping_list_item(
    meal_plan_id: UUID,
    ingredient_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> RemoveShoppingListItemResponse:
    stored = await recipe_service.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this meal plan.",
        )

    removal_status = await recipe_service.remove_shopping_list_item(
        meal_plan_id=meal_plan_id,
        ingredient_id=ingredient_id,
    )
    if removal_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} was not found in meal plan {meal_plan_id}.",
        )

    return RemoveShoppingListItemResponse(
        status=removal_status,
        meal_plan_ingredient_id=str(ingredient_id),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
