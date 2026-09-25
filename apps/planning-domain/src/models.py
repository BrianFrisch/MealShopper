import re
from typing import List, Optional, Union
from pydantic import BaseModel, Field, AliasChoices, field_validator


class DealInput(BaseModel):
    deal_id: str
    store_id: str
    store_name: str
    item_name: str
    category: str = Field(
        default="General",
        validation_alias=AliasChoices("category", "normalized_category"),
    )
    price: float = Field(
        ...,
        validation_alias=AliasChoices("price", "deal_price"),
    )
    unit: str = "item"
    primary_ingredient: str = Field(
        default="",
        validation_alias=AliasChoices("primary_ingredient", "item_name"),
    )
    original_price: Optional[float] = None
    currency: Optional[str] = "USD"
    value_score: Optional[float] = None


class RecipeIngredient(BaseModel):
    name: str
    quantity: str
    is_promotional: bool = False
    deal_id: Optional[str] = None
    store_name: Optional[str] = None


class PlannedMeal(BaseModel):
    meal_id: str
    recipe_name: str
    description: str
    #cuisine: str
    estimated_prep_time_minutes: int
    servings: int
    ingredients: List[RecipeIngredient]
    instructions: List[str]


class MissingIngredient(BaseModel):
    ingredient_name: str = Field(
        ...,
        validation_alias=AliasChoices("ingredient_name", "name")
    )
    quantity: float = 1.0
    unit: str = "item"
    associated_recipe_titles: List[str] = Field(default_factory=list)

    @field_validator("quantity", mode="before")
    @classmethod
    def parse_quantity(cls, v: Union[str, float, int]) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        #if isinstance(v, str): #not needed??
        match = re.search(r"^(\d+(?:\.\d+)?)", v.strip())
        if match:
            return float(match.group(1))
        return 1.0


class MealPlanRequest(BaseModel):
    scored_deals: List[DealInput] = Field(
        ...,
        validation_alias=AliasChoices("scored_deals", "top_deals"),
    )
    household_size: int = Field(
        default=2,
        ge=1,
        le=10,
        validation_alias=AliasChoices("household_size", "servings"),
    )
    target_meal_count: int = Field(
        default=3,
        ge=1,
        le=7,
        validation_alias=AliasChoices("target_meal_count", "days_count"),
    )
    preferred_cuisines: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("preferred_cuisines", "cuisines"),
    )
    dietary_restrictions: List[str] = Field(default_factory=list)
    avoid_ingredients: List[str] = Field(default_factory=list)


class MealPlanResponse(BaseModel):
    plan_id: str = Field(
        ...,
        validation_alias=AliasChoices("plan_id", "meal_plan_id")
    )
    meals: List[PlannedMeal]
    missing_primary_ingredients: List[MissingIngredient] = Field(default_factory=list)
    estimated_total_spend: float = 0.0