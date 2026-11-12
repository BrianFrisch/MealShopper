import logging
from typing import Optional
from uuid import UUID
from fastapi import HTTPException, status

from src.config import PLANNER_DATABASE_URL
from src.services.gemini_planner import GeminiPlannerService
from src.services.meal_plan_service import MealPlanService
from src.services.mock_planner import MockMealPlannerService
from src.services.recipe_service import RecipeService
from src.services.shopping_list_service import ShoppingListService

logger = logging.getLogger(__name__)

planner_service = GeminiPlannerService()
mock_planner_service = MockMealPlannerService()
recipe_service = RecipeService(PLANNER_DATABASE_URL)
meal_plan_service = MealPlanService(PLANNER_DATABASE_URL, recipe_service=recipe_service)
shopping_list_service = ShoppingListService(PLANNER_DATABASE_URL)


def get_planner_service() -> GeminiPlannerService:
    import sys
    main_mod = sys.modules.get("main")
    if main_mod is not None and hasattr(main_mod, "planner_service"):
        return getattr(main_mod, "planner_service")
    return planner_service


def get_mock_planner_service() -> MockMealPlannerService:
    import sys
    main_mod = sys.modules.get("main")
    if main_mod is not None and hasattr(main_mod, "mock_planner_service"):
        return getattr(main_mod, "mock_planner_service")
    return mock_planner_service


def get_recipe_service() -> RecipeService:
    import sys
    main_mod = sys.modules.get("main")
    if main_mod is not None and hasattr(main_mod, "recipe_service"):
        return getattr(main_mod, "recipe_service")
    return recipe_service


def get_meal_plan_service() -> MealPlanService:
    import sys
    main_mod = sys.modules.get("main")
    if main_mod is not None:
        if hasattr(main_mod, "meal_plan_service") and getattr(main_mod, "meal_plan_service") is not meal_plan_service:
            return getattr(main_mod, "meal_plan_service")
        if hasattr(main_mod, "recipe_service") and getattr(main_mod, "recipe_service") is not recipe_service:
            return getattr(main_mod, "recipe_service")
        if hasattr(main_mod, "meal_plan_service"):
            return getattr(main_mod, "meal_plan_service")
    return meal_plan_service


def get_shopping_list_service() -> ShoppingListService:
    import sys
    main_mod = sys.modules.get("main")
    if main_mod is not None:
        if hasattr(main_mod, "shopping_list_service") and getattr(main_mod, "shopping_list_service") is not shopping_list_service:
            return getattr(main_mod, "shopping_list_service")
        if hasattr(main_mod, "recipe_service") and getattr(main_mod, "recipe_service") is not recipe_service:
            return getattr(main_mod, "recipe_service")
        if hasattr(main_mod, "shopping_list_service"):
            return getattr(main_mod, "shopping_list_service")
    return shopping_list_service


def resolve_request_user_id(
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


def is_generation_service_busy(error: Exception) -> bool:
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
