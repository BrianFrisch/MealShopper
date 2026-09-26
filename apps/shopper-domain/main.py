from contextlib import asynccontextmanager
from datetime import datetime
import os
import redis.asyncio as redis 
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import (
    StoreDiscoveryRequest,
    StoreDiscoveryResponse,
    DealScoringRequest,
    DealScoringResponse,
    IngredientMatchRequest,
    IngredientMatchResponse,
)
from geo_service import StoreRepository
from deal_service import DealRepository
from pydantic import BaseModel, Field, AliasChoices
from src.storage.deal_storage import PartitionedDealStorage

app = FastAPI(title="MealShopper - Shopper Domain Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STORES_PATH = BASE_DIR / "data" / "stores.json"
DEALS_PATH = BASE_DIR / "data" / "deals.json"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_pool: Optional[redis.ConnectionPool] = None
store_repo = StoreRepository(STORES_PATH)
deal_repo = DealRepository(DEALS_PATH)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_pool
    redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    yield
    if redis_pool:
        await redis_pool.disconnect()


@app.get("/healthz")
def health_check():
    return {"status": "ok"}


# ---- Store Discovery Endpoints ----

@app.post("/v1/shopper/stores/discover", response_model=StoreDiscoveryResponse)
def discover_stores_v1(payload: StoreDiscoveryRequest):
    matched_stores = store_repo.find_nearby(
        user_lat=payload.latitude,
        user_lon=payload.longitude,
        radius_miles=payload.radius_miles,
        max_stores=payload.max_stores,
    )
    return StoreDiscoveryResponse(
        stores=matched_stores,
        total_found=len(matched_stores),
    )


class LegacyStoreRequest(BaseModel):
    latitude: float = 33.894893
    longitude: float = -118.362658
    radius_miles: float = 5.0
    max_stores: int = 3


@app.post("/v1/shopper/stores")
def discover_stores_legacy(payload: LegacyStoreRequest) -> Dict[str, Any]:
    matched = store_repo.find_nearby(
        user_lat=payload.latitude,
        user_lon=payload.longitude,
        radius_miles=payload.radius_miles,
        max_stores=payload.max_stores,
    )
    return {
        "stores": [
            {
                "id": s.id,
                "store_id": s.id,
                "name": s.name,
                "address": f"{s.street}, {s.city}",
                "distance_miles": s.distance_miles or 0.0,
            }
            for s in matched
        ]
    }

# ---- Deal Scoring & Ingestion Endpoints ----

class LegacyDealsRequest(BaseModel):
    store_ids: List[str] = Field(default_factory=list)
    avoid_ingredients: List[str] = Field(default_factory=list)


@app.post("/v1/shopper/deals")
def get_deals_legacy(payload: LegacyDealsRequest) -> Dict[str, Any]:
    """Dynamically queries deals.json for the Orchestrator client."""
    scored = deal_repo.get_scored_deals(
        store_ids=payload.store_ids,
        avoid_ingredients=payload.avoid_ingredients,
        top_n=10,
    )
    return {
        "deals": [
            {
                "deal_id": d.deal_id,
                "store_id": d.store_id,
                "store_name": d.store_name,
                "item_name": d.item_name,
                "normalized_category": d.category,
                "deal_price": d.price,
                "original_price": round(d.price * (1 + (d.discount_percentage / 100.0)), 2),
                "currency": "USD",
                "unit": d.unit,
                "value_score": d.deal_score or round(d.discount_percentage * 1.5, 2),
            }
            for d in scored
        ]
    }


@app.post("/v1/shopper/deals/score", response_model=DealScoringResponse)
def score_deals(payload: DealScoringRequest):
    scored = deal_repo.get_scored_deals(
        store_ids=payload.store_ids,
        avoid_ingredients=payload.avoid_ingredients,
        top_n=payload.top_n,
    )
    return DealScoringResponse(
        deals=scored,
        total_scored=len(scored),
    )

def get_deal_storage() -> PartitionedDealStorage:
    client = redis.Redis(connection_pool=redis_pool)
    return PartitionedDealStorage(redis_client=client)

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

@app.post("/v1/deals/ingest")
async def ingest_store_deals(
    payload: StoreCircularIngestRequest,
    storage: PartitionedDealStorage = Depends(get_deal_storage)
) -> Dict[str, Any]:
    deals_data = [item.model_dump() for item in payload.deals]
    paths = await storage.save_deals(
        store_id=payload.store_id,
        deals=deals_data,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to
    )
    return {
        "status": "success",
        "store_id": payload.store_id,
        "deal_count": len(deals_data),
        "persisted_partitions": paths
    }

@app.get("/v1/deals/stores/{store_id}")
async def get_store_deals(
    store_id: str,
    storage: PartitionedDealStorage = Depends(get_deal_storage)
) -> Dict[str, Any]:
    results = await storage.get_deals_for_stores([store_id])
    deals = results.get(store_id, [])
    if not deals:
        raise HTTPException(status_code=404, detail="No active deals found for store")
    return {"store_id": store_id, "deals": deals}

# ---- Loop-Back Matching Endpoints ----

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

@app.post("/v1/shopper/lookup-ingredients")
def lookup_ingredients(payload: LookupIngredientsRequest) -> Dict[str, Any]:
    """Dynamically runs fuzzy matching against deals.json for loop-back."""
    names: List[str] = []
    for item in payload.missing_ingredients:
        if isinstance(item, dict):
            names.append(
                item.get("ingredient_name")
                or item.get("name")
                or item.get("Name")
                or item.get("IngredientName")
                or "" # type: ignore
            )
        elif isinstance(item, str):
            names.append(item)
        elif hasattr(item, "name"):
            names.append(getattr(item, "name"))
        elif hasattr(item, "ingredient_name"):
            names.append(getattr(item, "ingredient_name"))

    valid_names = [n.strip() for n in names if n.strip()]

    matches = deal_repo.find_matching_deals(
        store_ids=payload.store_ids,
        missing_ingredients=valid_names,
        similarity_threshold=60.0,
    )

    return {
        "matches": [
            {
                "ingredient_name": m.missing_ingredient,
                "deal_id": m.deal_id,
                "store_id": m.store_id,
                "store_name": m.store_name,
                "deal_price": m.price,
                "unit": m.unit,
            }
            for m in matches
        ]
    }

@app.post("/v1/shopper/deals/match", response_model=IngredientMatchResponse)
def match_missing_ingredients(payload: IngredientMatchRequest):
    results = deal_repo.find_matching_deals(
        store_ids=payload.store_ids,
        missing_ingredients=payload.missing_ingredients,
        similarity_threshold=payload.similarity_threshold,
    )
    return IngredientMatchResponse(
        matches=results,
        total_matched=len(results),
    )