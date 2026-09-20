import json
from pathlib import Path
from typing import List
from models import Deal
from rapidfuzz import fuzz
from models import Deal, MatchedIngredientDeal




class DealRepository:
    def __init__(self, data_path: Path):
        self._deals: List[Deal] = []
        if data_path.exists():
            with open(data_path, "r", encoding="utf-8") as f:
                raw_deals = json.load(f)
                self._deals = [Deal(**item) for item in raw_deals]

    def get_scored_deals(
        self,
        store_ids: List[str],
        avoid_ingredients: List[str],
        top_n: int = 10,
    ) -> List[Deal]:
        avoid_set = {ing.strip().lower() for ing in avoid_ingredients if ing.strip()}
        eligible_deals: List[Deal] = []

        for deal in self._deals:
            # 1. Store filtering: Only consider stores selected in Phase 1
            if deal.store_id not in store_ids:
                continue

            # 2. Dietary avoidance: Reject deals matching avoid list
            deal_name_lower = deal.item_name.lower()
            primary_lower = deal.primary_ingredient.lower()
            if any(avoid in deal_name_lower or avoid in primary_lower for avoid in avoid_set):
                continue

            # 3. Score calculation: Primary weight on discount depth
            score = round(deal.discount_percentage * 1.5, 2)
            deal_copy = deal.model_copy(update={"deal_score": score})
            eligible_deals.append(deal_copy)

        # 4. Sort descending by score and cap at top_n
        eligible_deals.sort(key=lambda d: d.deal_score or 0.0, reverse=True)
        return eligible_deals[:top_n]


# Add this method to DealRepository:
    def find_matching_deals(
        self,
        store_ids: List[str],
        missing_ingredients: List[str],
        similarity_threshold: float = 65.0,
    ) -> List[MatchedIngredientDeal]:
        matches: List[MatchedIngredientDeal] = []

        # Only evaluate deals from stores included in the user's route
        active_deals = [d for d in self._deals if d.store_id in store_ids]

        for missing in missing_ingredients:
            missing_clean = missing.strip().lower()
            best_match: MatchedIngredientDeal | None = None
            best_score = 0.0

            for deal in active_deals:
                # Compare both raw item title and primary ingredient tag
                score_item = fuzz.token_set_ratio(missing_clean, deal.item_name.lower())
                score_primary = fuzz.token_set_ratio(missing_clean, deal.primary_ingredient.lower())
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

            if best_match:
                matches.append(best_match)

        return matches