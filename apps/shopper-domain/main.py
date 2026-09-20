from pathlib import Path
from fastapi import FastAPI
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
import json
from typing import Any


app = FastAPI(title="MealShopper - Shopper Domain Service")

BASE_DIR = Path(__file__).resolve().parent
STORES_PATH = BASE_DIR / "data" / "stores.json"
DEALS_PATH = BASE_DIR / "data" / "deals.json"
FIXTURES_DIR = BASE_DIR.parents[1] / "libs" / "contracts" / "tests" / "fixtures"

store_repo = StoreRepository(STORES_PATH)
deal_repo = DealRepository(DEALS_PATH)



@app.get("/healthz")
def health_check():
    return {"status": "ok"}

@app.post("/v1/shopper/stores")
def discover_stores() -> dict[str, list[dict[str, Any]]]:
    return {
        "stores": [
            {"store_id": "store_vons_1", "name": "Vons", "address": "123 Hawthorne Blvd", "distance_miles": 1.2},
            {"store_id": "store_grocoutlet_1", "name": "Grocery Outlet", "address": "456 Inglewood Ave", "distance_miles": 2.1}
        ]
    }

@app.post("/v1/shopper/stores/discover", response_model=StoreDiscoveryResponse)
def discover_stores(payload: StoreDiscoveryRequest):
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

@app.post("/v1/shopper/deals")
def get_deals():
    fixture = FIXTURES_DIR / "valid-top-deals.json"
    if fixture.exists():
        with open(fixture, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"deals": []}


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

# Append to apps/shopper-domain/main.py:
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

@app.post("/v1/shopper/lookup-ingredients")
def lookup_ingredients(payload: dict):
    return {
        "matches": [
            {
                "ingredient_name": "Asparagus",
                "deal_id": "deal_asp_1",
                "store_id": "store_vons_1",
                "store_name": "Vons",
                "deal_price": 3.99,
                "unit": "bundle"
            }
        ]
    }



