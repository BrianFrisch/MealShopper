from fastapi import FastAPI
import json
from pathlib import Path

app = FastAPI(title="Planning Domain Stub")

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BASE_DIR.parents[1] / "libs" / "contracts" / "tests" / "fixtures"

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/v1/planner/generate")
def generate_meal_plan(payload: dict):
    # If the schema fixture exists and matches, use it
    fixture_path = FIXTURES_DIR / "valid-meal-plan-proposal.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure missing_primary_ingredients elements are objects, not plain strings
            if data.get("missing_primary_ingredients") and isinstance(data["missing_primary_ingredients"][0], str):
                pass  # Fall through to the correct object structure below
            else:
                return data

    # Schema-compliant payload matching MealPlanDraftResponse & MissingIngredientDto
    return {
        "meal_plan_id": "plan_01hxyz123456",
        "meals": [
            {
                "meal_type": "Dinner",
                "recipe_title": "Lemon Pepper Chicken",
                "description": "Lemon pepper chicken paired with asparagus and quinoa",
                "ingredients": [
                    {
                        "name": "Chicken Breast",
                        "quantity": 1.5,
                        "unit": "lbs",
                        "deal_id": "deal_chk_1",
                        "store_name": "Grocery Outlet",
                        "deal_price": 2.49
                    },
                    {
                        "name": "Asparagus",
                        "quantity": 1.0,
                        "unit": "bundle",
                        "deal_id": None,
                        "store_name": None,
                        "deal_price": None
                    }
                ],
                "instructions": [
                    "Season chicken with lemon pepper.",
                    "Grill until internal temp reaches 165°F.",
                    "Steam asparagus until tender-crisp."
                ]
            }
        ],
        "missing_primary_ingredients": [
            {
                "ingredient_name": "Asparagus",
                "quantity": 1.0,
                "unit": "bundle",
                "associated_recipe_titles": ["Lemon Pepper Chicken"]
            }
        ]
    }