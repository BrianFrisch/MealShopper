from typing import Any

from rapidfuzz import fuzz

from models import Deal, MatchedIngredientDeal


def map_live_deal(data: dict[str, Any]) -> Deal:
    deal_data = dict(data)
    price = deal_data.get("deal_price", deal_data.get("price"))
    original_price = deal_data.get("original_price")
    if "discount_percentage" not in deal_data:
        deal_data["discount_percentage"] = (
            round((original_price - price) / original_price * 100, 2)
            if original_price and price is not None and original_price > price
            else 0.0
        )
    return Deal.model_validate(deal_data)


def get_scored_deals(
    deals: list[dict[str, Any]],
    store_ids: list[str],
    avoid_ingredients: list[str],
    top_n: int,
) -> list[Deal]:
    avoid_set = {ingredient.strip().lower() for ingredient in avoid_ingredients if ingredient.strip()}
    scored: list[Deal] = []

    for deal_data in deals:
        deal = map_live_deal(deal_data)
        if deal.store_id not in store_ids:
            continue

        item_name = deal.item_name.lower()
        primary_ingredient = deal.primary_ingredient.lower()
        if any(
            ingredient in item_name or ingredient in primary_ingredient
            for ingredient in avoid_set
        ):
            continue

        score = round(deal.discount_percentage * 1.5, 2)
        if score == 0 and deal.deal_score is not None:
            score = deal.deal_score
        scored.append(deal.model_copy(update={"deal_score": score}))

    scored.sort(key=lambda deal: deal.deal_score or 0.0, reverse=True)
    return scored[:top_n]


def find_matching_deals(
    deals: list[dict[str, Any]],
    store_ids: list[str],
    missing_ingredients: list[str],
    similarity_threshold: float,
) -> list[MatchedIngredientDeal]:
    active_deals = [
        map_live_deal(data)
        for data in deals
        if str(data.get("store_id") or "") in store_ids
    ]
    matches: list[MatchedIngredientDeal] = []

    for missing in missing_ingredients:
        missing_clean = missing.strip().lower()
        if not missing_clean:
            continue

        best_match: MatchedIngredientDeal | None = None
        best_score = 0.0
        for deal in active_deals:
            score_item = fuzz.token_set_ratio(missing_clean, deal.item_name.lower())
            score_primary = fuzz.token_set_ratio(
                missing_clean, deal.primary_ingredient.lower()
            )
            top_score = max(score_item, score_primary)
            if top_score >= similarity_threshold and top_score > best_score:
                best_score = top_score
                best_match = MatchedIngredientDeal(
                    missing_ingredient=missing,
                    deal_id=deal.deal_id,
                    store_id=deal.store_id,
                    store_name=deal.store_name,
                    item_name=deal.item_name,
                    price=deal.price,
                    unit=deal.unit,
                    similarity_score=round(top_score, 2),
                )

        if best_match is not None:
            matches.append(best_match)

    return matches
