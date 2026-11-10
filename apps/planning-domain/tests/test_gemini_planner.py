from types import SimpleNamespace
from typing import Any

import pytest

from src.models import DealInput, MealPlanResponse
from src.services.gemini_planner import GeminiPlannerService


@pytest.mark.asyncio
@pytest.mark.parametrize("main_ingredient", [None, "chicken"])
async def test_generate_plan_prompt_includes_selected_deals_and_preferences(
    main_ingredient: str | None,
) -> None:
    class FakeModels:
        prompt: str | None = None

        async def generate_content(self, **kwargs: Any) -> SimpleNamespace:
            self.prompt = kwargs["contents"]
            return SimpleNamespace(
                parsed=MealPlanResponse(plan_id="plan-1", meals=[]),
                text=None,
            )

    models = FakeModels()
    service = GeminiPlannerService.__new__(GeminiPlannerService)
    service.client = SimpleNamespace(aio=SimpleNamespace(models=models))
    service.model_name = "test-model"

    await service.generate_plan(
        cuisines=["Southern", "Classic American", "Comfort Food"],
        avoid_ingredients=["onions", "corn", "mango"],
        dietary_restrictions=["Keto"],
        days_count=3,
        servings_count=4,
        main_ingredient=main_ingredient,
        include_ingredients=["mushrooms", "spinach"],
        top_deals=[
            DealInput(
                deal_id="groceryoutlet-387_1047303061_1",
                store_id="groceryoutlet-368",
                store_name="Grocery Outlet",
                item_name="Boneless Skinless Chicken Breast",
                primary_ingredient="Chicken Breast",
                category="Meat & Poultry",
                price=2.99,
                unit="lb",
            )
        ],
    )

    assert models.prompt is not None
    assert "Southern, Classic American, Comfort Food" in models.prompt
    assert "Keto" in models.prompt
    assert "onions, corn, mango" in models.prompt
    assert "Optional ingredients to include: mushrooms, spinach" in models.prompt
    assert "include it in exactly one recipe if it fits naturally" in models.prompt
    assert "otherwise omit it" in models.prompt
    assert "Strict avoidance and dietary requirements take precedence" in models.prompt
    if main_ingredient:
        assert "built around the main ingredient: chicken" in models.prompt
    else:
        assert '"dealId": "groceryoutlet-387_1047303061_1"' in models.prompt
        assert '"primaryIngredient": "Chicken Breast"' in models.prompt
        assert "Use each deal's 'primaryIngredient' as the ingredient name" in models.prompt
        assert "'deal_id'" in models.prompt
