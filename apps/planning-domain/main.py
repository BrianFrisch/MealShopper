import os
import logging
from fastapi import FastAPI #, Depends, HTTPException, status

from src.models import MealPlanRequest#, MealPlanResponse
from src.services.gemini_planner import GeminiPlannerService
from src.services.mock_planner import MockMealPlannerService #generate_mock_plan # Existing fallback
from src.models import MealPlanResponse, MealPlanRequest

# from models import MealPlanRequest, MealPlanResponse
# from src.services.planner_service import MealPlannerService

app = FastAPI(title="MealShopper - Planning Domain Service")
logger = logging.getLogger("planning-domain")
logging.basicConfig(level=logging.INFO)

planner_service = GeminiPlannerService()
mock_planner_service = MockMealPlannerService()


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

    if not use_mock and planner_service.client:
        try:
            logger.info("Generating meal plan via %s...", planner_service.model_name)
            plan = await planner_service.generate_plan(
                cuisines=request.preferred_cuisines,
                avoid_ingredients=request.avoid_ingredients,
                top_deals=request.scored_deals,
                days_count=request.target_meal_count or 3
            )
            return plan
        except Exception as ex:
            logger.error("Gemini live generation failed (%s). Falling back to mock synthesis.", ex)

    logger.info("Using mock meal plan generator.")
    return await mock_planner_service.generate_mock_plan(request)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
