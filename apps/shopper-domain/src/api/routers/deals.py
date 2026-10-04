from typing import Any, Dict, List
from fastapi import APIRouter, Depends

from deal_service import DealRepository
from dependencies import get_deal_repository
from models import (
    DealScoringRequest,
    DealScoringResponse,
    IngredientMatchRequest,
    IngredientMatchResponse,
    LegacyDealsRequest,
    LookupIngredientsRequest,
)

router = APIRouter(prefix="/v1/shopper", tags=["Deals"])


@router.post("/deals")
def get_deals_legacy(
    payload: LegacyDealsRequest,
    deal_repo: DealRepository = Depends(get_deal_repository),
) -> Dict[str, Any]:
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


@router.post("/deals/score", response_model=DealScoringResponse)
def score_deals(
    payload: DealScoringRequest,
    deal_repo: DealRepository = Depends(get_deal_repository),
) -> DealScoringResponse:
    scored = deal_repo.get_scored_deals(
        store_ids=payload.store_ids,
        avoid_ingredients=payload.avoid_ingredients,
        top_n=payload.top_n,
    )
    return DealScoringResponse(
        deals=scored,
        total_scored=len(scored),
    )


@router.post("/lookup-ingredients")
def lookup_ingredients(
    payload: LookupIngredientsRequest,
    deal_repo: DealRepository = Depends(get_deal_repository),
) -> Dict[str, Any]:
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


@router.post("/deals/match", response_model=IngredientMatchResponse)
def match_missing_ingredients(
    payload: IngredientMatchRequest,
    deal_repo: DealRepository = Depends(get_deal_repository),
) -> IngredientMatchResponse:
    results = deal_repo.find_matching_deals(
        store_ids=payload.store_ids,
        missing_ingredients=payload.missing_ingredients,
        similarity_threshold=payload.similarity_threshold,
    )
    return IngredientMatchResponse(
        matches=results,
        total_matched=len(results),
    )
