import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Depends as DependsType

from dependencies import (
    get_mock_planner_service,
    get_planner_service,
    get_recipe_service,
    is_generation_service_busy,
)
from src.models import MealPlanRequest, MealPlanResponse
from src.services.gemini_planner import GeminiPlannerService
from src.services.mock_planner import MockMealPlannerService
from src.services.recipe_service import RecipeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/planner", tags=["Planner"])


@router.post("/generate", response_model=MealPlanResponse)
async def generate_plan(
    request: MealPlanRequest,
    planner: GeminiPlannerService = Depends(get_planner_service),
    mock_planner: MockMealPlannerService = Depends(get_mock_planner_service),
    recipes: RecipeService = Depends(get_recipe_service),
) -> MealPlanResponse:
    if isinstance(planner, DependsType) or planner is None:
        planner = get_planner_service()
    if isinstance(mock_planner, DependsType) or mock_planner is None:
        mock_planner = get_mock_planner_service()
    if isinstance(recipes, DependsType) or recipes is None:
        recipes = get_recipe_service()

    use_mock = os.getenv("PLANNER_USE_MOCK", "false").lower() == "true"

    if use_mock:
        logger.info("Using mock meal plan generator.")
        plan = await mock_planner.generate_mock_plan(request)
    elif not planner.client:
        logger.error("Cannot generate meal plan because the Gemini client is not configured.")
        raise HTTPException(
            status_code=503,
            detail="Meal generation is unavailable because the planning provider is not configured.",
        )
    else:
        try:
            logger.info("Generating meal plan via %s...", planner.model_name)
            plan = await planner.generate_plan(
                cuisines=request.preferred_cuisines,
                avoid_ingredients=request.avoid_ingredients,
                top_deals=request.scored_deals,
                days_count=request.target_meal_count or 3,
                dietary_restrictions=request.dietary_restrictions,
                servings_count=request.household_size,
                main_ingredient=request.main_ingredient,
                include_ingredients=request.include_ingredients,
            )
        except Exception as ex:
            logger.exception("Meal plan generation failed.")
            if is_generation_service_busy(ex):
                raise HTTPException(
                    status_code=503,
                    detail="The meal generation service is busy or temporarily unavailable. Please try again shortly.",
                ) from ex
            raise HTTPException(
                status_code=502,
                detail="Meal plan generation failed because the planning provider returned an error.",
            ) from ex

    await recipes.persist_meal_plan(request.user_id, plan)
    return plan
