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
        days_count: int = 3,
        dietary_restrictions: List[str] | None = None,
        servings_count: int = 2
    ) -> MealPlanResponse:
        if not self.client:
            raise RuntimeError("GEMINI_API_KEY not configured. Live planner unavailable.")

        deals_context = json.dumps([
            {
                "dealId": d.deal_id,
                "name": d.item_name,
                "primaryIngredient": d.primary_ingredient,
                "category": d.category,
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
2. Dietary Requirements: {', '.join(dietary_restrictions or []) if dietary_restrictions else 'None'}
3. Strictly Avoid Ingredients: {', '.join(avoid_ingredients) if avoid_ingredients else 'None'}
4. Each meal must serve {servings_count} people.
5. Use the selected promotional deals as recipe ingredients. When the number of selected deals is no greater than the number of meals, use each selected deal as the core ingredient of at least one meal. Use each deal's 'primaryIngredient' as the ingredient name and do not substitute another ingredient.
   - Set 'is_promotional' to true
   - Populate 'store_name' and 'deal_id' exactly as provided in the deals list.
6. If an essential main recipe component (e.g. protein or fresh produce base) is missing from the circular deals, list its generic name in 'missing_primary_ingredients' so our shopper engine can search for it in secondary circulars.
7. Common pantry staples (oil, salt, pepper, flour, vinegar, standard dried spices) should have 'store_name' and 'deal_id' set to null, 'is_promotional' to false, and must NOT be added to 'missing_primary_ingredients'.
8. RECIPE NAMING: Do not use generic placeholders like "Protein" or "Meat" in your recipe titles. Name the actual dish (e.g., "Garlic Butter Ribeye" or "DiGiorno Pizza with Side Salad").
9. PREPARED FOODS: If an ingredient is a fully prepared or frozen food (like a frozen pizza, lasagna, or chicken nuggets), DO NOT treat it as a raw ingredient to be seared, marinated, or heavily prepped. Instruct the user to cook it according to package directions and pair it with a fresh side.

AVAILABLE PROMOTIONAL DEALS:
{deals_context}
"""

        logger.info("Sending prompt to Gemini model: %s", prompt)
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