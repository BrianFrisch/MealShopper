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

from fastapi import FastAPI, HTTPException

from src.config import PLANNER_DATABASE_URL
from src.models import MealPlanRequest, MealPlanResponse
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
                servings_count=request.household_size
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

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
