from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.params import Depends as DependsType

from dependencies import (
    get_meal_plan_service,
    get_recipe_service,
    resolve_request_user_id,
)
from src.models import (
    AssociateMealPlanRecipeRequest,
    CreateMealPlanRequest,
    MealPlanRecordResponse,
    UpdateMealPlanNameRequest,
)
from src.services.meal_plan_service import MealPlanService
from src.services.recipe_service import RecipeService

router = APIRouter(prefix="/v1/planner/meal-plans", tags=["Meal Plans"])


@router.post(
    "",
    response_model=MealPlanRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/",
    response_model=MealPlanRecordResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_meal_plan(
    request: CreateMealPlanRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> MealPlanRecordResponse:
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    user_id = resolve_request_user_id(x_user_id, request.user_id)
    meal_plan_name = request.meal_plan_name.strip()
    if not meal_plan_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="meal_plan_name cannot be empty.",
        )

    meal_plan_id = await meal_plans.create_meal_plan(
        user_id=user_id,
        meal_plan_name=meal_plan_name,
        meal_plan_id=request.meal_plan_id,
    )
    stored = await meal_plans.get_meal_plan(meal_plan_id)
    if stored is not None:
        return MealPlanRecordResponse.model_validate(stored)

    return MealPlanRecordResponse(
        meal_plan_id=str(meal_plan_id),
        meal_plan_name=meal_plan_name,
        user_id=str(user_id),
    )


@router.post("/{meal_plan_id}/recipes")
async def associate_recipe_to_meal_plan(
    meal_plan_id: UUID,
    request: AssociateMealPlanRecipeRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> dict[str, str]:
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    stored = await meal_plans.get_meal_plan(meal_plan_id)
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

    await meal_plans.associate_meal_plan_with_recipe(
        meal_plan_id=meal_plan_id,
        recipe_id=request.recipe_id,
    )
    return {
        "status": "associated",
        "meal_plan_id": str(meal_plan_id),
        "recipe_id": str(request.recipe_id),
    }


@router.delete("/{meal_plan_id}/recipes/{recipe_id}")
async def remove_recipe_from_meal_plan(
    meal_plan_id: UUID,
    recipe_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> dict[str, str]:
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    stored = await meal_plans.get_meal_plan(meal_plan_id)
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

    await meal_plans.remove_recipe_from_meal_plan(
        meal_plan_id=meal_plan_id,
        recipe_id=recipe_id,
    )
    return {
        "status": "removed",
        "meal_plan_id": str(meal_plan_id),
        "recipe_id": str(recipe_id),
    }


@router.put(
    "/{meal_plan_id}",
    response_model=MealPlanRecordResponse,
)
@router.patch(
    "/{meal_plan_id}",
    response_model=MealPlanRecordResponse,
)
async def update_meal_plan_name(
    meal_plan_id: UUID,
    request: UpdateMealPlanNameRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> MealPlanRecordResponse:
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    meal_plan_name = request.meal_plan_name.strip()
    if not meal_plan_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="meal_plan_name cannot be empty.",
        )

    stored = await meal_plans.get_meal_plan(meal_plan_id)
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

    await meal_plans.update_meal_plan(
        meal_plan_id=meal_plan_id,
        meal_plan_name=meal_plan_name,
        is_archived=(
            request.is_archived
            if request.is_archived is not None
            else stored.get("is_archived", False)
        ),
    )
    updated = await meal_plans.get_meal_plan(meal_plan_id)
    if updated is not None:
        return MealPlanRecordResponse.model_validate(updated)

    return MealPlanRecordResponse(
        meal_plan_id=str(meal_plan_id),
        meal_plan_name=meal_plan_name,
        user_id=stored["user_id"],
        is_archived=stored.get("is_archived", False),
        created_at=stored.get("created_at"),
    )


@router.get(
    "",
    response_model=list[MealPlanRecordResponse],
)
@router.get(
    "/",
    response_model=list[MealPlanRecordResponse],
    include_in_schema=False,
)
async def list_meal_plans_for_user(
    user_id: Optional[UUID] = None,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> list[MealPlanRecordResponse]:
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    resolved_user_id = resolve_request_user_id(x_user_id, user_id)
    plans = await meal_plans.get_meal_plans_for_user(resolved_user_id)
    results: list[MealPlanRecordResponse] = []
    for plan in plans:
        plan_data = dict(plan)
        if "recipe_count" not in plan_data and hasattr(meal_plans, "get_recipes_for_meal_plan"):
            plan_recipes = await meal_plans.get_recipes_for_meal_plan(UUID(str(plan_data["meal_plan_id"])))
            plan_data["recipe_count"] = len(plan_recipes)
        results.append(MealPlanRecordResponse.model_validate(plan_data))
    return results


@router.get(
    "/{meal_plan_id}",
    response_model=MealPlanRecordResponse,
)
async def get_meal_plan_by_id(
    meal_plan_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> MealPlanRecordResponse:
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    stored = await meal_plans.get_meal_plan(meal_plan_id)
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
    if "recipe_count" not in plan_data and hasattr(meal_plans, "get_recipes_for_meal_plan"):
        plan_recipes = await meal_plans.get_recipes_for_meal_plan(meal_plan_id)
        plan_data["recipe_count"] = len(plan_recipes)
    return MealPlanRecordResponse.model_validate(plan_data)


@router.get("/{meal_plan_id}/recipes")
async def list_recipes_for_meal_plan(
    meal_plan_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
    recipes: RecipeService = Depends(get_recipe_service),
) -> list[dict[str, object]]:
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()
    if isinstance(recipes, DependsType):
        recipes = get_recipe_service()

    stored = await meal_plans.get_meal_plan(meal_plan_id)
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
    recipes_list = await recipes.get_recipes_for_meal_plan(meal_plan_id)
    return [dict(recipe) for recipe in recipes_list]

    stored = await recipes.get_meal_plan(meal_plan_id)
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
    recipes_list = await recipes.get_recipes_for_meal_plan(meal_plan_id)
    return [dict(recipe) for recipe in recipes_list]
