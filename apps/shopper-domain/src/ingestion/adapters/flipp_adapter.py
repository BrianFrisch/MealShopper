from datetime import datetime, timezone, timedelta
import logging
import re
from typing import Any, Optional
import httpx

try:
    from src.ingestion.models import NormalizedDealItem, clean_product_name
except ImportError:
    from ..models import NormalizedDealItem, clean_product_name

logger = logging.getLogger(__name__)

FLIPP_BASE_URL = "https://backflipp.wishabi.com/flipp"
DEFAULT_TIMEOUT = 10.0


class FlippAdapter:
    """
    Asynchronous adapter for querying the Flipp circulars & promotions API.
    """

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._external_client = client is not None
        self._timeout = httpx.Timeout(timeout)
        self._client = client

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

    async def fetch_flyers_by_postal_code(
        self, postal_code: str, merchant_name: str = "Ralphs"
    ) -> list[dict[str, Any]]:
        """
        Fetch active flyers for a given postal code and filter by target merchant.
        """
        url = f"{FLIPP_BASE_URL}/flyers"
        params = {"postal_code": postal_code}

        try:
            client = await self._get_client()
            logger.info("Fetching flyers for postal_code=%s merchant=%s", postal_code, merchant_name)
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            merchant_lower = merchant_name.strip().lower()
            matched_flyers: list[dict[str, Any]] = []

            raw_flyers: list[Any] = []
            if isinstance(data, list):
                raw_flyers = data
            elif isinstance(data, dict):
                raw = data.get("flyers")
                if isinstance(raw, list):
                    raw_flyers = raw

            for item in raw_flyers:
                if isinstance(item, dict):
                    flyer_obj: dict[str, Any] = item
                    name_candidate = flyer_obj.get("merchant") or flyer_obj.get("merchant_name") or flyer_obj.get("name") or flyer_obj.get("flyer_run_id") or ""
                    if merchant_lower in str(name_candidate).lower():
                        matched_flyers.append(flyer_obj)

            logger.info(
                "Found %d flyers matching merchant '%s' in postal code %s",
                len(matched_flyers),
                merchant_name,
                postal_code,
            )
            return matched_flyers

            logger.info(
                "Found %d flyers matching merchant '%s' in postal code %s",
                len(matched_flyers),
                merchant_name,
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

    async def get_normalized_deals(
        self,
        postal_code: str,
        store_id: str,
        merchant_name: str = "Ralphs",
    ) -> tuple[datetime, datetime, list[NormalizedDealItem]]:
        """
        Resolves the active weekly circular for the merchant and returns normalized deals.
        """
        now = datetime.now(timezone.utc)
        default_valid_from = now
        default_valid_to = now + timedelta(days=7)

        flyers = await self.fetch_flyers_by_postal_code(postal_code, merchant_name=merchant_name)
        if not flyers:
            logger.warning(
                "No active flyer found for merchant='%s' in postal_code=%s (store_id=%s)",
                merchant_name,
                postal_code,
                store_id,
            )
            return default_valid_from, default_valid_to, []

        # Prioritize primary weekly circulars if available
        def flyer_priority(f: dict[str, Any]) -> int:
            name = str(f.get("name") or "").lower()
            if re.search(r"\b(?:weekly|ad|circular)\b", name, re.IGNORECASE):
                return 0
            return 1

        flyers.sort(key=flyer_priority)

        # Use the first active flyer for the circular
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
            logger.warning("Flyer found without valid ID for store_id=%s", store_id)
            return valid_from, valid_to, []

        items = await self.fetch_promotions_for_flyer(int(flyer_id))
        normalized_deals: list[NormalizedDealItem] = []

        for item in items:
            product_name = str(
                item.get("name")
                or item.get("title")
                or item.get("item_name")
                or ""
            ).strip()

            if not product_name:
                continue

            sale_price = self._extract_sale_price(item)
            if sale_price is None or sale_price < 0:
                continue

            # Regular / Original price if present
            regular_price: Optional[float] = None
            orig_raw = item.get("original_price") or item.get("regular_price")
            if orig_raw is not None:
                try:
                    regular_price = float(re.sub(r"[^\d.]", "", str(orig_raw)))
                except ValueError:
                    regular_price = None

            pricing_unit = self._determine_pricing_unit(item)

            raw_promo = (
                item.get("sale_story")
                or item.get("pre_price_text")
                or item.get("post_price_text")
                or item.get("description")
                or f"${sale_price:.2f} {pricing_unit}"
            )

            category = str(item.get("category") or item.get("item_category") or "Grocery").strip()

            deal_item = NormalizedDealItem(
                product_name=product_name,
                clean_name=clean_product_name(product_name),
                category=category or "Grocery",
                sale_price=sale_price,
                regular_price=regular_price,
                pricing_unit=pricing_unit,
                raw_promotion_text=str(raw_promo),
                valid_from=valid_from,
                valid_to=valid_to,
            )
            normalized_deals.append(deal_item)

        logger.info(
            "Successfully normalized %d deals for store %s from flyer %s",
            len(normalized_deals),
            store_id,
            flyer_id,
        )
        return valid_from, valid_to, normalized_deals
