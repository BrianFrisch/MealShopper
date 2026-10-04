from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException

from dependencies import (
    get_deal_adapter_factory,
    get_deal_storage,
    get_store_repository,
)
from geo_service import StoreRepository
from models import EvaluateTopDealsRequest, StoreCircularIngestRequest
from src.ingestion.factory import DealAdapterFactory
from src.ingestion.models import CoordinatesDto, RegionContextDto, TopDealsResponse
from src.services.deal_evaluator import deduplicate_and_rank_deals
from src.services.on_demand_ingestion import ingest_store_on_demand
from src.storage.deal_storage import PartitionedDealStorage

router = APIRouter(prefix="/v1/deals", tags=["Circulars"])


@router.post("/ingest")
async def ingest_store_deals(
    payload: StoreCircularIngestRequest,
    storage: PartitionedDealStorage = Depends(get_deal_storage),
) -> Dict[str, Any]:
    deals_data = [item.model_dump() for item in payload.deals]
    paths = await storage.save_deals(
        flyer_id=payload.store_id,
        deals=deals_data,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    return {
        "status": "success",
        "store_id": payload.store_id,
        "deal_count": len(deals_data),
        "persisted_partitions": paths,
    }


@router.get("/stores/{store_id}")
async def get_store_deals(
    store_id: str,
    tier: str = "primary",  # "primary", "secondary", or "all"
    postal_code: Optional[str] = None,
    chain: Optional[str] = None,
    storage: PartitionedDealStorage = Depends(get_deal_storage),
    factory: DealAdapterFactory = Depends(get_deal_adapter_factory),
    store_repo: StoreRepository = Depends(get_store_repository),
) -> Dict[str, Any]:
    # 1. Lookup store context (postal_code, chain_id)
    eff_postal = postal_code
    eff_chain = chain

    # Fast-path: Check cached store context in Redis
    if not eff_postal or not eff_chain:
        try:
            cached_ctx_raw = await storage.redis.get(f"deals:store:{store_id}:context")
            if cached_ctx_raw:
                cached_ctx = json.loads(cached_ctx_raw)
                eff_postal = eff_postal or cached_ctx.get("postal_code")
                eff_chain = eff_chain or cached_ctx.get("chain_id")
        except Exception:
            pass

    # Fallback to database store context lookup
    if not eff_postal or not eff_chain:
        try:
            ctx = await store_repo.get_store_context(store_id)
            if ctx:
                eff_postal = eff_postal or ctx.zip_code
                eff_chain = eff_chain or ctx.chain_id or ctx.adapter_name
        except Exception:
            pass

    deals: list[dict[str, Any]] = []
    flyer_id: Optional[str] = None

    # 2. Check if we have a cached flyer_id for that postal_code/chain
    if eff_postal and eff_chain:
        flyer_id = await storage.get_flyer_id_for_postal(eff_postal, eff_chain)

    # 3. If yes, fetch the deals directly using that flyer_id
    if flyer_id:
        deals = await storage.get_deals_by_flyer_id(flyer_id, tier=tier)

    # 4. If no flyer_id is cached, or the deals are missing, call the adapter to fetch the metadata,
    #    cache the routing key, process the deals, and save them by flyer_id.
    if not flyer_id or not deals:
        if eff_postal and eff_chain:
            deals = await ingest_store_on_demand(
                store_id=store_id,
                chain=eff_chain,
                postal_code=eff_postal,
                storage=storage,
                factory=factory,
                tier=tier,
            )

    if not deals:
        raise HTTPException(
            status_code=404,
            detail=f"No circular deals found for store {store_id}",
        )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "store_id": store_id,
        "tier": tier,
        "deals_count": len(deals),
        "deals": deals,
    }


@router.post("/evaluate-top", response_model=TopDealsResponse)
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

    # Load only the specified tier (defaults strictly to "primary" meat/seafood)
    deals_by_store = await storage.get_deals_for_stores(
        payload.store_ids, tier=payload.tier
    )

    all_deals_raw: list[dict[str, Any]] = []
    for sid in payload.store_ids:
        store_deals = deals_by_store.get(sid, [])
        all_deals_raw.extend(store_deals)

    selected_deals = deduplicate_and_rank_deals(all_deals_raw, limit=payload.limit)

    return TopDealsResponse(
        timestamp=datetime.now(timezone.utc),
        region_context=RegionContextDto(
            coordinates=CoordinatesDto(latitude=33.8895, longitude=-118.3533),
            store_ids=payload.store_ids,
        ),
        deals=selected_deals,
    )
