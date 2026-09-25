import os
import json
import logging

from typing import List
from google import genai
from google.genai import types
from src.models import DealInput, MealPlanResponse

logger = logging.getLogger("planning_domain.gemini")

class GeminiPlannerService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3.8-flash")

    async def generate_plan(
        self,
        cuisines: List[str],
        avoid_ingredients: List[str],
        top_deals: List[DealInput],
        days_count: int = 3
    ) -> MealPlanResponse:
        if not self.client:
            raise RuntimeError("GEMINI_API_KEY not configured. Live planner unavailable.")

        deals_context = json.dumps([
            {
                "dealId": d.deal_id,
                "name": d.item_name,
                "storeName": d.store_name,
                "dealPrice": d.price,
                "unit": d.unit
            }
            for d in top_deals
        ], indent=2)

        prompt = f"""
You are an expert budget-conscious chef and meal planner.
Synthesize a {days_count}-meal dinner plan using the promotional grocery circular deals provided below.

CONSTRAINTS:
1. Target Cuisines: {', '.join(cuisines) if cuisines else 'Any balanced cuisines'}
2. Strictly Avoid Ingredients: {', '.join(avoid_ingredients) if avoid_ingredients else 'None'}
3. Maximize usage of the supplied promotional circular deals. When a recipe uses a promotional deal:
   - Set 'isPromotional' to true
   - Populate 'storeName' and 'dealId' exactly as provided in the deals list.
4. If an essential main recipe component (e.g. protein or fresh produce base) is missing from the circular deals, list its generic name in 'missingPrimaryIngredients' so our shopper engine can search for it in secondary circulars.
5. Common pantry staples (oil, salt, pepper, flour, vinegar, standard dried spices) should have 'storeName' and 'dealId' set to null, 'isPromotional' to false, and must NOT be added to 'missingPrimaryIngredients'.

AVAILABLE PROMOTIONAL DEALS:
{deals_context}
"""

        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=MealPlanResponse,
                temperature=0.2
            )
        )

        if response.parsed:
            if isinstance(response.parsed, MealPlanResponse):
                return response.parsed
            return MealPlanResponse.model_validate(response.parsed)

        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        return MealPlanResponse.model_validate_json(response.text)