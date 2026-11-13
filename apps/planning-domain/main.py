import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

# Ensure planning-domain root directory is in sys.path
_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import dependencies
from dependencies import (
    get_meal_plan_service,
    get_mock_planner_service,
    get_planner_service,
    get_recipe_service,
    get_shopping_list_service,
    is_generation_service_busy,
    meal_plan_service,
    mock_planner_service,
    planner_service,
    recipe_service,
    resolve_request_user_id,
    shopping_list_service,
)
from src.api.routers.meal_plans import (
    associate_recipe_to_meal_plan,
    create_meal_plan,
    get_meal_plan_by_id,
    list_meal_plans_for_user,
    list_recipes_for_meal_plan,
    remove_recipe_from_meal_plan,
    router as meal_plans_router,
    update_meal_plan_name,
)
from src.api.routers.planner import generate_plan, router as planner_router
from src.api.routers.recipes import (
    delete_recipe_tag,
    get_recipe_by_id,
    get_user_recipe_tags,
    list_user_recipe_tags,
    list_user_recipes,
    remove_recipe_tag,
    remove_user_recipe,
    router as recipes_router,
    update_recipe_rating,
)
from src.api.routers.shopping_list import (
    add_meal_plan_shopping_list_item,
    get_meal_plan_shopping_list,
    remove_meal_plan_shopping_list_item,
    router as shopping_list_router,
    update_meal_plan_ingredient_purchase,
)
from src.models import (
    AddShoppingListItemRequest,
    AssociateMealPlanRecipeRequest,
    CreateMealPlanRequest,
    MealPlanIngredientResponse,
    MealPlanRecordResponse,
    MealPlanRequest,
    MealPlanResponse,
    RemoveShoppingListItemResponse,
    UpdateIngredientPurchaseRequest,
    UpdateMealPlanNameRequest,
    UpdateRecipeRatingRequest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    recipe_svc = get_recipe_service()
    meal_plan_svc = get_meal_plan_service()
    shopping_list_svc = get_shopping_list_service()
    await recipe_svc.connect()
    if recipe_svc.pool is not None:
        if meal_plan_svc.pool is None:
            meal_plan_svc.set_pool(recipe_svc.pool)
        if shopping_list_svc.pool is None:
            shopping_list_svc.set_pool(recipe_svc.pool)
    logger.info("Planning domain started")
    try:
        yield
    finally:
        await recipe_svc.close()
        logger.info("Planning domain stopped")


app = FastAPI(title="MealShopper - Planning Domain Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> Dict[str, str]:
    return {"status": "ok", "service": "planning-domain"}


# Mount domain routers
app.include_router(planner_router)
app.include_router(meal_plans_router)
app.include_router(recipes_router)
app.include_router(shopping_list_router)

# Compatibility aliases
_resolve_request_user_id = resolve_request_user_id
_is_generation_service_busy = is_generation_service_busy

# Compatibility exports
__all__ = [
    "app",
    "lifespan",
    "healthz",
    "generate_plan",
    "create_meal_plan",
    "associate_recipe_to_meal_plan",
    "remove_recipe_from_meal_plan",
    "update_meal_plan_name",
    "list_meal_plans_for_user",
    "get_meal_plan_by_id",
    "list_user_recipes",
    "get_recipe_by_id",
    "remove_user_recipe",
    "update_recipe_rating",
    "list_recipes_for_meal_plan",
    "get_meal_plan_shopping_list",
    "update_meal_plan_ingredient_purchase",
    "add_meal_plan_shopping_list_item",
    "remove_meal_plan_shopping_list_item",
    "recipe_service",
    "planner_service",
    "mock_planner_service",
    "meal_plan_service",
    "shopping_list_service",
    "get_recipe_service",
    "get_planner_service",
    "get_mock_planner_service",
    "get_meal_plan_service",
    "get_shopping_list_service",
    "resolve_request_user_id",
    "is_generation_service_busy",
    "_resolve_request_user_id",
    "_is_generation_service_busy",
    "AddShoppingListItemRequest",
    "AssociateMealPlanRecipeRequest",
    "CreateMealPlanRequest",
    "MealPlanRecordResponse",
    "MealPlanIngredientResponse",
    "MealPlanRequest",
    "MealPlanResponse",
    "RemoveShoppingListItemResponse",
    "UpdateMealPlanNameRequest",
    "UpdateIngredientPurchaseRequest",
    "UpdateRecipeRatingRequest",
]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
