from pathlib import Path
from typing import Any, List
from fastapi import FastAPI
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

store_repo = StoreRepository(STORES_PATH)
deal_repo = DealRepository(DEALS_PATH)


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
def discover_stores_legacy(payload: LegacyStoreRequest):
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
def get_deals_legacy(payload: LegacyDealsRequest):
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
def lookup_ingredients(payload: LookupIngredientsRequest):
    """Dynamically runs fuzzy matching against deals.json for loop-back."""
    names: List[str] = []
    for item in payload.missing_ingredients:
        if isinstance(item, dict):
            names.append(
                item.get("ingredient_name")
                or item.get("name")
                or item.get("Name")
                or item.get("IngredientName")
                or ""
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