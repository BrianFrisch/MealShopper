import asyncio
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Optional

from deal_normalizer import (
    needs_multi_item_expansion,
    expand_and_normalize_deals_batch,
)
from src.services.categories import (
    DEFAULT_CATEGORY_MAP,
    is_excluded_primary_meat_item,
    resolve_protein_subtype,
    standardize_category as _standardize_category,
)


try:
    from src.ingestion.models import NormalizedDealItem, clean_product_name
except ImportError:
    from ..models import NormalizedDealItem, clean_product_name

logger = logging.getLogger(__name__)

_gemini_semaphore = asyncio.Semaphore(1)


class BaseDealAdapter(ABC):
    """
    Abstract base class for grocery store circular/deal adapters.
    Implements the Template Method pattern for deal ingestion and normalization.
    """

    category_map: dict[str, str] = DEFAULT_CATEGORY_MAP

    def __init__(self, gemini_client: Optional[Any] = None, **kwargs: Any) -> None:
        self.gemini_client = gemini_client
        if self.gemini_client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("BaseDealAdapter: GEMINI_API_KEY is not set or empty in environment.")
            else:
                try:
                    from google import genai
                    self.gemini_client = genai.Client(api_key=api_key)
                    logger.info("BaseDealAdapter: Successfully initialized Gemini client.")
                except Exception as exc:
                    logger.error("BaseDealAdapter: Failed to initialize Gemini client: %s", exc, exc_info=True)
                    self.gemini_client = None

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

    def extract_brand(self, item: dict[str, Any]) -> Optional[str]:
        """
        Extract brand string from provider item payload if present.
        Default implementation checks common brand keys in provider payloads.
        """
        raw_brand = item.get("brand") or item.get("brand_name") or item.get("merchant_brand")
        if raw_brand is not None:
            brand_str = str(raw_brand).strip()
            return brand_str if brand_str else None
        return None

    @abstractmethod
    def extract_image_url(self, item: dict[str, Any]) -> Optional[str]:
        """Extract the promotional product image URL from the raw item."""
        pass

    def determine_protein_subtype(self, product_name: str, normalized_category: str) -> Optional[str]:
        """Resolves specific protein subtype for meat/seafood deals."""
        return resolve_protein_subtype(product_name, normalized_category)

    def standardize_category(self, raw_category: str, product_name: str = "") -> str:
        """
        Maps raw category strings and product titles to standardized categories:
        Produce, Dairy, Meat, Seafood, Bakery, Pantry.
        """
        return _standardize_category(raw_category, product_name, category_map=self.category_map)

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
        chain_id = (
            merchant_name
            or kwargs.get("chain_id")
            or getattr(self, "default_merchant", None)
            or getattr(self, "DEFAULT_MERCHANT", None)
            or store_id
        )
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

        effective_gemini_client = (
            kwargs.get("gemini_client")
            if "gemini_client" in kwargs
            else self.gemini_client
        )

        parsed_deals: list[dict[str, Any]] = []
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
            brand = self.extract_brand(item)

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

            image_url = self.extract_image_url(item)
            protein_subtype = self.determine_protein_subtype(product_name, normalized_cat)
            
            parsed_deals.append(
                {
                    "deal_id": deal_id,
                    "store_id": store_id,
                    "store_name": effective_store_name,
                    "item_name": product_name,
                    "clean_name": clean_name,
                    "brand": brand,
                    "raw_category": raw_cat,
                    "normalized_category": normalized_cat,
                    "protein_subtype": protein_subtype,
                    "image_url": image_url,
                    "deal_price": sale_price,
                    "original_price": original_price,
                    "currency": "USD",
                    "unit": unit or "each",
                    "value_score": value_score,
                    "raw_promotion_text": raw_promo,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                }
            )

        # 1. Partition parsed deals into candidate and passthrough deals
        passthrough_deals: list[dict[str, Any]] = []
        candidate_deals: list[dict[str, Any]] = []

        for deal_dict in parsed_deals:
            item_name = str(deal_dict.get("item_name") or "")
            if needs_multi_item_expansion(item_name):
                candidate_deals.append(deal_dict)
            else:
                passthrough_deals.append(deal_dict)

        # 2. Batch and throttle multi-item expansions for candidate deals
        expanded_candidate_deals: list[dict[str, Any]] = []
        if candidate_deals and effective_gemini_client is not None:
            chunk_size = 15
            chunks = [
                candidate_deals[i : i + chunk_size]
                for i in range(0, len(candidate_deals), chunk_size)
            ]
            for idx, chunk in enumerate(chunks):
                async with _gemini_semaphore:
                    batch_res = await expand_and_normalize_deals_batch(
                        deals=chunk,
                        client=effective_gemini_client,
                    )
                    expanded_candidate_deals.extend(batch_res)
                    if idx < len(chunks) - 1:
                        await asyncio.sleep(1.0)
        else:
            expanded_candidate_deals = candidate_deals

        combined_deals: list[dict[str, Any]] = expanded_candidate_deals + passthrough_deals

        # 3. Recompute category exclusions & protein_subtype after expansion, then deduplicate by (store_id, clean_name)
        deduped_deals: list[NormalizedDealItem] = []
        seen_keys: set[tuple[str, str]] = set()

        for deal_data in combined_deals:
            if isinstance(deal_data, dict):
                effective_name = str(
                    deal_data.get("clean_name")
                    or deal_data.get("item_name")
                    or ""
                )
                effective_cat = str(
                    deal_data.get("normalized_category")
                    or deal_data.get("category")
                    or "Pantry"
                )
                if is_excluded_primary_meat_item(effective_name):
                    effective_cat = "Pantry"
                    deal_data["normalized_category"] = "Pantry"
                deal_data["protein_subtype"] = self.determine_protein_subtype(
                    effective_name, effective_cat
                )

            deal_item = (
                deal_data
                if isinstance(deal_data, NormalizedDealItem)
                else NormalizedDealItem.model_validate(deal_data)
            )
            dedup_key = (deal_item.store_id, deal_item.clean_name.strip().lower())
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                deduped_deals.append(deal_item)

        return valid_from, valid_to, deduped_deals

    async def close(self) -> None:
        """Closes any underlying client or network connections."""
        pass

    async def __aenter__(self) -> "BaseDealAdapter":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
