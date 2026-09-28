import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import redis.asyncio as redis 
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, logger
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
from src.ingestion.models import TopDealsResponse, RegionContextDto, CoordinatesDto, NormalizedDealItem
from src.ingestion.factory import DealAdapterFactory

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
    logger.logger.info("Initializing Redis connection pool for Shopper Domain at %s", REDIS_URL)
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
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    client = redis.Redis(connection_pool=redis_pool)
    return PartitionedDealStorage(redis_client=client)

def get_deal_adapter_factory() -> DealAdapterFactory:
    return DealAdapterFactory()

async def ingest_store_on_demand(
    store_id: str,
    chain: str,
    postal_code: str,
    storage: PartitionedDealStorage,
    factory: DealAdapterFactory
) -> list[dict[str, Any]]:
    adapter = factory.get_adapter(chain)
    if adapter is None:
        return []

    lock_key = f"lock:ingest:{store_id}"
    redis_client = storage.redis
    lock_ttl_seconds = 15

    # 1. Attempt to acquire ingestion lock
    acquired = await redis_client.set(lock_key, "1", nx=True, ex=lock_ttl_seconds)

    if not acquired:
        logger.logger.info("Store %s is currently being ingested by another request. Awaiting result...", store_id)
        # Poll up to 6 seconds (12 x 500ms) for the scraping worker to complete
        for _ in range(12):
            await asyncio.sleep(0.5)
            # Check if deals are now available in Redis/disk
            cached = await storage.get_deals_for_stores([store_id])
            deals = cached.get(store_id, [])
            if deals:
                return deals
            # If lock cleared, worker finished or released
            if not await redis_client.exists(lock_key):
                break

        # Final fallback check
        cached = await storage.get_deals_for_stores([store_id])
        return cached.get(store_id, [])

    # 2. Worker executing the scrape
    try:
        valid_from, valid_to, deals = await adapter.get_normalized_deals(
            postal_code=postal_code,
            store_id=store_id,
            merchant_name=chain,
        )
        if deals:
            deal_dicts = [d.model_dump() if hasattr(d, "model_dump") else d for d in deals]
            await storage.save_deals(store_id, deal_dicts, valid_from, valid_to)
            return deal_dicts
        return []
    except Exception as exc:
        logger.logger.error("On-demand ingestion failed for store %s (%s): %s", store_id, chain, exc, exc_info=True)
        return []
    finally:
        # 3. Always release lock so queued readers can complete immediately
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass

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
    postal_code: Optional[str] = None,
    chain: Optional[str] = None,
    storage: PartitionedDealStorage = Depends(get_deal_storage),
    factory: DealAdapterFactory = Depends(get_deal_adapter_factory)
) -> Dict[str, Any]:
    # 1. Check local/Redis cache
    results = await storage.get_deals_for_stores([store_id])
    deals = results.get(store_id, [])

    # 2. Lazy ingest on miss if params provided
    if not deals and postal_code and chain:
        deals = await ingest_store_on_demand(store_id, chain, postal_code, storage, factory)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "region_context": {
            "coordinates": {"latitude": 33.8895, "longitude": -118.3533},
            "store_ids": [store_id],
        },
        "deals": deals,
    }


class EvaluateTopDealsRequest(BaseModel):
    store_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=30, ge=1, le=100)


@app.post("/v1/deals/evaluate-top", response_model=TopDealsResponse)
async def evaluate_top_deals(
    payload: EvaluateTopDealsRequest,
    storage: PartitionedDealStorage = Depends(get_deal_storage),
) -> TopDealsResponse:
    if not payload.store_ids:
        return TopDealsResponse(
            timestamp=datetime.now(timezone.utc),
            region_context=RegionContextDto(
                coordinates=CoordinatesDto(latitude=33.8895, longitude=-118.3533),
                store_ids=[],
            ),
            deals=[],
        )

    deals_by_store = await storage.get_deals_for_stores(payload.store_ids)

    # Flatten deals across all stores
    all_deals_raw: list[dict[str, Any]] = []
    for sid in payload.store_ids:
        store_deals = deals_by_store.get(sid, [])
        all_deals_raw.extend(store_deals)

    # Deduplicate by clean_name, keeping the deal with lowest deal_price
    deduped_deals: dict[str, dict[str, Any]] = {}
    for d in all_deals_raw:
        clean_name = d.get("clean_name") or d.get("item_name") or d.get("product_name") or ""
        clean_key = clean_name.strip().lower()
        if not clean_key:
            clean_key = str(d.get("deal_id") or id(d))

        raw_price = d.get("deal_price")
        if raw_price is None:
            raw_price = d.get("price") or d.get("sale_price") or 0.0
        deal_price = float(raw_price)

        if clean_key not in deduped_deals:
            deduped_deals[clean_key] = d
        else:
            existing = deduped_deals[clean_key]
            existing_raw = existing.get("deal_price")
            if existing_raw is None:
                existing_raw = existing.get("price") or existing.get("sale_price") or 0.0
            existing_price = float(existing_raw)
            if deal_price < existing_price:
                deduped_deals[clean_key] = d

    # Convert to NormalizedDealItem models
    normalized_items: list[NormalizedDealItem] = []
    for d in deduped_deals.values():
        if isinstance(d, NormalizedDealItem):
            normalized_items.append(d)
        else:
            normalized_items.append(NormalizedDealItem.model_validate(d))

    # Sort descending by value_score
    normalized_items.sort(key=lambda x: x.value_score, reverse=True)

    # Take limit items
    selected_deals = normalized_items[: payload.limit]

    return TopDealsResponse(
        timestamp=datetime.now(timezone.utc),
        region_context=RegionContextDto(
            coordinates=CoordinatesDto(latitude=33.8895, longitude=-118.3533),
            store_ids=payload.store_ids,
        ),
        deals=selected_deals,
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