from typing import List, Optional
from pydantic import BaseModel, Field


class Store(BaseModel):
    id: str
    name: str
    street: str
    city: str
    state: str
    zip_code: str
    latitude: float
    longitude: float
    distance_miles: Optional[float] = None


class StoreDiscoveryRequest(BaseModel):
    """Payload for locating nearby grocery stores within a geographic radius."""
    latitude: float = Field(..., description="User's starting latitude")
    longitude: float = Field(..., description="User's starting longitude")
    radius_miles: float = Field(default=5.0, description="Search radius (1, 2, 5, 7, 10)")
    max_stores: int = Field(default=2, ge=1, le=4, description="Store cap (1 to 4)")


class StoreDiscoveryResponse(BaseModel):
    stores: List[Store]
    total_found: int


class Deal(BaseModel):
    deal_id: str
    store_id: str
    store_name: str
    item_name: str
    category: str
    price: float
    unit: str
    discount_percentage: float
    primary_ingredient: str
    deal_score: Optional[float] = None


class DealScoringRequest(BaseModel):
    store_ids: List[str]
    avoid_ingredients: List[str] = Field(default_factory=list)
    top_n: int = Field(default=10, ge=1, le=50)


class DealScoringResponse(BaseModel):
    deals: List[Deal]
    total_scored: int

class IngredientMatchRequest(BaseModel):
    store_ids: List[str]
    missing_ingredients: List[str]
    similarity_threshold: float = Field(default=65.0, ge=0.0, le=100.0)


class MatchedIngredientDeal(BaseModel):
    missing_ingredient: str
    deal_id: str
    store_id: str
    store_name: str
    item_name: str
    price: float
    unit: str
    similarity_score: float


class IngredientMatchResponse(BaseModel):
    matches: List[MatchedIngredientDeal]
    total_matched: int