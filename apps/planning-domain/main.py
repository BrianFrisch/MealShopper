import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import MealPlanRequest, MealPlanResponse
from planner_service import MealPlannerService

logger = logging.getLogger("planning-domain")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="MealShopper - Planning Domain Service")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

planner_service = MealPlannerService()


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "planning-domain"}


@app.post("/v1/planner/generate", response_model=MealPlanResponse)
async def generate_meal_plan(request: MealPlanRequest) -> MealPlanResponse:
    try:
        return await planner_service.generate_plan(request)
    except Exception as e:
        logger.exception("Error generating meal plan: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": "generation_failed", "detail": str(e)},
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
