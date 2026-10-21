from typing import Any, Dict, List
from fastapi import APIRouter, Depends
import logging

from deal_service import find_matching_deals, get_scored_deals, map_live_deal
from dependencies import get_deal_storage
from models import (
    DealBatchLookupRequest,
    DealBatchLookupResponse,
    DealScoringRequest,
    DealScoringResponse,
    IngredientMatchRequest,
    IngredientMatchResponse,
    LegacyDealsRequest,
    LookupIngredientsRequest,
)
from src.storage.deal_storage import PartitionedDealStorage

router = APIRouter(prefix="/v1/shopper", tags=["Deals"])

logger = logging.getLogger(__name__)

async def _get_live_deals(
    store_ids: list[str],
    storage: PartitionedDealStorage,
) -> list[dict[str, Any]]:
    deals_by_store = await storage.get_deals_for_stores(store_ids, tier="all")
    return [
        deal
        for store_id in store_ids
        for deal in deals_by_store.get(store_id, [])
    ]


@router.post("/deals")
async def get_deals_legacy(
    payload: LegacyDealsRequest,
    deal_storage: PartitionedDealStorage = Depends(get_deal_storage),
) -> Dict[str, Any]:
    live_deals = await _get_live_deals(payload.store_ids, deal_storage)
    scored = get_scored_deals(
        deals=live_deals,
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


@router.post("/deals/score", response_model=DealScoringResponse)
async def score_deals(
    payload: DealScoringRequest,
    deal_storage: PartitionedDealStorage = Depends(get_deal_storage),
) -> DealScoringResponse:
    live_deals = await _get_live_deals(payload.store_ids, deal_storage)
    scored = get_scored_deals(
        deals=live_deals,
        store_ids=payload.store_ids,
        avoid_ingredients=payload.avoid_ingredients,
        top_n=payload.top_n,
    )
    return DealScoringResponse(
        deals=scored,
        total_scored=len(scored),
    )


@router.post("/lookup-ingredients")
async def lookup_ingredients(
    payload: LookupIngredientsRequest,
    deal_storage: PartitionedDealStorage = Depends(get_deal_storage),
) -> Dict[str, Any]:
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

    live_deals = await _get_live_deals(payload.store_ids, deal_storage)
    matches = find_matching_deals(
        deals=live_deals,
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


@router.post("/deals/match", response_model=IngredientMatchResponse)
async def match_missing_ingredients(
    payload: IngredientMatchRequest,
    deal_storage: PartitionedDealStorage = Depends(get_deal_storage),
) -> IngredientMatchResponse:
    live_deals = await _get_live_deals(payload.store_ids, deal_storage)
    results = find_matching_deals(
        deals=live_deals,
        store_ids=payload.store_ids,
        missing_ingredients=payload.missing_ingredients,
        similarity_threshold=payload.similarity_threshold,
    )
    return IngredientMatchResponse(
        matches=results,
        total_matched=len(results),
    )


@router.post("/deals/batch-lookup", response_model=DealBatchLookupResponse)
async def batch_lookup_deals(
    payload: DealBatchLookupRequest,
    deal_storage: PartitionedDealStorage = Depends(get_deal_storage),
) -> DealBatchLookupResponse:
    requested_pairs = [
        (item.store_id, item.deal_id) for item in payload.items
    ]
    for requested in requested_pairs:
        logger.info("Looking up deal for store_id=%s, deal_id=%s", requested[0], requested[1])
    live_deal_data = await deal_storage.get_deals_by_keys(requested_pairs)
    logger.info("Found %d deals for requested pairs", len(live_deal_data))
    deals = [map_live_deal(deal) for deal in live_deal_data]
    logger.info("Mapped %d live deals to Deal models", len(deals))
    return DealBatchLookupResponse(
        deals=deals,
        total_found=len(deals),
    )
