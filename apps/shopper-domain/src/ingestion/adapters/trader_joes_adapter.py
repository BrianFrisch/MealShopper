import asyncio
from datetime import datetime, timezone, timedelta
import json
import logging
import re
from typing import Any, Optional
import httpx

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
except ImportError:
    CurlAsyncSession = None

try:
    from src.ingestion.adapters.base import BaseDealAdapter
except ImportError:
    from .base import BaseDealAdapter

try:
    from src.ingestion.circuit_breaker import UpstreamCircuitBreaker, CircuitBreakerOpenException
except ImportError:
    from ..circuit_breaker import UpstreamCircuitBreaker, CircuitBreakerOpenException

logger = logging.getLogger(__name__)

TRADER_JOES_GRAPHQL_URL = "https://www.traderjoes.com/api/graphql"
DEFAULT_TIMEOUT = 10.0
DEFAULT_STORE_CODE = "34"
DEFAULT_MERCHANT = "Trader Joe's"

DEFAULT_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.traderjoes.com",
    "Referer": "https://www.traderjoes.com/home/discover/fearless-flyer",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Shared circuit breaker for Trader Joe's upstream GraphQL endpoint
trader_joes_circuit_breaker = UpstreamCircuitBreaker(
    name="trader-joes-graphql-api",
    failure_threshold=3,
    recovery_timeout_seconds=30.0,
)

TRADER_JOES_CATEGORY_MAP: dict[str, str] = {
    **BaseDealAdapter.category_map,
    "fresh fruits & veggies": "Produce",
    "fruits & veggies": "Produce",
    "fruit & veggies": "Produce",
    "fruits and veggies": "Produce",
    "fresh produce": "Produce",
    "flowers & plants": "Pantry",
    "flowers and plants": "Pantry",
    "for the pantry": "Pantry",
    "from the freezer": "Pantry",
    "dips, sauces & dressings": "Pantry",
    "dips, sauces and dressings": "Pantry",
    "snacks & sweets": "Pantry",
    "snacks and sweets": "Pantry",
    "wine, beer & liquor": "Pantry",
    "everything else": "Pantry",
    "meat, seafood & plant-based": "Meat",
    "meat, seafood and plant-based": "Meat",
    "cheese": "Dairy",
    "soup, chili & meals": "Pantry",
}

# Dual-query fetching both What's New and Limited Time Fearless Flyer circular items
FEARLESS_FLYER_PROMO_QUERY = """
query FearlessFlyerProducts(
  $currentPage: Int
  $pageSize: Int
  $storeCode: String
  $availability: String = "1"
  $published: String = "1"
) {
  newProducts: products(
    filter: {
      store_code: { eq: $storeCode }
      published: { eq: $published }
      availability: { match: $availability }
      new_product: { match: "1" }
    }
    currentPage: $currentPage
    pageSize: $pageSize
  ) {
    items {
      sku
      item_title
      name
      retail_price
      sales_size
      sales_uom_code
      sales_uom_description
      fun_tags
      item_characteristics
      item_story_marketing
      item_story_qil
      new_product
      promotion
      product_label
      category_hierarchy {
        id
        name
        url_key
        level
      }
      primary_image
      primary_image_meta {
        url
        metadata
      }
      price_range {
        minimum_price {
          final_price {
            value
            currency
          }
          regular_price {
            value
            currency
          }
        }
      }
    }
    total_count
    page_info {
      current_page
      page_size
      total_pages
    }
  }
  limitedTime: products(
    filter: {
      store_code: { eq: $storeCode }
      published: { eq: $published }
      availability: { match: $availability }
      product_label: { match: "LIMITED TIME" }
    }
    currentPage: $currentPage
    pageSize: $pageSize
  ) {
    items {
      sku
      item_title
      name
      retail_price
      sales_size
      sales_uom_code
      sales_uom_description
      fun_tags
      item_characteristics
      item_story_marketing
      item_story_qil
      new_product
      promotion
      product_label
      category_hierarchy {
        id
        name
        url_key
        level
      }
      primary_image
      primary_image_meta {
        url
        metadata
      }
      price_range {
        minimum_price {
          final_price {
            value
            currency
          }
          regular_price {
            value
            currency
          }
        }
      }
    }
    total_count
    page_info {
      current_page
      page_size
      total_pages
    }
  }
}
"""

SEARCH_PRODUCTS_QUERY = """
query SearchProducts(
  $search: String
  $pageSize: Int
  $currentPage: Int
  $storeCode: String
  $availability: String = "1"
  $published: String = "1"
) {
  products(
    search: $search
    filter: {
      store_code: { eq: $storeCode }
      published: { eq: $published }
      availability: { match: $availability }
    }
    pageSize: $pageSize
    currentPage: $currentPage
  ) {
    items {
      sku
      item_title
      name
      retail_price
      sales_size
      sales_uom_code
      sales_uom_description
      fun_tags
      item_characteristics
      item_story_marketing
      item_story_qil
      new_product
      promotion
      product_label
      category_hierarchy {
        id
        name
        url_key
        level
      }
      primary_image
      primary_image_meta {
        url
        metadata
      }
      price_range {
        minimum_price {
          final_price {
            value
            currency
          }
          regular_price {
            value
            currency
          }
        }
      }
    }
    total_count
    page_info {
      current_page
      page_size
      total_pages
    }
  }
}
"""


class TraderJoesAdapter(BaseDealAdapter):
    """
    Asynchronous adapter for querying Trader Joe's Fearless Flyer circulars and promotions
    via the public Trader Joe's GraphQL API.
    Inherits from BaseDealAdapter and implements Template Method hooks.
    Uses browser TLS impersonation via curl_cffi when available to avoid Akamai 403 blocks.
    """

    category_map = TRADER_JOES_CATEGORY_MAP
    DEFAULT_MERCHANT: str = DEFAULT_MERCHANT
    GRAPHQL_URL: str = TRADER_JOES_GRAPHQL_URL

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = DEFAULT_TIMEOUT,
        store_code: str = DEFAULT_STORE_CODE,
        merchant_name: str = DEFAULT_MERCHANT,
        gemini_client: Optional[Any] = None,
        graphql_url: str = TRADER_JOES_GRAPHQL_URL,
        default_search: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        max_pages: int = 5,
        impersonate: str = "chrome120",
    ) -> None:
        super().__init__(gemini_client=gemini_client)
        self._external_client = client is not None
        self._timeout = httpx.Timeout(timeout)
        self._timeout_seconds = timeout
        self._client = client
        self.store_code = store_code
        self.default_merchant = merchant_name
        self.graphql_url = graphql_url
        self.default_search = default_search
        self.max_pages = max_pages
        self.impersonate = impersonate
        self._curl_session: Optional[Any] = None
        self._headers = dict(DEFAULT_HEADERS)
        if headers:
            self._headers.update(headers)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers=self._headers,
            )
        return self._client

    async def _get_curl_session(self) -> Any:
        if CurlAsyncSession is None:
            return None
        if self._curl_session is None:
            self._curl_session = CurlAsyncSession(
                impersonate=self.impersonate,
                timeout=self._timeout_seconds,
                headers=self._headers,
            )
        return self._curl_session

    async def close(self) -> None:
        """Closes the underlying HTTP client or curl session if managed internally."""
        if not self._external_client and self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        if self._curl_session is not None:
            try:
                await self._curl_session.close()
            except Exception:
                pass
            self._curl_session = None

    async def __aenter__(self) -> "TraderJoesAdapter":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def execute_graphql(
        self,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        operation_name: str = "SearchProducts",
        strict: bool = False,
    ) -> dict[str, Any]:
        """
        Executes a GraphQL query against Trader Joe's GraphQL API endpoint
        with circuit breaker protection. Uses curl_cffi TLS impersonation if available
        to bypass Akamai edge protection, falling back to httpx if client was injected.
        """
        payload: dict[str, Any] = {
            "query": query,
            "operationName": operation_name,
        }
        if variables:
            payload["variables"] = variables

        async def _do_request() -> dict[str, Any]:
            logger.info("Executing Trader Joe's GraphQL query '%s'", operation_name)

            if self._client is not None:
                client = await self._get_client()
                response = await client.post(
                    self.graphql_url,
                    json=payload,
                    headers=self._headers,
                )
                response.raise_for_status()
                data = response.json()
            else:
                curl_session = await self._get_curl_session()
                if curl_session is not None:
                    res = await curl_session.post(
                        self.graphql_url,
                        json=payload,
                        headers=self._headers,
                    )
                    if res.status_code >= 400:
                        raise httpx.HTTPStatusError(
                            f"Client error '{res.status_code}' for url '{self.graphql_url}'",
                            request=httpx.Request("POST", self.graphql_url),
                            response=httpx.Response(res.status_code, text=res.text),
                        )
                    data = res.json()
                else:
                    client = await self._get_client()
                    response = await client.post(
                        self.graphql_url,
                        json=payload,
                        headers=self._headers,
                    )
                    response.raise_for_status()
                    data = response.json()

            if not isinstance(data, dict):
                logger.warning("Trader Joe's GraphQL returned unexpected non-dict payload: %s", type(data))
                if strict:
                    raise ValueError("Invalid GraphQL response")
                return {}
            if "errors" in data and not data.get("data"):
                logger.error("Trader Joe's GraphQL returned errors: %s", data["errors"])
                if strict:
                    raise ValueError("GraphQL request failed")
                return {}
            if strict and data.get("errors"):
                raise ValueError("GraphQL response was incomplete")
            return data

        try:
            return await trader_joes_circuit_breaker.call(_do_request)
        except CircuitBreakerOpenException as cbe:
            logger.warning("Trader Joe's circuit breaker active: %s", cbe)
            if strict:
                raise
            return {}
        except Exception as exc:
            logger.error("Error executing Trader Joe's GraphQL query: %s", exc)
            if strict:
                raise
            return {}

    # --- BaseDealAdapter Template Method Hooks ---

    async def fetch_flyer_metadata(
        self,
        postal_code: str,
        chain_id: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[Optional[str], datetime, datetime]:
        """
        Resolves circular/flyer metadata for Trader Joe's Fearless Flyer.
        Returns a tuple of (flyer_id, valid_from, valid_to).
        """
        store_code = (
            kwargs.get("store_code")
            or self._extract_store_code(chain_id)
            or self._extract_store_code(kwargs.get("store_id"))
            or self.store_code
        )

        now = datetime.now(timezone.utc)
        default_valid_from = kwargs.get("valid_from") or now
        default_valid_to = kwargs.get("valid_to") or (now + timedelta(days=14))

        flyer_id = kwargs.get("flyer_id") or f"tj-fearless-flyer-{store_code}"
        return flyer_id, default_valid_from, default_valid_to

    async def fetch_raw_items(self, flyer_id: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """
        Fetches raw promotional item dictionaries for the Fearless Flyer via GraphQL.
        Extracts both What's New and Limited Time Fearless Flyer items.
        """
        store_code = self._extract_store_code(str(flyer_id)) or self.store_code
        seen_skus: set[str] = set()
        all_items: list[dict[str, Any]] = []
        page_size = 50
        current_page = 1

        use_search = bool(self.default_search)

        page_limit = 100 if kwargs.get("strict") else self.max_pages
        while current_page <= page_limit:
            variables: dict[str, Any] = {
                "storeCode": store_code,
                "pageSize": page_size,
                "currentPage": current_page,
                "published": "1",
                "availability": "1",
            }

            if use_search:
                variables["search"] = self.default_search
                query_to_run = SEARCH_PRODUCTS_QUERY
                op_name = "SearchProducts"
            else:
                query_to_run = FEARLESS_FLYER_PROMO_QUERY
                op_name = "FearlessFlyerProducts"

            res = await self.execute_graphql(
                query=query_to_run,
                variables=variables,
                operation_name=op_name,
                **({"strict": True} if kwargs.get("strict") else {}),
            )

            data = res.get("data") if isinstance(res, dict) else None
            if not isinstance(data, dict):
                if kwargs.get("strict"):
                    raise ValueError("Invalid GraphQL data")
                break

            items_to_process: list[dict[str, Any]] = []
            total_pages = 1

            if "products" in data:
                # Standard SearchProducts payload (also used by mocked tests)
                products_data = data.get("products")
                if isinstance(products_data, dict):
                    raw_items = products_data.get("items")
                    if isinstance(raw_items, list):
                        items_to_process.extend(raw_items)
                    page_info = products_data.get("page_info") or {}
                    total_pages = int(page_info.get("total_pages") or 1)
                elif kwargs.get("strict"):
                    raise ValueError("Invalid GraphQL products data")
            else:
                # FearlessFlyerProducts dual-query payload (newProducts + limitedTime)
                for key in ("newProducts", "limitedTime"):
                    sub_data = data.get(key)
                    if isinstance(sub_data, dict):
                        raw_items = sub_data.get("items")
                        if isinstance(raw_items, list):
                            items_to_process.extend(raw_items)
                        page_info = sub_data.get("page_info") or {}
                        sub_pages = int(page_info.get("total_pages") or 1)
                        if sub_pages > total_pages:
                            total_pages = sub_pages
                    elif kwargs.get("strict"):
                        raise ValueError("Incomplete GraphQL products data")

            if kwargs.get("strict") and total_pages > page_limit:
                raise ValueError("GraphQL result exceeds the page limit")

            if not items_to_process:
                break

            for item in items_to_process:
                if isinstance(item, dict):
                    sku = str(item.get("sku") or "").strip()
                    if sku and sku not in seen_skus:
                        seen_skus.add(sku)
                        item.setdefault("id", sku)
                        item.setdefault("item_id", sku)
                        all_items.append(item)
                    elif not sku:
                        all_items.append(item)

            if current_page >= total_pages:
                break
            current_page += 1

        return all_items

    def extract_product_name(self, item: dict[str, Any]) -> str:
        """
        Extracts the raw product name from the GraphQL item dictionary.
        """
        return str(
            item.get("item_title")
            or item.get("name")
            or item.get("title")
            or ""
        ).strip()

    def extract_pricing(
        self, item: dict[str, Any]
    ) -> tuple[Optional[float], Optional[float], str]:
        """
        Extracts (sale_price, original_price, unit) tailored for Trader Joe's data.
        Handles nested price_range structures, retail_price strings/numbers,
        and determines pricing units.
        """
        sale_price = self._extract_sale_price(item)
        original_price = self._extract_regular_price(item, sale_price=sale_price)
        unit = self._determine_pricing_unit(item)
        return sale_price, original_price, unit

    def extract_raw_category(self, item: dict[str, Any]) -> str:
        """
        Extracts raw category string from Trader Joe's category_hierarchy,
        picking the most descriptive/deepest category level available.
        """
        hierarchy = item.get("category_hierarchy")
        if isinstance(hierarchy, list) and hierarchy:
            # Filter out top-level or generic names like 'Products', 'Default Category'
            candidates = [
                h for h in hierarchy
                if isinstance(h, dict) and h.get("name")
                and str(h.get("name")).strip().lower() not in ("products", "default category", "all")
            ]
            if candidates:
                # Pick the highest level (deepest) category
                deepest = max(candidates, key=lambda c: int(c.get("level") or 0))
                cat_name = str(deepest.get("name") or "").strip()
                if cat_name:
                    return cat_name

        categories = item.get("categories")
        if isinstance(categories, list) and categories:
            for cat in reversed(categories):
                if isinstance(cat, dict) and cat.get("name"):
                    name = str(cat.get("name")).strip()
                    if name and name.lower() not in ("products", "default category"):
                        return name

        raw = item.get("category") or item.get("category_code") or "Pantry"
        return str(raw).strip() or "Pantry"

    def extract_brand(self, item: dict[str, Any]) -> Optional[str]:
        """
        Extracts brand name. Trader Joe's inventory is predominantly private label,
        so items default to "Trader Joe's" unless another brand is specified.
        """
        raw_brand = item.get("brand") or item.get("brand_name") or item.get("merchant_brand")
        if raw_brand:
            brand_str = str(raw_brand).strip()
            if brand_str:
                return brand_str

        # Check for well-known TJ sub-brands in product name
        name = self.extract_product_name(item)
        tj_brands = [
            "Trader Joe's",
            "Trader Joe",
            "Trader Jacques",
            "Trader Ming's",
            "Trader Giotto's",
            "Trader Jose's",
            "Baker Josef's",
            "Trader Darwin's",
        ]
        for b in tj_brands:
            if b.lower() in name.lower():
                return "Trader Joe's"

        return self.DEFAULT_MERCHANT

    def extract_image_url(self, item: dict[str, Any]) -> Optional[str]:
        """
        Extracts and normalizes product image URL from primary_image or primary_image_meta.
        Ensures relative paths are resolved to fully qualified https:// URLs.
        """
        url_candidate: Optional[str] = None

        meta = item.get("primary_image_meta")
        if isinstance(meta, dict):
            url_candidate = meta.get("url")
            if not url_candidate and meta.get("metadata"):
                try:
                    meta_json = json.loads(meta["metadata"]) if isinstance(meta["metadata"], str) else meta["metadata"]
                    if isinstance(meta_json, dict):
                        url_candidate = meta_json.get("srcOriginal") or meta_json.get("src")
                except Exception:
                    pass

        if not url_candidate:
            raw_primary = item.get("primary_image")
            if isinstance(raw_primary, str) and raw_primary.strip():
                url_candidate = raw_primary.strip()

        if not url_candidate:
            other_meta = item.get("other_images_meta")
            if isinstance(other_meta, list) and other_meta:
                first = other_meta[0]
                if isinstance(first, dict):
                    url_candidate = first.get("url")

        if not url_candidate:
            context_meta = item.get("context_image_meta")
            if isinstance(context_meta, dict):
                url_candidate = context_meta.get("url")

        if not url_candidate:
            raw_thumb = item.get("thumbnail")
            if isinstance(raw_thumb, dict):
                url_candidate = raw_thumb.get("url")
            elif isinstance(raw_thumb, str) and raw_thumb.strip():
                url_candidate = raw_thumb.strip()

        if not url_candidate or not isinstance(url_candidate, str):
            return None

        url_str = url_candidate.strip()
        if not url_str:
            return None

        if url_str.startswith("//"):
            return f"https:{url_str}"
        if url_str.startswith("/"):
            return f"https://www.traderjoes.com{url_str}"
        if url_str.startswith("http://"):
            return f"https://{url_str[7:]}"
        if url_str.startswith("https://"):
            return url_str

        return f"https://www.traderjoes.com/{url_str.lstrip('/')}"

    # --- Pricing & Unit Helpers ---

    def _extract_sale_price(self, item: dict[str, Any]) -> Optional[float]:
        """
        Extracts sale/current price from GraphQL item payload.
        """
        # 1. Check special_price
        special = item.get("special_price")
        if special is not None:
            val = self._parse_float_price(special)
            if val is not None and val > 0:
                return val

        # 2. Check price_range.minimum_price.final_price.value
        price_range = item.get("price_range")
        if isinstance(price_range, dict):
            min_price = price_range.get("minimum_price")
            if isinstance(min_price, dict):
                final_price = min_price.get("final_price")
                if isinstance(final_price, dict) and final_price.get("value") is not None:
                    val = self._parse_float_price(final_price.get("value"))
                    if val is not None and val > 0:
                        return val

        # 3. Check retail_price
        retail = item.get("retail_price")
        if retail is not None:
            val = self._parse_float_price(retail)
            if val is not None and val > 0:
                return val

        # 4. Check price
        price = item.get("price")
        if price is not None:
            val = self._parse_float_price(price)
            if val is not None and val > 0:
                return val

        # 5. Check item marketing story or description text for price mentions
        text = str(item.get("item_story_marketing") or item.get("item_description") or "")
        dollar_match = re.search(r"\$\s*(\d+(?:\.\d{2})?)", text)
        if dollar_match:
            try:
                val = float(dollar_match.group(1))
                if val > 0:
                    return val
            except ValueError:
                pass

        return None

    def _extract_regular_price(
        self, item: dict[str, Any], sale_price: Optional[float] = None
    ) -> Optional[float]:
        """
        Extracts original/regular price if distinct from the sale price.
        """
        # 1. Check regular_price under price_range
        price_range = item.get("price_range")
        if isinstance(price_range, dict):
            min_price = price_range.get("minimum_price")
            if isinstance(min_price, dict):
                regular = min_price.get("regular_price")
                if isinstance(regular, dict) and regular.get("value") is not None:
                    val = self._parse_float_price(regular.get("value"))
                    if val is not None and sale_price is not None and val > sale_price:
                        return val

        # 2. Check explicit regular_price / original_price fields
        for key in ("regular_price", "original_price"):
            raw = item.get(key)
            if raw is not None:
                val = self._parse_float_price(raw)
                if val is not None and sale_price is not None and val > sale_price:
                    return val

        # 3. If special_price was used as sale_price, retail_price is the original
        if item.get("special_price") is not None and item.get("retail_price") is not None:
            retail_val = self._parse_float_price(item.get("retail_price"))
            if retail_val is not None and sale_price is not None and retail_val > sale_price:
                return retail_val

        return None

    def _determine_pricing_unit(self, item: dict[str, Any]) -> str:
        """
        Determines whether the pricing unit is 'lb' or 'each'.
        """
        text_sources = [
            str(item.get("sales_uom_description") or ""),
            str(item.get("sales_uom_code") or ""),
            str(item.get("sales_size") or ""),
            str(item.get("item_title") or ""),
            str(item.get("name") or ""),
            str(item.get("item_story_marketing") or ""),
        ]
        combined = " ".join(text_sources).lower()

        # Check explicit per-pound patterns
        if re.search(
            r"(?:per\s+lb|per\s+pound|\/\s*lb|\b\$\s*\d+(?:\.\d+)?\s*\/\s*lb|\b\$\s*\d+(?:\.\d+)?\s*per\s*lb|\b\$\s*\d+(?:\.\d+)?\s*lb\b)",
            combined,
        ):
            return "lb"

        if any(term in combined for term in ("per lb", "/lb", "/ lb", "per pound")):
            return "lb"

        uom = str(item.get("sales_uom_description") or "").strip().lower()
        if uom in ("pound", "lb", "lbs"):
            return "lb"

        return "each"

    @staticmethod
    def _parse_float_price(val: Any) -> Optional[float]:
        """Parses a float price from number or formatted string ($1.99, 99c)."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = val.strip()
            # Match 99¢ or 99 cents
            cents_match = re.match(r"^(\d+)\s*(?:¢|c|cents?)$", cleaned, re.IGNORECASE)
            if cents_match:
                try:
                    return round(float(cents_match.group(1)) / 100.0, 2)
                except ValueError:
                    return None
            # Match $X.XX or X.XX
            num_match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
            if num_match:
                try:
                    return float(num_match.group(1))
                except ValueError:
                    return None
        return None

    @staticmethod
    def _extract_store_code(identifier: Optional[str]) -> Optional[str]:
        """Extracts store code from identifier like 'tj-fearless-flyer-34' or 'trader-joes-701'."""
        if not identifier:
            return None
        s = str(identifier).strip()
        match = re.search(r"\b(\d{1,4})\b", s)
        if match:
            return match.group(1)
        return None
