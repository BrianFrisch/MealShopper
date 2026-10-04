from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Optional

try:
    from src.ingestion.models import NormalizedDealItem, clean_product_name
except ImportError:
    from ..models import NormalizedDealItem, clean_product_name

logger = logging.getLogger(__name__)

DEFAULT_CATEGORY_MAP: dict[str, str] = {
    "produce": "Produce",
    "fresh produce": "Produce",
    "fruit": "Produce",
    "fruits": "Produce",
    "vegetable": "Produce",
    "vegetables": "Produce",
    "dairy": "Dairy",
    "dairy & eggs": "Dairy",
    "eggs": "Dairy",
    "meat": "Meat",
    "fresh meat": "Meat",
    "poultry": "Meat",
    "beef": "Meat",
    "pork": "Meat",
    "chicken": "Meat",
    "seafood": "Seafood",
    "fresh seafood": "Seafood",
    "fish": "Seafood",
    "bakery": "Bakery",
    "bread": "Bakery",
    "pantry": "Pantry",
    "grocery": "Pantry",
    "snacks": "Pantry",
    "beverages": "Pantry",
    "frozen": "Pantry",
    "aldi finds": "Pantry",
}


class BaseDealAdapter(ABC):
    """
    Abstract base class for grocery store circular/deal adapters.
    Implements the Template Method pattern for deal ingestion and normalization.
    """

    category_map: dict[str, str] = DEFAULT_CATEGORY_MAP

    @abstractmethod
    async def fetch_flyer_metadata(
        self,
        postal_code: str,
        chain_id: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[Optional[str], datetime, datetime]:
        """
        Fetch circular/flyer metadata for a given postal code and chain,
        returning a tuple of (flyer_id, valid_from, valid_to).
        """
        pass

    @abstractmethod
    async def fetch_raw_items(self, flyer_id: Any) -> list[dict[str, Any]]:
        """
        Fetch raw promotional item dictionaries for a given flyer ID.
        """
        pass

    @abstractmethod
    def extract_product_name(self, item: dict[str, Any]) -> str:
        """
        Extract the raw product name from an item dictionary.
        """
        pass

    @abstractmethod
    def extract_pricing(
        self, item: dict[str, Any]
    ) -> tuple[Optional[float], Optional[float], str]:
        """
        Extract pricing information from an item dictionary,
        returning (sale_price, original_price, unit).
        """
        pass

    @abstractmethod
    def extract_raw_category(self, item: dict[str, Any]) -> str:
        """
        Extract the raw category string from an item dictionary.
        """
        pass

    def standardize_category(self, raw_category: str, product_name: str = "") -> str:
        """
        Maps raw category strings and product titles to standardized categories:
        Produce, Dairy, Meat, Seafood, Bakery, Pantry.
        """
        raw_clean = (raw_category or "").strip()
        item_clean = (product_name or "").lower()
        cat_lower = raw_clean.lower()
        combined = f"{cat_lower} {item_clean}"

        # 1. Prepared / Convenience / Non-food items -> Pantry (evaluated on COMBINED text)
        pantry_terms = [
            "pizza", "hot pocket", "hot pockets", "burrito", "chimichanga",
            "lasagna", "meal kit", "tv dinner", "bites", "waffles", "ice cream",
            "chips", "candy", "cookies", "crackers", "cereal", "tortillas",
            "buns", "bread", "dressing", "sauce", "mustard", "mayo",
            "beverage", "soda", "beer", "wine", "tequila", "whiskey", "vodka",
            "wipes", "charcoal", "pillow", "bucket", "tissue", "toothpaste", "shampoo",
        ]
        if any(term in combined for term in pantry_terms):
            return "Pantry"

        # 2. Seafood checks
        seafood_terms = [
            "seafood", "fish", "shrimp", "salmon", "tilapia", "tuna", "crab",
            "lobster", "cod", "flounder", "scallop", "trout", "halibut", "mahi"
        ]
        if any(k in combined for k in seafood_terms):
            return "Seafood"

        # 3. Meat checks (Must run BEFORE generic category_map like 'grocery')
        meat_terms = [
            "fresh meat", "meat", "poultry", "beef", "pork", "chicken", "turkey",
            "steak", "steaks", "lamb", "ribs", "sausage", "bacon", "roast", "roasts",
            "chop", "chops", "drumstick", "drumsticks", "wing", "wings", "tri-tip",
            "tri tip", "flanken", "ribeye", "tenderloin", "brisket", "patties", "ground beef"
        ]
        if any(k in combined for k in meat_terms):
            return "Meat"

        # 4. Produce checks
        produce_terms = [
            "produce", "fruit", "fruits", "vegetable", "vegetables", "greens",
            "apple", "apples", "banana", "bananas", "avocado", "avocados", "berry",
            "berries", "strawberries", "salad", "spinach", "lettuce", "tomato",
            "tomatoes", "potato", "potatoes", "onion", "onions", "carrot", "carrots",
            "pepper", "peppers", "cucumber", "zucchini", "squash", "broccoli",
            "asparagus", "celery", "citrus", "orange", "oranges", "lemon", "lemons",
            "lime", "limes", "corn", "peaches", "plums", "grapes", "cantaloupe", "mandarins"
        ]
        if any(k in combined for k in produce_terms):
            return "Produce"

        # 5. Dairy checks
        dairy_terms = [
            "dairy & eggs", "dairy", "cheese", "milk", "egg", "eggs", "yogurt",
            "butter", "cream", "cheddar", "mozzarella", "sour cream", "cottage cheese"
        ]
        if any(k in combined for k in dairy_terms):
            return "Dairy"

        # 6. Bakery checks
        bakery_terms = [
            "bakery", "bread", "bagel", "bagels", "pastry", "muffin", "muffins",
            "croissant", "cake", "rolls", "brioche"
        ]
        if any(k in combined for k in bakery_terms):
            return "Bakery"

        # 7. Explicit category map fallback (excluding generic 'grocery')
        if cat_lower in self.category_map and cat_lower != "grocery":
            return self.category_map[cat_lower]

        return "Pantry"

    async def get_normalized_deals(
        self,
        postal_code: str,
        store_id: str,
        merchant_name: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[datetime, datetime, list[NormalizedDealItem]]:
        """
        Template method orchestrating the ingestion and normalization of circular deals.
        1. Fetches flyer metadata (flyer_id, valid_from, valid_to).
        2. Fetches raw promotional items using flyer_id.
        3. Loops through items, applying concrete category standardizing and name cleaning.
        """
        chain_id = merchant_name or kwargs.get("chain_id") or store_id
        now = datetime.now(timezone.utc)
        default_valid_from = now
        default_valid_to = now + timedelta(days=7)

        meta = await self.fetch_flyer_metadata(postal_code, chain_id=chain_id, **kwargs)
        if not meta:
            logger.warning("No flyer metadata found for postal_code=%s chain=%s", postal_code, chain_id)
            return default_valid_from, default_valid_to, []

        flyer_id, valid_from, valid_to = meta
        if not flyer_id:
            logger.warning("No active flyer ID resolved for postal_code=%s chain=%s", postal_code, chain_id)
            return valid_from or default_valid_from, valid_to or default_valid_to, []

        valid_from = valid_from or default_valid_from
        valid_to = valid_to or default_valid_to

        raw_items = await self.fetch_raw_items(flyer_id)
        if not raw_items:
            logger.warning("No raw items found for flyer_id=%s", flyer_id)
            return valid_from, valid_to, []

        effective_store_name = (
            merchant_name
            or getattr(self, "default_merchant", None)
            or getattr(self, "DEFAULT_MERCHANT", None)
            or chain_id
            or store_id
        )

        normalized_deals: list[NormalizedDealItem] = []
        for item in raw_items:
            product_name = self.extract_product_name(item)
            if not product_name:
                continue

            clean_name = clean_product_name(product_name)

            pricing = self.extract_pricing(item)
            if not pricing:
                continue
            sale_price, original_price, unit = pricing
            if sale_price is None or sale_price < 0:
                continue

            raw_cat = self.extract_raw_category(item)
            normalized_cat = self.standardize_category(raw_cat, product_name)
            
            item_id = item.get("id") or item.get("item_id") or item.get("flyer_item_id")
            if item_id is not None:
                deal_id = f"{store_id}_{item_id}"
            else:
                deal_id = f"{store_id}_{abs(hash(clean_name))}"

            raw_promo = str(
                item.get("sale_story")
                or item.get("pre_price_text")
                or item.get("post_price_text")
                or item.get("description")
                or f"${sale_price:.2f} {unit or 'each'}"
            )

            value_score = 8.0
            if original_price is not None and original_price > sale_price > 0:
                savings = (original_price - sale_price) / original_price
                if savings > 0.20:
                    value_score = round(min(8.0 + (savings - 0.20) * 5.0, 10.0), 1)

            normalized_deals.append(
                NormalizedDealItem(
                    deal_id=deal_id,
                    store_id=store_id,
                    store_name=effective_store_name,
                    item_name=product_name,
                    clean_name=clean_name,
                    normalized_category=normalized_cat,
                    deal_price=sale_price,
                    original_price=original_price,
                    currency="USD",
                    unit=unit or "each",
                    value_score=value_score,
                    raw_promotion_text=raw_promo,
                    valid_from=valid_from,
                    valid_to=valid_to,
                )
            )

        return valid_from, valid_to, normalized_deals

    async def close(self) -> None:
        """Closes any underlying client or network connections."""
        pass

    async def __aenter__(self) -> "BaseDealAdapter":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
