from datetime import datetime, timezone, timedelta
import logging
import re
from typing import Any, Optional
import httpx

try:
    from src.ingestion.models import NormalizedDealItem
    from src.ingestion.adapters.flipp_adapter import FlippAdapter, DEFAULT_TIMEOUT
except ImportError:
    from ..models import NormalizedDealItem
    from .flipp_adapter import FlippAdapter, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


class AldiAdapter(FlippAdapter):
    """
    Asynchronous adapter for querying ALDI circulars & promotions via Flipp API.
    Handles Aldi-specific conventions including 'Fresh Meat Special', produce pricing,
    category inferences (e.g. Aldi Finds, Fresh Meat, Produce, Pantry), and clean fallbacks.
    """

    DEFAULT_MERCHANT: str = "ALDI"
    MERCHANT_SEARCH_TERMS: tuple[str, ...] = ("aldi", "aldi finds", "aldi us")

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        super().__init__(client=client, timeout=timeout, merchant_name=self.DEFAULT_MERCHANT)

    def is_merchant_match(
        self, flyer: dict[str, Any], merchant_name: str = DEFAULT_MERCHANT
    ) -> bool:
        """
        Matches flyers belonging to Aldi / ALDI.
        """
        if not flyer:
            return False

        name_candidate = str(
            flyer.get("merchant")
            or flyer.get("merchant_name")
            or flyer.get("name")
            or flyer.get("flyer_run_id")
            or ""
        ).lower()

        target = merchant_name.strip().lower() if merchant_name else "aldi"
        if target in name_candidate:
            return True

        return any(term in name_candidate for term in self.MERCHANT_SEARCH_TERMS)

    async def fetch_flyers_by_postal_code(
        self, postal_code: str, merchant_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Fetch active flyers for postal code with ALDI as default merchant.
        """
        target_merchant = merchant_name if merchant_name is not None else self.DEFAULT_MERCHANT
        return await super().fetch_flyers_by_postal_code(
            postal_code=postal_code, merchant_name=target_merchant
        )

    def _determine_pricing_unit(self, item: dict[str, Any]) -> str:
        """
        Determines pricing unit ('lb' or 'each') taking into account Aldi's
        'Fresh Meat Special' and produce pricing conventions.
        """
        text_sources = [
            str(item.get("sale_story") or ""),
            str(item.get("pre_price_text") or ""),
            str(item.get("post_price_text") or ""),
            str(item.get("name") or ""),
            str(item.get("title") or ""),
            str(item.get("description") or ""),
            str(item.get("category") or ""),
        ]
        combined = " ".join(text_sources).lower()

        # Check explicit per-pound patterns: "per lb", "/lb", "/ lb", "per pound", "$X.XX/lb", "$X.XX lb"
        if re.search(
            r"(?:per\s+lb|per\s+pound|\/\s*lb|\b\$\s*\d+(?:\.\d+)?\s*\/\s*lb|\b\$\s*\d+(?:\.\d+)?\s*per\s*lb|\b\$\s*\d+(?:\.\d+)?\s*lb\b)",
            combined,
        ):
            return "lb"

        if "per lb" in combined or "/lb" in combined or "/ lb" in combined or "per pound" in combined:
            return "lb"

        # Check explicit per-each / per-item / package indicators
        if re.search(
            r"\b(?:each|ea\b|per\s+each|\/\s*ea|per\s+pkg|per\s+pack|per\s+bag|per\s+bunch|per\s+container)\b",
            combined,
        ):
            return "each"

        # Fresh Meat Special fallback when price is per pound
        if "fresh meat special" in combined:
            if any(k in combined for k in ["per lb", "/lb", "pound", "lb"]):
                return "lb"

        return "each"

    def _extract_sale_price(self, item: dict[str, Any]) -> Optional[float]:
        """
        Extracts sale price handling standard numbers, multi-buys, cents notations (e.g. 79¢),
        and Aldi text representations.
        """
        current_price = item.get("current_price") if item.get("current_price") is not None else item.get("price")
        if current_price is not None:
            if isinstance(current_price, (int, float)) and current_price > 0:
                return float(current_price)
            if isinstance(current_price, str):
                cleaned = current_price.strip()
                cents_match = re.match(r"^(\d+)\s*(?:¢|c|cents?)$", cleaned, re.IGNORECASE)
                if cents_match:
                    return round(float(cents_match.group(1)) / 100.0, 2)
                try:
                    val = float(re.sub(r"[^\d.]", "", cleaned))
                    if val > 0:
                        return val
                except ValueError:
                    pass

        # Text parsing fallback from sale_story, pre_price_text, post_price_text, description, name
        text_sources = [
            item.get("sale_story") or "",
            item.get("pre_price_text") or "",
            item.get("post_price_text") or "",
            item.get("description") or "",
            item.get("name") or "",
        ]
        combined = " ".join(filter(None, text_sources))

        # Check multi-buy pattern: e.g. "4 for $3.00", "2 for 5", "2/$5.00"
        multi_match = re.search(
            r"(\d+)\s*(?:for|\/)\s*\$?\s*(\d+(?:\.\d+)?)",
            combined,
            re.IGNORECASE,
        )
        if multi_match:
            try:
                qty = float(multi_match.group(1))
                total = float(multi_match.group(2))
                if qty > 0:
                    return round(total / qty, 2)
            except (ValueError, ZeroDivisionError):
                pass

        # Check dollar pattern: e.g. "$1.99"
        dollar_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", combined)
        if dollar_match:
            try:
                return float(dollar_match.group(1))
            except ValueError:
                pass

        # Check cents pattern: e.g. "89¢", "79 c", "99 cents"
        cents_match = re.search(r"\b(\d{1,2})\s*(?:¢|c|cents?)\b", combined, re.IGNORECASE)
        if cents_match:
            try:
                return round(float(cents_match.group(1)) / 100.0, 2)
            except ValueError:
                pass

        # Check raw decimal pattern: e.g. "1.99"
        decimal_match = re.search(r"\b(\d+\.\d{2})\b", combined)
        if decimal_match:
            try:
                return float(decimal_match.group(1))
            except ValueError:
                pass

        return None

    def _extract_regular_price(self, item: dict[str, Any]) -> Optional[float]:
        """
        Aldi circulars typically omit regular prices (everyday low pricing model).
        Returns float if present and valid, otherwise cleanly falls back to None.
        """
        orig_raw = item.get("original_price") or item.get("regular_price") or item.get("was_price")
        if orig_raw is not None:
            try:
                cleaned = re.sub(r"[^\d.]", "", str(orig_raw))
                if cleaned:
                    val = float(cleaned)
                    if val > 0:
                        return val
            except (ValueError, TypeError):
                return None
        return None

    def _extract_category(
        self, item: dict[str, Any], flyer_context: Optional[dict[str, Any]] = None
    ) -> str:
        """
        Parses category hints from item descriptions, sale stories, flyer sections,
        or item categories (e.g., 'Fresh Meat', 'Produce', 'Pantry', 'Aldi Finds').
        """
        raw_category = str(item.get("category") or item.get("item_category") or "").strip()
        section = str(
            item.get("section")
            or item.get("flyer_section")
            or (flyer_context.get("name") if flyer_context else "")
            or ""
        ).strip()
        name = str(item.get("name") or item.get("title") or item.get("item_name") or "").strip()
        description = str(item.get("description") or "").strip()
        sale_story = str(item.get("sale_story") or "").strip()
        pre_post = str(item.get("pre_price_text") or "") + " " + str(item.get("post_price_text") or "")

        combined_text = f"{raw_category} {section} {name} {description} {sale_story} {pre_post}".lower()

        # 1. Aldi Finds / Weekly Finds / Special Buys
        if any(
            term in combined_text
            for term in [
                "aldi find",
                "aldi finds",
                "weekly find",
                "weekly finds",
                "special buy",
                "limited time",
                "while supplies last",
            ]
        ):
            return "Aldi Finds"

        # 2. Fresh Meat / Seafood / Poultry / Beef / Pork
        if any(
            term in combined_text
            for term in [
                "fresh meat special",
                "fresh meat",
                "meat special",
                "beef",
                "chicken",
                "pork",
                "turkey",
                "steak",
                "ground beef",
                "ribeye",
                "sirloin",
                "chuck roast",
                "roast",
                "pork chop",
                "pork chops",
                "pork loin",
                "tenderloin",
                "ribs",
                "bratwurst",
                "sausage",
                "bacon",
                "salmon",
                "tilapia",
                "shrimp",
                "cod",
                "flounder",
                "tuna",
                "poultry",
                "lamb",
                "meat & seafood",
                "fresh seafood",
                "drumsticks",
                "chicken breast",
                "chicken thighs",
                "wings",
            ]
        ):
            return "Fresh Meat"

        # 3. Produce
        if any(
            term in combined_text
            for term in [
                "produce",
                "fresh fruit",
                "fresh vegetable",
                "apple",
                "apples",
                "banana",
                "bananas",
                "avocado",
                "avocados",
                "berry",
                "berries",
                "strawberry",
                "strawberries",
                "blueberry",
                "blueberries",
                "raspberry",
                "raspberries",
                "blackberry",
                "blackberries",
                "grape",
                "grapes",
                "orange",
                "oranges",
                "lemon",
                "lemons",
                "lime",
                "limes",
                "potato",
                "potatoes",
                "tomato",
                "tomatoes",
                "onion",
                "onions",
                "salad",
                "spinach",
                "lettuce",
                "kale",
                "carrot",
                "carrots",
                "pepper",
                "peppers",
                "bell pepper",
                "mushroom",
                "mushrooms",
                "asparagus",
                "cucumber",
                "cucumbers",
                "zucchini",
                "squash",
                "broccoli",
                "cauliflower",
                "celery",
                "watermelon",
                "cantaloupe",
                "honeydew",
                "pineapple",
                "mango",
                "mandarin",
                "clementines",
            ]
        ):
            return "Produce"

        # 4. Pantry
        if any(
            term in combined_text
            for term in [
                "pantry",
                "pasta",
                "sauce",
                "marinara",
                "rice",
                "olive oil",
                "vegetable oil",
                "canola oil",
                "canned",
                "beans",
                "broth",
                "soup",
                "cereal",
                "oats",
                "oatmeal",
                "flour",
                "sugar",
                "spice",
                "spices",
                "seasoning",
                "condiment",
                "ketchup",
                "mustard",
                "mayo",
                "mayonnaise",
                "salad dressing",
                "vinegar",
                "peanut butter",
                "jelly",
                "jam",
                "honey",
                "syrup",
                "baking",
                "tuna can",
                "diced tomatoes",
            ]
        ):
            return "Pantry"

        # 5. Dairy & Eggs
        if any(
            term in combined_text
            for term in [
                "dairy",
                "milk",
                "cheese",
                "cheddar",
                "mozzarella",
                "butter",
                "yogurt",
                "eggs",
                "egg",
                "sour cream",
                "cottage cheese",
                "heavy cream",
                "creamer",
            ]
        ):
            return "Dairy & Eggs"

        # 6. Frozen
        if any(
            term in combined_text
            for term in [
                "frozen",
                "ice cream",
                "pizza",
                "frozen veggies",
                "frozen fruit",
                "gelato",
                "popsicles",
            ]
        ):
            return "Frozen"

        # 7. Bakery
        if any(
            term in combined_text
            for term in [
                "bakery",
                "bread",
                "bagel",
                "bagels",
                "buns",
                "rolls",
                "croissant",
                "croissants",
                "muffins",
                "tortilla",
                "tortillas",
                "brioche",
            ]
        ):
            return "Bakery"

        # 8. Beverages
        if any(
            term in combined_text
            for term in [
                "beverage",
                "beverages",
                "coffee",
                "tea",
                "juice",
                "sparkling water",
                "soda",
                "lemonade",
                "drink",
            ]
        ):
            return "Beverages"

        # 9. Snacks
        if any(
            term in combined_text
            for term in [
                "snack",
                "snacks",
                "chips",
                "tortilla chips",
                "potato chips",
                "crackers",
                "cookies",
                "nuts",
                "almonds",
                "cashews",
                "peanuts",
                "pretzels",
                "popcorn",
                "chocolate",
                "candy",
            ]
        ):
            return "Snacks"

        # Fallback to Flipp raw category if available, otherwise "Grocery"
        if raw_category and raw_category.lower() not in ["", "none", "null", "grocery"]:
            return raw_category

        return "Grocery"

    async def get_normalized_deals(
        self,
        postal_code: str,
        store_id: str,
        merchant_name: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[datetime, datetime, list[NormalizedDealItem]]:
        """
        Resolves the active weekly circular for Aldi in the given postal code
        and returns normalized deals.

        Includes proper logging and exception handling when no active circulars exist.
        """
        target_merchant = merchant_name if merchant_name is not None else self.DEFAULT_MERCHANT
        now = datetime.now(timezone.utc)
        default_valid_from = now
        default_valid_to = now + timedelta(days=7)

        try:
            flyers = await self.fetch_flyers_by_postal_code(
                postal_code=postal_code, merchant_name=target_merchant
            )
        except Exception as exc:
            logger.error(
                "Error fetching ALDI circulars for postal_code=%s (store_id=%s): %s",
                postal_code,
                store_id,
                exc,
                exc_info=True,
            )
            return default_valid_from, default_valid_to, []

        if not flyers:
            logger.warning(
                "No active ALDI circular found for postal_code=%s (store_id=%s)",
                postal_code,
                store_id,
            )
            return default_valid_from, default_valid_to, []

        flyers = self.prioritize_flyers(flyers)
        flyer = flyers[0]

        valid_from = self._parse_datetime(
            flyer.get("valid_from") or flyer.get("available_from"),
            default=default_valid_from,
        )
        valid_to = self._parse_datetime(
            flyer.get("valid_to") or flyer.get("available_to"),
            default=default_valid_to,
        )

        flyer_id = flyer.get("id") or flyer.get("flyer_id")
        if not flyer_id:
            logger.warning(
                "ALDI flyer found without valid ID for postal_code=%s (store_id=%s)",
                postal_code,
                store_id,
            )
            return valid_from, valid_to, []

        try:
            items = await self.fetch_promotions_for_flyer(int(flyer_id))
        except Exception as exc:
            logger.error(
                "Error fetching ALDI promotions for flyer_id=%s (store_id=%s): %s",
                flyer_id,
                store_id,
                exc,
                exc_info=True,
            )
            return valid_from, valid_to, []

        normalized_deals: list[NormalizedDealItem] = []
        for item in items:
            deal_item = self._parse_deal_item(
                item,
                valid_from=valid_from,
                valid_to=valid_to,
                flyer_context=flyer,
            )
            if deal_item is not None:
                normalized_deals.append(deal_item)

        logger.info(
            "Successfully normalized %d ALDI deals for store %s from flyer %s in postal code %s",
            len(normalized_deals),
            store_id,
            flyer_id,
            postal_code,
        )
        return valid_from, valid_to, normalized_deals
