from datetime import datetime, timezone, timedelta
import logging
import re
from typing import Any, Optional
import httpx

try:
    from src.ingestion.models import NormalizedDealItem, clean_product_name
    from src.ingestion.adapters.base import BaseDealAdapter
except ImportError:
    from ..models import NormalizedDealItem, clean_product_name
    from .base import BaseDealAdapter

logger = logging.getLogger(__name__)

FLIPP_BASE_URL = "https://backflipp.wishabi.com/flipp"
DEFAULT_TIMEOUT = 10.0


def compute_value_score(deal_price: float, original_price: Optional[float] = None) -> float:
    """
    Computes value score on a scale of 1 to 10.
    Defaults to 8.0, or calculates higher if a valid original_price shows >20% savings.
    """
    if original_price is not None and original_price > deal_price > 0:
        savings = (original_price - deal_price) / original_price
        if savings > 0.20:
            return round(min(8.0 + (savings - 0.20) * 5.0, 10.0), 1)
    return 8.0


def normalize_category_name(category_raw: str, item_name: str = "") -> str:
    """
    Maps raw or extracted category strings to one of the standardized categories:
    Produce, Dairy, Meat, Seafood, Bakery, Pantry.
    """
    raw_clean = (category_raw or "").strip()
    item_clean = (item_name or "").lower()
    cat_lower = raw_clean.lower()
    combined = f"{cat_lower} {item_clean}"

    # Handle combined "Meat & Seafood" category based on item name
    if "meat" in cat_lower and "seafood" in cat_lower:
        seafood_item_terms = [
            "seafood", "fish", "shrimp", "salmon", "tilapia", "tuna", "crab",
            "lobster", "cod", "flounder", "scallop", "trout", "halibut", "mahi"
        ]
        if any(k in item_clean for k in seafood_item_terms):
            return "Seafood"
        return "Meat"

    exact_map = {
        "produce": "Produce",
        "dairy": "Dairy",
        "meat": "Meat",
        "seafood": "Seafood",
        "bakery": "Bakery",
        "pantry": "Pantry",
    }
    if cat_lower in exact_map:
        return exact_map[cat_lower]

    if any(k in combined for k in ["seafood", "fish", "shrimp", "salmon", "tilapia", "tuna", "crab", "lobster", "cod", "flounder"]):
        return "Seafood"
    if any(k in combined for k in [
        "fresh meat", "meat", "poultry", "beef", "pork", "chicken", "turkey",
        "steak", "lamb", "ribs", "sausage", "bacon", "roast", "chop", "drumstick", "wing"
    ]):
        return "Meat"
    if any(k in combined for k in [
        "produce", "fruit", "vegetable", "greens", "apple", "banana", "avocado",
        "berry", "berries", "salad", "spinach", "lettuce", "tomato", "potato",
        "onion", "carrot", "pepper", "cucumber", "zucchini", "squash", "broccoli",
        "asparagus", "celery", "citrus", "orange", "lemon", "lime"
    ]):
        return "Produce"
    if any(k in combined for k in [
        "dairy & eggs", "dairy", "cheese", "milk", "egg", "yogurt", "butter",
        "cream", "cheddar", "mozzarella", "sour cream", "cottage cheese"
    ]):
        return "Dairy"
    if any(k in combined for k in [
        "bakery", "bread", "bagel", "pastry", "muffin", "croissant", "cake",
        "buns", "rolls", "brioche", "tortilla"
    ]):
        return "Bakery"

    return "Pantry"


class FlippAdapter(BaseDealAdapter):
    """
    Asynchronous adapter for querying the Flipp circulars & promotions API.
    """

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = DEFAULT_TIMEOUT,
        merchant_name: str = "Ralphs",
    ) -> None:
        self._external_client = client is not None
        self._timeout = httpx.Timeout(timeout)
        self._client = client
        self.default_merchant = merchant_name

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "User-Agent": "MealShopper/1.0",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Closes the underlying HTTP client if managed internally."""
        if not self._external_client and self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "FlippAdapter":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    def is_merchant_match(self, flyer: dict[str, Any], merchant_name: str) -> bool:
        """
        Checks whether a flyer dictionary matches the target merchant name or criteria.
        Subclasses can override this method to customize merchant matching.
        """
        if not flyer or not merchant_name:
            return False
        merchant_lower = merchant_name.strip().lower()
        name_candidate = (
            flyer.get("merchant")
            or flyer.get("merchant_name")
            or flyer.get("name")
            or flyer.get("flyer_run_id")
            or ""
        )
        return merchant_lower in str(name_candidate).lower()

    async def fetch_flyers_by_postal_code(
        self, postal_code: str, merchant_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Fetch active flyers for a given postal code and filter by target merchant.
        """
        target_merchant = merchant_name if merchant_name is not None else self.default_merchant
        url = f"{FLIPP_BASE_URL}/flyers"
        params = {"postal_code": postal_code}

        try:
            client = await self._get_client()
            logger.info("Fetching flyers for postal_code=%s merchant=%s", postal_code, target_merchant)
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            matched_flyers: list[dict[str, Any]] = []

            raw_flyers: list[dict[str, Any]] = []
            if isinstance(data, list):
                raw_flyers = [f for f in data if isinstance(f, dict)]
            elif isinstance(data, dict):
                raw = data.get("flyers")
                if isinstance(raw, list):
                    raw_flyers = [f for f in raw if isinstance(f, dict)]

            for flyer_obj in raw_flyers:
                if self.is_merchant_match(flyer_obj, target_merchant):
                    matched_flyers.append(flyer_obj)

            logger.info(
                "Found %d flyers matching merchant '%s' in postal code %s",
                len(matched_flyers),
                target_merchant,
                postal_code,
            )
            return matched_flyers

        except httpx.TimeoutException as exc:
            logger.error("Timeout fetching flyers for postal_code=%s: %s", postal_code, exc)
            return []
        except httpx.HTTPError as exc:
            logger.error("HTTP error fetching flyers for postal_code=%s: %s", postal_code, exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error fetching flyers for postal_code=%s: %s", postal_code, exc)
            return []

    async def fetch_promotions_for_flyer(self, flyer_id: int) -> list[dict[str, Any]]:
        """
        Fetch promotional items array for a specific flyer ID.
        """
        url = f"{FLIPP_BASE_URL}/flyers/{flyer_id}/items"

        try:
            client = await self._get_client()
            logger.info("Fetching promotions for flyer_id=%s", flyer_id)
            response = await client.get(url)
            if response.status_code == 404:
                # Fallback to flyer endpoint which contains items
                fallback_url = f"{FLIPP_BASE_URL}/flyers/{flyer_id}"
                response = await client.get(fallback_url)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                items_val = data.get("items")
                if isinstance(items_val, list):
                    return items_val
                promos_val = data.get("promotions")
                if isinstance(promos_val, list):
                    return promos_val

            return []

        except httpx.TimeoutException as exc:
            logger.error("Timeout fetching promotions for flyer_id=%s: %s", flyer_id, exc)
            return []
        except httpx.HTTPError as exc:
            logger.error("HTTP error fetching promotions for flyer_id=%s: %s", flyer_id, exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error fetching promotions for flyer_id=%s: %s", flyer_id, exc)
            return []

    def _parse_datetime(self, date_val: Any, default: datetime) -> datetime:
        """Parses ISO date string or returns default datetime."""
        if isinstance(date_val, datetime):
            return date_val if date_val.tzinfo else date_val.replace(tzinfo=timezone.utc)
        if isinstance(date_val, str):
            try:
                cleaned = date_val.replace("Z", "+00:00")
                dt = datetime.fromisoformat(cleaned)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass
        return default

    def _extract_sale_price(self, item: dict[str, Any]) -> Optional[float]:
        """Extracts sale price from current_price, price, or text descriptions."""
        current_price = item.get("current_price") if item.get("current_price") is not None else item.get("price")
        if current_price is not None:
            if isinstance(current_price, (int, float)) and current_price > 0:
                return float(current_price)
            if isinstance(current_price, str):
                try:
                    val = float(re.sub(r"[^\d.]", "", current_price))
                    if val > 0:
                        return val
                except ValueError:
                    pass

        # Fallback to text parsing from sale_story, description, pre_price_text, post_price_text
        text_sources = [
            item.get("sale_story") or "",
            item.get("pre_price_text") or "",
            item.get("post_price_text") or "",
            item.get("description") or "",
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

        # Check raw decimal pattern: e.g. "1.99"
        decimal_match = re.search(r"\b(\d+\.\d{2})\b", combined)
        if decimal_match:
            try:
                return float(decimal_match.group(1))
            except ValueError:
                pass

        return None

    def _determine_pricing_unit(self, item: dict[str, Any]) -> str:
        """Determines if pricing unit is 'lb' or 'each'."""
        text = " ".join(
            [
                str(item.get("sale_story") or ""),
                str(item.get("pre_price_text") or ""),
                str(item.get("post_price_text") or ""),
                str(item.get("name") or ""),
                str(item.get("description") or ""),
            ]
        ).lower()

        if "per lb" in text or "/lb" in text or "/ lb" in text or "per pound" in text:
            return "lb"
        return "each"

    def _extract_product_name(self, item: dict[str, Any]) -> str:
        """Extracts raw product name from item dictionary."""
        return str(
            item.get("name")
            or item.get("title")
            or item.get("item_name")
            or ""
        ).strip()

    def _extract_regular_price(self, item: dict[str, Any]) -> Optional[float]:
        """Extracts regular/original price from item dictionary if present."""
        orig_raw = item.get("original_price") or item.get("regular_price")
        if orig_raw is not None:
            try:
                val = float(re.sub(r"[^\d.]", "", str(orig_raw)))
                if val > 0:
                    return val
            except ValueError:
                return None
        return None

    def _extract_raw_promotion(
        self, item: dict[str, Any], sale_price: float, pricing_unit: str
    ) -> str:
        """Extracts promotion text or generates fallback from sale price and unit."""
        return str(
            item.get("sale_story")
            or item.get("pre_price_text")
            or item.get("post_price_text")
            or item.get("description")
            or f"${sale_price:.2f} {pricing_unit}"
        )

    def _extract_category(
        self, item: dict[str, Any], flyer_context: Optional[dict[str, Any]] = None
    ) -> str:
        """Extracts or infers item category."""
        cat = item.get("category") or item.get("item_category") or "Grocery"
        return str(cat).strip() or "Grocery"

    def _parse_deal_item(
        self,
        item: dict[str, Any],
        valid_from: datetime,
        valid_to: datetime,
        flyer_context: Optional[dict[str, Any]] = None,
        store_id: str = "store-1",
        store_name: Optional[str] = None,
    ) -> Optional[NormalizedDealItem]:
        """Parses a raw flyer item dictionary into a NormalizedDealItem."""
        product_name = self._extract_product_name(item)
        if not product_name:
            return None

        sale_price = self._extract_sale_price(item)
        if sale_price is None or sale_price < 0:
            return None

        regular_price = self._extract_regular_price(item)
        pricing_unit = self._determine_pricing_unit(item)
        raw_promo = self._extract_raw_promotion(item, sale_price, pricing_unit)
        raw_category = self._extract_category(item, flyer_context=flyer_context)

        clean_name = clean_product_name(product_name)
        normalized_cat = normalize_category_name(raw_category, product_name)

        item_id = item.get("id") or item.get("item_id") or item.get("flyer_item_id")
        if item_id is not None:
            deal_id = f"{store_id}_{item_id}"
        else:
            deal_id = f"{store_id}_{abs(hash(clean_name))}"

        effective_store_name = (
            store_name
            or (flyer_context.get("merchant") if flyer_context else None)
            or (flyer_context.get("merchant_name") if flyer_context else None)
            or self.default_merchant
        )

        value_score = compute_value_score(sale_price, regular_price)

        return NormalizedDealItem(
            deal_id=deal_id,
            store_id=store_id,
            store_name=effective_store_name,
            item_name=product_name,
            clean_name=clean_name,
            normalized_category=normalized_cat,
            deal_price=sale_price,
            original_price=regular_price,
            currency="USD",
            unit=pricing_unit,
            value_score=value_score,
            raw_promotion_text=raw_promo,
            valid_from=valid_from,
            valid_to=valid_to,
        )

    def prioritize_flyers(self, flyers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Prioritizes primary weekly circulars if available."""
        def flyer_priority(f: dict[str, Any]) -> int:
            name = str(f.get("name") or "").lower()
            if re.search(r"\b(?:weekly|ad|circular)\b", name, re.IGNORECASE):
                return 0
            return 1

        return sorted(flyers, key=flyer_priority)

    def select_active_flyer(
        self,
        flyers: list[dict[str, Any]],
        now: Optional[datetime] = None
    ) -> Optional[dict[str, Any]]:
        """
        Selects the best flyer:
        1. Prioritizes circulars currently valid (valid_from <= now <= valid_to).
        2. If multiple are active, prefers weekly circulars with the latest start date.
        3. If no circular is currently active, falls back to the closest upcoming circular.
        """
        if not flyers:
            return None

        now_utc = now or datetime.now(timezone.utc)
        active_flyers = []
        upcoming_flyers = []

        for flyer in flyers:
            v_from = self._parse_datetime(
                flyer.get("valid_from") or flyer.get("available_from"),
                default=now_utc
            )
            v_to = self._parse_datetime(
                flyer.get("valid_to") or flyer.get("available_to"),
                default=now_utc + timedelta(days=7)
            )

            is_weekly = bool(re.search(r"\b(?:weekly|ad|circular)\b", str(flyer.get("name") or ""), re.I))

            if v_from <= now_utc <= v_to:
                active_flyers.append((flyer, is_weekly, v_from, v_to))
            elif v_from > now_utc:
                upcoming_flyers.append((flyer, is_weekly, v_from, v_to))

        # 1. Prefer currently active circulars
        if active_flyers:
            # Sort weekly circulars first, then newest valid_from
            active_flyers.sort(key=lambda x: (1 if x[1] else 0, x[2]), reverse=True)
            return active_flyers[0][0]

        # 2. Fall back to closest upcoming circular
        if upcoming_flyers:
            upcoming_flyers.sort(key=lambda x: (1 if x[1] else 0, -x[2].timestamp()), reverse=True)
            return upcoming_flyers[0][0]

        return flyers[0]

    async def get_normalized_deals(
        self,
        postal_code: str,
        store_id: str,
        merchant_name: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[datetime, datetime, list[NormalizedDealItem]]:
        """
        Resolves the active weekly circular for the merchant and returns normalized deals.
        """
        target_merchant = merchant_name if merchant_name is not None else self.default_merchant
        now = datetime.now(timezone.utc)
        default_valid_from = now
        default_valid_to = now + timedelta(days=7)

        flyers = await self.fetch_flyers_by_postal_code(postal_code, merchant_name=target_merchant)
        if not flyers:
            logger.warning(
                "No active flyer found for merchant='%s' in postal_code=%s (store_id=%s)",
                target_merchant,
                postal_code,
                store_id,
            )
            return default_valid_from, default_valid_to, []

        flyer = self.select_active_flyer(flyers, now=now)
        if not flyer:
            logger.warning("No suitable flyer found for store_id=%s", store_id)
            return default_valid_from, default_valid_to, []
        
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
            logger.warning("Flyer found without valid ID for store_id=%s", store_id)
            return valid_from, valid_to, []

        items = await self.fetch_promotions_for_flyer(int(flyer_id))
        normalized_deals: list[NormalizedDealItem] = []

        for item in items:
            deal_item = self._parse_deal_item(
                item,
                valid_from=valid_from,
                valid_to=valid_to,
                flyer_context=flyer,
                store_id=store_id,
                store_name=target_merchant,
            )
            if deal_item is not None:
                normalized_deals.append(deal_item)

        logger.info(
            "Successfully normalized %d deals for store %s from flyer %s",
            len(normalized_deals),
            store_id,
            flyer_id,
        )
        return valid_from, valid_to, normalized_deals
