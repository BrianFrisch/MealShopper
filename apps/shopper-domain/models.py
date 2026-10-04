from datetime import datetime
from typing import Any, List, Optional
from pydantic import AliasChoices, BaseModel, Field


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
    chain_id: Optional[str] = None
    adapter_name: Optional[str] = None


class StoreDiscoveryRequest(BaseModel):
    """Payload for locating nearby grocery stores within a geographic radius."""
    latitude: float = Field(..., description="User's starting latitude")
    longitude: float = Field(..., description="User's starting longitude")
    radius_miles: float = Field(default=5.0, description="Search radius (1, 2, 5, 7, 10)")
    max_stores: int = Field(default=2, ge=1, le=4, description="Store cap (1 to 4)")


class StoreDiscoveryResponse(BaseModel):
    stores: List[Store]
    total_found: int


class LegacyStoreRequest(BaseModel):
    latitude: float = 33.894893
    longitude: float = -118.362658
    radius_miles: float = 5.0
    max_stores: int = 3


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


class LegacyDealsRequest(BaseModel):
    store_ids: List[str] = Field(default_factory=list)
    avoid_ingredients: List[str] = Field(default_factory=list)


class DealItemDto(BaseModel):
    product_name: str
    clean_name: str
    category: str
    sale_price: float
    pricing_unit: str
    raw_promotion_text: str


class StoreCircularIngestRequest(BaseModel):
    store_id: str
    store_chain: str
    valid_from: datetime
    valid_to: datetime
    deals: List[DealItemDto]


class EvaluateTopDealsRequest(BaseModel):
    store_ids: List[str] = Field(default_factory=list)
    limit: int = Field(default=30, ge=1, le=100)
    tier: str = Field(default="primary", description="primary (meat/seafood), secondary, or all")


class LookupIngredientsRequest(BaseModel):
    store_ids: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("store_ids", "storeIds", "StoreIds"),
    )
    missing_ingredients: List[Any] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "missing_ingredients",
            "missingIngredients",
            "MissingIngredients",
            "items",
            "Items",
        ),
    )


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


class AdminStoreImportRequest(BaseModel):
    chain_id: str = Field(..., description="Target chain identifier (e.g. ralphs, aldi, vons)")
    region: str = Field(default="California", description="State or region name for Overpass query")
    all_brands: bool = Field(default=False, description="If true, imports all banners for the chain; otherwise filters by primary banner only")
