import logging
import uuid
from typing import Any, List

from src.models import MealPlanRequest, MealPlanResponse, PlannedMeal, RecipeIngredient, MissingIngredient

logger = logging.getLogger(__name__)


class MockMealPlannerService:
    """Service for generating meal plans utilizing Gemini GenAI with offline fallback."""

    async def generate_mock_plan(self, request: MealPlanRequest) -> MealPlanResponse:
        """Constructs a deterministic offline mock response based on available deals."""
        deals = request.scored_deals
        target_count = request.target_meal_count
        meals: List[PlannedMeal] = []
        total_spend = 0.0

        # Template recipes to draw from
        recipe_templates: List[dict[str, Any]] = [
            {
                "name": "Pan-Seared Herb Protein with Roasted Vegetables",
                "description": "Flavorful seared protein paired with seasoned roasted vegetables.",
                "prep_time": 30,
                "instructions": [
                    "Preheat oven to 400°F (200°C).",
                    "Season protein and vegetables with olive oil, salt, pepper, and herbs.",
                    "Pan-sear protein over medium-high heat until golden brown.",
                    "Roast vegetables on baking sheet for 20-25 minutes until tender-crisp.",
                    "Rest protein for 5 minutes before slicing and serving.",
                ],
            },
            {
                "name": "Savory Skillet Medley with Fresh Herbs",
                "description": "Quick one-pan skillet dish featuring deal ingredients and aromatic spices.",
                "prep_time": 25,
                "instructions": [
                    "Heat olive oil in a large skillet over medium heat.",
                    "Sauté aromatics and key ingredients until softened.",
                    "Add protein and season thoroughly.",
                    "Cook until protein is done and flavors meld together.",
                    "Garnish with freshly chopped herbs and serve immediately.",
                ],
            },
            {
                "name": "Hearty Garden Stir-Fry",
                "description": "Crisp stir-fried vegetables and protein tossed in a savory glaze.",
                "prep_time": 20,
                "instructions": [
                    "Chop protein and vegetables into bite-sized pieces.",
                    "Heat oil in wok or skillet on high heat.",
                    "Stir-fry protein until fully cooked, then set aside.",
                    "Flash-fry vegetables until tender-crisp, then combine with protein.",
                    "Toss with glaze and serve over rice or grains.",
                ],
            },
            {
                "name": "Slow-Simmered Comfort Bowl",
                "description": "Warm, comforting stew combining tender protein, aromatics, and hearty sides.",
                "prep_time": 45,
                "instructions": [
                    "Brown protein in a heavy pot or Dutch oven.",
                    "Add broth, garlic, and seasoning; bring to a simmer.",
                    "Incorporate hearty vegetables and simmer on low heat for 30 minutes.",
                    "Adjust seasonings to taste.",
                    "Ladle into bowls and serve with crusty bread.",
                ],
            },
            {
                "name": "Sheet Pan Citrus-Glazed Feast",
                "description": "Effortless roasted meal balanced with bright citrus and herb notes.",
                "prep_time": 35,
                "instructions": [
                    "Line large baking sheet with parchment paper.",
                    "Arrange protein and cut vegetables in a single layer.",
                    "Drizzle with citrus glaze, olive oil, and herbs.",
                    "Bake at 425°F for 25-30 minutes until protein is cooked through.",
                    "Finish with fresh lemon juice and serve.",
                ],
            },
            {
                "name": "Crispy Golden Protein with Steamed Greens",
                "description": "Tender crisp protein served alongside vibrant steamed greens.",
                "prep_time": 30,
                "instructions": [
                    "Pat protein dry and season generously.",
                    "Cook in hot skillet with light oil until crust is golden and crisp.",
                    "Steam greens in a covered pot with light salt for 4-5 minutes.",
                    "Plate protein over greens and drizzle with pan juices.",
                ],
            },
            {
                "name": "Zesty Herb-Crusted Entrée",
                "description": "Oven-baked entrée crusted with herbs and spices for rich flavor.",
                "prep_time": 40,
                "instructions": [
                    "Coat protein in herb and spice crust mixture.",
                    "Arrange on baking rack and roast at 375°F for 30 minutes.",
                    "Prepare side vegetables with light olive oil and salt.",
                    "Serve hot with a side of lemon wedges.",
                ],
            },
        ]

        # Standard missing primary ingredients for realistic mock output
        missing_primary_ingredients=[
            MissingIngredient(
                ingredient_name="Garlic",
                quantity=3.0,
                unit="cloves",
                associated_recipe_titles=["Pan-Seared Herb Protein with Roasted Vegetables", "Savory Skillet Medley with Fresh Herbs"]
            ),
            MissingIngredient(
                ingredient_name="Olive Oil",
                quantity=4.0,
                unit="tbsp",
                associated_recipe_titles=["Pan-Seared Herb Protein with Roasted Vegetables", "Savory Skillet Medley with Fresh Herbs"]
            ),
            MissingIngredient(
                ingredient_name="Lemon",
                quantity=1.0,
                unit="each",
                associated_recipe_titles=["Pan-Seared Herb Protein with Roasted Vegetables"]
            )
        ]

        for i in range(target_count):
            template = recipe_templates[i % len(recipe_templates)]
            ingredients: List[RecipeIngredient] = []

            # Assign a deal to this meal if available
            if deals:
                deal = deals[i % len(deals)]
                ingredients.append(
                    RecipeIngredient(
                        name=deal.item_name,
                        quantity=f"{request.household_size * 0.5:.1f} {deal.unit}",
                        is_promotional=True,
                        deal_id=deal.deal_id,
                        store_name=deal.store_name,
                    )
                )
                total_spend += deal.price
            else:
                ingredients.append(
                    RecipeIngredient(
                        name="Chicken Breast",
                        quantity=f"{request.household_size * 0.5:.1f} lbs",
                        is_promotional=False,
                        deal_id=None,
                        store_name=None,
                    )
                )

            # Add complementary pantry/produce items to the recipe
            ingredients.append(
                RecipeIngredient(
                    name="Olive Oil",
                    quantity="2 tbsp",
                    is_promotional=False,
                    deal_id=None,
                    store_name=None,
                )
            )
            ingredients.append(
                RecipeIngredient(
                    name="Garlic",
                    quantity="3 cloves",
                    is_promotional=False,
                    deal_id=None,
                    store_name=None,
                )
            )

            meal = PlannedMeal(
                meal_id=f"meal_{i + 1:02d}",
                recipe_name=template["name"],
                description=template["description"],
                estimated_prep_time_minutes=template["prep_time"],
                servings=request.household_size,
                ingredients=ingredients,
                instructions=template["instructions"],
            )
            meals.append(meal)

        return MealPlanResponse(
            plan_id=f"plan_{uuid.uuid4().hex[:12]}",
            meals=meals,
            missing_primary_ingredients=missing_primary_ingredients,
            estimated_total_spend=round(total_spend, 2),
        )
