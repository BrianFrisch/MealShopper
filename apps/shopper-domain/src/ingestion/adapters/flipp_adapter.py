from datetime import datetime, timezone, timedelta
import logging
import re
from typing import Any, Optional
import httpx

try:
    from src.ingestion.adapters.base import BaseDealAdapter
except ImportError:
    from .base import BaseDealAdapter

try:
    from src.ingestion.circuit_breaker import UpstreamCircuitBreaker, CircuitBreakerOpenException
except ImportError:
    from ..circuit_breaker import UpstreamCircuitBreaker, CircuitBreakerOpenException

from src.services.grocery_chain_service import GroceryChainService

logger = logging.getLogger(__name__)

FLIPP_BASE_URL = "https://backflipp.wishabi.com/flipp"
DEFAULT_TIMEOUT = 10.0

# Shared module breaker for wishabi/flipp backend endpoints
flipp_circuit_breaker = UpstreamCircuitBreaker(
    name="wishabi-flipp-api",
    failure_threshold=3,
    recovery_timeout_seconds=30.0,
)


class FlippAdapter(BaseDealAdapter):
    """
    Asynchronous adapter for querying the Flipp circulars & promotions API.
    Inherits from BaseDealAdapter and implements Template Method hooks.
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

        async def _do_request() -> list[dict[str, Any]]:
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

        try:
            return await flipp_circuit_breaker.call(_do_request)
        except CircuitBreakerOpenException as cbe:
            logger.warning("Flipp breaker active: %s", cbe)
            return []
        except Exception as exc:
            logger.error("Error fetching flyers for postal_code=%s: %s", postal_code, exc)
            return []

    async def fetch_promotions_for_flyer(self, flyer_id: Any) -> list[dict[str, Any]]:
        """
        Fetch promotional items array for a specific flyer ID.
        """
        url = f"{FLIPP_BASE_URL}/flyers/{flyer_id}/items"

        async def _do_request() -> list[dict[str, Any]]:
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

        try:
            return await flipp_circuit_breaker.call(_do_request)
        except CircuitBreakerOpenException as cbe:
            logger.warning("Flipp breaker active: %s", cbe)
            return []
        except Exception as exc:
            logger.error("Error fetching promos for flyer_id=%s: %s", flyer_id, exc)
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

        now_utc = (
            now
            if (now is not None and now.tzinfo is not None)
            else (now.replace(tzinfo=timezone.utc) if now is not None else datetime.now(timezone.utc))
        )
        active_flyers: list[tuple[dict[str, Any], bool, datetime, datetime]] = []
        upcoming_flyers: list[tuple[dict[str, Any], bool, datetime, datetime]] = []

        for flyer in flyers:
            v_from = self._parse_datetime(
                flyer.get("valid_from") or flyer.get("available_from"),
                default=now_utc
            )
            v_to = self._parse_datetime(
                flyer.get("valid_to") or flyer.get("available_to"),
                default=now_utc + timedelta(days=7)
            )

            is_weekly = bool(
                re.search(r"\b(?:weekly|ad|circular)\b", str(flyer.get("name") or flyer.get("flyer_run_id") or ""), re.I)
            )

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

    def _extract_sale_price(self, item: dict[str, Any]) -> Optional[float]:
        """Extracts sale price from current_price, price, or text descriptions."""
        current_price = item.get("current_price") if item.get("current_price") is not None else item.get("price")
        if current_price is not None:
            if isinstance(current_price, (int, float)) and current_price > 0:
                return float(current_price)
            if isinstance(current_price, str):
                cleaned = current_price.strip()
                cents_match = re.match(r"^(\d+)\s*(?:¢|c|cents?)$", cleaned, re.IGNORECASE)
                if cents_match:
                    try:
                        return round(float(cents_match.group(1)) / 100.0, 2)
                    except ValueError:
                        pass
                simple_match = re.match(r"^\s*\$?\s*(\d+(?:\.\d+)?)\s*$", cleaned)
                if simple_match:
                    try:
                        val = float(simple_match.group(1))
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

        # Check cents pattern: e.g. "49¢", "79c"
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

        if any(u in text for u in ["per lb", "/lb", "/ lb", "per pound", "lbs", "pound"]):
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
        orig_raw = item.get("original_price") if item.get("original_price") is not None else item.get("regular_price")
        if orig_raw is not None:
            if isinstance(orig_raw, (int, float)) and orig_raw > 0:
                return float(orig_raw)
            if isinstance(orig_raw, str):
                orig_match = re.search(r"\$?\s*(\d+(?:\.\d+)?)", orig_raw)
                if orig_match:
                    try:
                        val = float(orig_match.group(1))
                        if val > 0:
                            return val
                    except ValueError:
                        return None
        return None

    def _extract_category(
        self, item: dict[str, Any], flyer_context: Optional[dict[str, Any]] = None
    ) -> str:
        """Extracts or infers item category."""
        cat = item.get("category") or item.get("item_category") or "Grocery"
        return str(cat).strip() or "Grocery"

    # --- BaseDealAdapter Template Method Hooks ---

    async def fetch_flyer_metadata(
        self,
        postal_code: str,
        chain_id: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[Optional[str], datetime, datetime]:
        """
        Calls Flipp /flyers endpoint, filters array by merchant_name, and returns matching (flyer_id, valid_from, valid_to).
        """

        target_chain_id = chain_id if chain_id is not None else self.default_merchant 
        chain_obj = await GroceryChainService().get_chain_metadata(target_chain_id)  # Ensure chain is loaded in DB for future lookups
        target_merchant = str(chain_obj.get("display_name")).strip().lower()

        # target_merchant = chain_id if chain_id is not None else self.default_merchant
        now = datetime.now(timezone.utc)
        default_valid_from = now
        default_valid_to = now + timedelta(days=7)

        flyers = await self.fetch_flyers_by_postal_code(postal_code, merchant_name=target_merchant)
        if not flyers:
            logger.warning(
                "No active flyer found for merchant='%s' in postal_code=%s",
                target_merchant,
                postal_code,
            )
            return None, default_valid_from, default_valid_to

        flyer = self.select_active_flyer(flyers, now=now)
        if not flyer:
            logger.warning("No suitable flyer found for postal_code=%s merchant=%s", postal_code, target_merchant)
            return None, default_valid_from, default_valid_to

        valid_from = self._parse_datetime(
            flyer.get("valid_from") or flyer.get("available_from"),
            default=default_valid_from,
        )
        valid_to = self._parse_datetime(
            flyer.get("valid_to") or flyer.get("available_to"),
            default=default_valid_to,
        )

        flyer_id = flyer.get("id") or flyer.get("flyer_id")
        return (str(flyer_id) if flyer_id is not None else None), valid_from, valid_to

    async def fetch_raw_items(self, flyer_id: Any) -> list[dict[str, Any]]:
        """
        Calls Flipp /items endpoint for the given flyer ID.
        """
        return await self.fetch_promotions_for_flyer(flyer_id)

    def extract_product_name(self, item: dict[str, Any]) -> str:
        """
        Extracts raw product name from Wishabi/Flipp item structure.
        """
        return self._extract_product_name(item)

    def extract_pricing(
        self, item: dict[str, Any]
    ) -> tuple[Optional[float], Optional[float], str]:
        """
        Extracts (sale_price, original_price, unit) using Wishabi/Flipp JSON paths.
        """
        sale_price = self._extract_sale_price(item)
        original_price = self._extract_regular_price(item)
        unit = self._determine_pricing_unit(item)
        return sale_price, original_price, unit

    def extract_raw_category(self, item: dict[str, Any]) -> str:
        """
        Extracts raw category string from Wishabi/Flipp item structure.
        """
        return self._extract_category(item)
