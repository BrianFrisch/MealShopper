from typing import List, Optional
from pydantic import BaseModel, Field


class DealInput(BaseModel):
    deal_id: str
    store_id: str
    store_name: str
    item_name: str
    category: str
    price: float
    unit: str
    primary_ingredient: str


class RecipeIngredient(BaseModel):
    name: str
    quantity: str
    is_promotional: bool
    deal_id: Optional[str] = None
    store_name: Optional[str] = None


class PlannedMeal(BaseModel):
    meal_id: str
    recipe_name: str
    description: str
    estimated_prep_time_minutes: int
    servings: int
    ingredients: List[RecipeIngredient]
    instructions: List[str]


class MealPlanRequest(BaseModel):
    scored_deals: List[DealInput]
    household_size: int = Field(default=2, ge=1, le=10)
    target_meal_count: int = Field(default=3, ge=1, le=7)
    preferred_cuisines: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)
    avoid_ingredients: List[str] = Field(default_factory=list)


class MealPlanResponse(BaseModel):
    plan_id: str
    meals: List[PlannedMeal]
    missing_primary_ingredients: List[str]
    estimated_total_spend: float



