from typing import Any, List
from src.ingestion.models import NormalizedDealItem


def deduplicate_and_rank_deals(
    all_deals_raw: List[dict[str, Any]],
    limit: int = 30,
) -> List[NormalizedDealItem]:
    deduped_deals: dict[str, dict[str, Any]] = {}
    for d in all_deals_raw:
        clean_name = (
            d.get("clean_name")
            or d.get("item_name")
            or d.get("product_name")
            or ""
        )
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
                existing_raw = (
                    existing.get("price") or existing.get("sale_price") or 0.0
                )
            if deal_price < float(existing_raw):
                deduped_deals[clean_key] = d

    normalized_items: list[NormalizedDealItem] = [
        NormalizedDealItem.model_validate(d) if not isinstance(d, NormalizedDealItem) else d
        for d in deduped_deals.values()
    ]

    # Rank descending by score
    normalized_items.sort(key=lambda x: x.value_score, reverse=True)
    return normalized_items[:limit]
