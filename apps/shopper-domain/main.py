from fastapi import FastAPI
import json
from pathlib import Path
from typing import Any

app = FastAPI(title="Shopper Domain Stub")

# Locate the contract test fixture
BASE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BASE_DIR.parents[1] / "libs" / "contracts" / "tests" / "fixtures"

@app.post("/v1/shopper/stores")
def discover_stores() -> dict[str, list[dict[str, Any]]]:
    return {
        "stores": [
            {"store_id": "store_vons_1", "name": "Vons", "address": "123 Hawthorne Blvd", "distance_miles": 1.2},
            {"store_id": "store_grocoutlet_1", "name": "Grocery Outlet", "address": "456 Inglewood Ave", "distance_miles": 2.1}
        ]
    }

@app.post("/v1/shopper/deals")
def get_deals():
    fixture = FIXTURES_DIR / "valid-top-deals.json"
    if fixture.exists():
        with open(fixture, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"deals": []}

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