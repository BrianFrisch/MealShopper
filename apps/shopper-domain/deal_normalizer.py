import asyncio
import copy
import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, Optional

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("shopper_domain.deal_normalizer")

# Standard normalized grocery categories
VALID_CATEGORIES = [
    "Produce",
    "Meat",
    "Seafood",
    "Dairy",
    "Bakery",
    "Pantry",
]

NormalizedCategory = Literal[
    "Produce",
    "Meat",
    "Seafood",
    "Dairy",
    "Bakery",
    "Pantry",
]

CATEGORY_MAP: Dict[str, NormalizedCategory] = {
    "produce": "Produce",
    "fruits": "Produce",
    "fruit": "Produce",
    "vegetables": "Produce",
    "vegetable": "Produce",
    "fresh produce": "Produce",
    "meat & poultry": "Meat",
    "meat and poultry": "Meat",
    "meat": "Meat",
    "poultry": "Meat",
    "beef": "Meat",
    "chicken": "Meat",
    "pork": "Meat",
    "turkey": "Meat",
    "lamb": "Meat",
    "seafood": "Seafood",
    "fish": "Seafood",
    "shellfish": "Seafood",
    "dairy & eggs": "Dairy",
    "dairy and eggs": "Dairy",
    "dairy": "Dairy",
    "eggs": "Dairy",
    "milk": "Dairy",
    "cheese": "Dairy",
    "pantry": "Pantry",
    "grocery": "Pantry",
    "snacks": "Pantry",
    "condiments": "Pantry",
    "canned goods": "Pantry",
    "bakery": "Bakery",
    "bread": "Bakery",
    "baked goods": "Bakery",
    "frozen": "Pantry",
    "frozen foods": "Pantry",
    "frozen meals": "Pantry",
    "beverages": "Pantry",
    "beverage": "Pantry",
    "drinks": "Pantry",
    "soda": "Pantry",
}


class NormalizedDealItemOutput(BaseModel):
    """Pydantic schema representing a single cleanly extracted item from a deal."""
    clean_name: str
    normalized_category: NormalizedCategory
    unit: str = "each"
    qualifiers: List[str] = Field(default_factory=list)
    brand: Optional[str] = None

    @field_validator("normalized_category", mode="before")
    @classmethod
    def validate_and_normalize_category(cls, v: Any) -> Any:
        if isinstance(v, str):
            key = v.strip().lower()
            if key in CATEGORY_MAP:
                return CATEGORY_MAP[key]
            for cat in VALID_CATEGORIES:
                if cat.lower() == key:
                    return cat
        return v


class DealExpansionItem(BaseModel):
    """Container for multi-item expansion results linked to a source index."""
    source_index: int
    items: List[NormalizedDealItemOutput] = Field(default_factory=list)


class BatchDealExpansionResponse(BaseModel):
    """Structured response container returned by Gemini LLM for batched deal expansion."""
    expansions: List[DealExpansionItem] = Field(default_factory=list)


# Backwards compatibility aliases / legacy models
NormalizedItem = NormalizedDealItemOutput


class DealExpansionResponse(BaseModel):
    """Legacy structured response container for single-deal expansion."""
    items: List[NormalizedDealItemOutput] = Field(default_factory=list)


# Global rate-limiting semaphore for flyer ingestion LLM calls
DEFAULT_MAX_CONCURRENCY = int(os.getenv("GEMINI_MAX_CONCURRENCY", "10"))
_default_semaphore: Optional[asyncio.Semaphore] = None


def get_default_semaphore(limit: int = DEFAULT_MAX_CONCURRENCY) -> asyncio.Semaphore:
    """Retrieve or lazily initialize the default asyncio Semaphore for rate limiting."""
    global _default_semaphore
    if _default_semaphore is None:
        _default_semaphore = asyncio.Semaphore(limit)
    return _default_semaphore


def needs_multi_item_expansion(item_name: Optional[str]) -> bool:
    """
    Heuristic detector using regex to determine if a promotional deal title
    describes a multi-item choice/disjunctive deal (e.g. "Item A or Item B",
    "Choice of Beef or Chicken", "Apples / Pears").

    Avoids false positives on:
    - Compound complementary pairs (e.g. "bacon and eggs", "mac and cheese", "pork and beans")
    - Fractions / ratios (e.g. "1/2 lb", "80/20 ground beef", "24/16.9 fl oz")
    - Standard abbreviations (e.g. "w/", "w/o", "c/o")
    - Per-unit price tags (e.g. "$1.99/lb", "per/lb")
    - Standalone words containing 'or' substring (e.g. "orange", "organic", "pork", "flavor")
    """
    if not isinstance(item_name, str):
        return False

    text = item_name.strip()
    if not text:
        return False

    # 1. Disjunctive keywords: standalone 'or' or 'choice of' (e.g. "Apples or Pears", "Choice of Ribeye or Salmon")
    if re.search(r"\b(?:or|choice of)\b", text, re.IGNORECASE):
        return True

    # 2. Slashes between distinct word tokens (e.g., "Beef / Chicken", "Apples/Pears")
    # Matches alphabetical tokens of length >= 2 separated by slash, excluding common abbreviations or units
    slash_match = re.search(
        r"(?<!\bw)(?<!\bc)(?<!\b\d)\b([a-zA-Z]{2,})\s*/\s*([a-zA-Z]{2,})\b(?!/)(?!o\b)",
        text,
        re.IGNORECASE,
    )
    if slash_match:
        w1, w2 = slash_match.group(1).lower(), slash_match.group(2).lower()
        units_and_noise = {
            "lb", "lbs", "oz", "pkg", "pk", "ct", "ea", "kg", "qt", "pt", "gal",
            "fl", "per", "approx", "max", "min", "net", "wt"
        }
        if w1 not in units_and_noise and w2 not in units_and_noise:
            return True

    return False


async def expand_and_normalize_deals_batch(
    deals: List[Dict[str, Any]],
    client: Any,
    model: str = "gemini-3.5-flash-lite",
) -> List[Dict[str, Any]]:
    """
    Asynchronously expand and normalize a batch of promotional grocery deals.

    - Accepts a list of raw deal dictionaries (up to 15-20 items per batch).
    - Formats a structured prompt passing an array of `{"source_index": i, "raw_name": deal["item_name"]}`.
    - Instructs Gemini to identify deals containing multiple distinct products (via "or", "/", "choice of") and split them;
      single products return 1 item with clean_name and category.
    - For each returned expansion, maps `source_index` back to the original deal dictionary:
      - If multiple items are extracted (> 1), clones the parent deal dictionary for each with
        deal_id = f"{parent_deal_id}_{idx}", updated clean_name, normalized_category, and unit.
      - If 1 item is extracted, updates clean_name, normalized_category, and unit on the original deal dictionary.
    - Structured output config: response_mime_type="application/json", response_schema=BatchDealExpansionResponse, temperature=0.1.
    - On quota (429) or API error, logs a warning and falls back gracefully to returning the original deals unchanged.
    """
    if not deals:
        return []

    if client is None:
        logger.warning("No Gemini client provided. Returning deals unchanged.")
        return deals

    input_deals = [
        {
            "source_index": i,
            "raw_name": str(
                d.get("item_name")
                or d.get("product_name")
                or d.get("name")
                or d.get("clean_name")
                or ""
            ),
            "brand": str(d.get("brand") or ""),
            "raw_category": str(d.get("raw_category") or d.get("category") or ""),
        }
        for i, d in enumerate(deals)
    ]
    deals_json = json.dumps(input_deals, indent=2)

    prompt = f"""You are an expert grocery catalog normalizer.
Analyze the following batch of promotional grocery deals.

DEALS TO NORMALIZE:
{deals_json}

INSTRUCTIONS:
1. For each deal by its `source_index`:
   - Identify if the promotional deal contains multiple distinct product choices/options (e.g. via "or", "/", "choice of" like "Apples or Pears", "Choice of Ribeye or Salmon", "Beef / Chicken", "cray 5-6 oz. or Barilla Pesto Sauce 6.2-6.5 oz.").
   - If it contains multiple distinct products, split them into separate items in `items`.
   - If it is a single product deal, return exactly 1 item in `items`.
2. Actively use the `brand` field to correct OCR clipping or typos in `raw_name`:
   - For example, brand "PAM" with item name "cray" indicates "cooking spray", which must be normalized to clean_name "cooking spray", normalized_category "Pantry", and unit matching the container, NOT "Seafood".
   - Distribute compound multi-brand deals (e.g., brand "PAM | Barilla" for "cray 5-6 oz. or Barilla Pesto Sauce 6.2-6.5 oz.") to their corresponding split items:
     * Item 1: brand "PAM", clean_name "cooking spray", normalized_category "Pantry"
     * Item 2: brand "Barilla", clean_name "pesto sauce", normalized_category "Pantry"
3. For each extracted item:
   - `clean_name`: Concise, clean product name without sizing noise, prices, or OCR truncation artifacts (e.g. 'cooking spray', 'pesto sauce', 'gala apples', 'bartlett pears').
   - `brand`: The specific brand associated with this extracted item if known or derived from `brand` (e.g. 'PAM', 'Barilla').
   - `normalized_category`: Must be one of: 'Produce', 'Meat', 'Seafood', 'Dairy', 'Bakery', 'Pantry'.
   - `unit`: Pricing unit (e.g. 'lb', 'each', 'oz', 'gallon'). Default to 'each' if unspecified.
   - `qualifiers`: List of any specific varietals, brands, or cuts (e.g. ['boneless', 'skinless', 'pesto', 'original']).
4. Ensure every `source_index` from the input array is represented in `expansions`.
"""

    try:
        config = (
            getattr(types, "GenerateContentConfig")(
                response_mime_type="application/json",
                response_schema=BatchDealExpansionResponse,
                temperature=0.1,
            )
            if types is not None and hasattr(types, "GenerateContentConfig")
            else {
                "response_mime_type": "application/json",
                "response_schema": BatchDealExpansionResponse,
                "temperature": 0.1,
            }
        )

        if hasattr(client, "aio") and hasattr(client.aio, "models"):
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
        elif hasattr(client, "models"):
            response = await asyncio.to_thread(
                lambda: client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
            )
        else:
            raise AttributeError("Client does not have 'aio.models' or 'models' attribute.")

        batch_response: Optional[BatchDealExpansionResponse] = None
        if hasattr(response, "parsed") and response.parsed:
            if isinstance(response.parsed, BatchDealExpansionResponse):
                batch_response = response.parsed
            elif isinstance(response.parsed, DealExpansionResponse):
                batch_response = BatchDealExpansionResponse(
                    expansions=[DealExpansionItem(source_index=0, items=response.parsed.items)]
                )
            elif isinstance(response.parsed, dict):
                if "expansions" in response.parsed:
                    batch_response = BatchDealExpansionResponse.model_validate(response.parsed)
                elif "items" in response.parsed:
                    batch_response = BatchDealExpansionResponse(
                        expansions=[
                            DealExpansionItem.model_validate(
                                {"source_index": 0, "items": response.parsed["items"]}
                            )
                        ]
                    )
            elif hasattr(response.parsed, "expansions"):
                batch_response = BatchDealExpansionResponse.model_validate(response.parsed)
            elif hasattr(response.parsed, "items"):
                items_val = getattr(response.parsed, "items")
                batch_response = BatchDealExpansionResponse(
                    expansions=[
                        DealExpansionItem.model_validate(
                            {"source_index": 0, "items": items_val}
                        )
                    ]
                )
            elif isinstance(response.parsed, BaseModel):
                batch_response = BatchDealExpansionResponse.model_validate(response.parsed.model_dump())
            else:
                batch_response = BatchDealExpansionResponse.model_validate(response.parsed)

        if not batch_response and hasattr(response, "text") and response.text:
            try:
                batch_response = BatchDealExpansionResponse.model_validate_json(response.text)
            except Exception:
                pass

        if not batch_response or not batch_response.expansions:
            logger.warning("Gemini returned empty expansions. Falling back to original deals.")
            return deals

        expansions_by_index: Dict[int, List[NormalizedDealItemOutput]] = {}
        for exp in batch_response.expansions:
            if 0 <= exp.source_index < len(deals):
                expansions_by_index[exp.source_index] = exp.items

        result_deals: List[Dict[str, Any]] = []
        for i, deal in enumerate(deals):
            items = expansions_by_index.get(i)
            if not items:
                result_deals.append(deal)
                continue

            parent_deal_id = str(deal.get("deal_id") or deal.get("id") or f"deal_{i}")
            parent_unit = str(deal.get("unit") or deal.get("pricing_unit") or "each")
            parent_brand = deal.get("brand")

            # Parse potential compound brands (e.g. "PAM | Barilla" -> ["PAM", "Barilla"])
            brand_parts = (
                [b.strip() for b in re.split(r"\s*(?:\||\/|\bor\b)\s*", str(parent_brand))]
                if parent_brand
                else []
            )

            if len(items) > 1:
                for idx, item in enumerate(items):
                    cloned: Dict[str, Any] = copy.deepcopy(deal)
                    cloned["deal_id"] = f"{parent_deal_id}_{idx}"
                    cloned["clean_name"] = item.clean_name
                    cloned["normalized_category"] = item.normalized_category
                    cloned["unit"] = item.unit or parent_unit
                    if "category" in cloned:
                        cloned["category"] = item.normalized_category
                    if "item_name" in cloned:
                        cloned["item_name"] = item.clean_name
                    if item.qualifiers:
                        cloned["qualifiers"] = item.qualifiers

                    # Preserved / distributed brand mapping
                    if getattr(item, "brand", None):
                        cloned["brand"] = item.brand
                    elif len(brand_parts) == len(items) and idx < len(brand_parts):
                        cloned["brand"] = brand_parts[idx]
                    elif parent_brand is not None:
                        cloned["brand"] = parent_brand

                    result_deals.append(cloned)
            elif len(items) == 1:
                item = items[0]
                cloned = copy.deepcopy(deal)
                cloned["clean_name"] = item.clean_name
                cloned["normalized_category"] = item.normalized_category
                cloned["unit"] = item.unit or parent_unit
                if "category" in cloned:
                    cloned["category"] = item.normalized_category
                if "item_name" in cloned:
                    cloned["item_name"] = item.clean_name
                if item.qualifiers:
                    cloned["qualifiers"] = item.qualifiers

                # Preserved brand mapping
                if getattr(item, "brand", None):
                    cloned["brand"] = item.brand
                elif parent_brand is not None:
                    cloned["brand"] = parent_brand

                result_deals.append(cloned)
            else:
                result_deals.append(deal)

        return result_deals

    except Exception as e:
        logger.warning(
            "Failed to expand/normalize deals batch via Gemini LLM (%s). Falling back to original deals.",
            str(e),
        )
        return deals


async def expand_and_normalize_deal(
    raw_deal: Dict[str, Any],
    client: Optional[Any] = None,
    semaphore: Optional[asyncio.Semaphore] = None,
    model_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Asynchronously expand and normalize a promotional grocery deal.

    If `needs_multi_item_expansion` detects a multi-item deal:
      - Prompts Gemini using structured JSON output matching BatchDealExpansionResponse schema.
      - For each extracted item:
          - deal_id: f"{raw_deal['deal_id']}_{idx}"
          - clean_name: item.clean_name
          - normalized_category: item.normalized_category
          - unit: item.unit or raw_deal['unit']
          - retains original store_id, deal_price, and validity timestamps.
    If not a multi-item deal or upon LLM failure:
      - Gracefully falls back to returning the single parent deal dictionary in a list.
    """
    logger.info("Expanding and normalizing deal: %s", raw_deal.get("item_name") or raw_deal.get("deal_id") or "N/A")
    if client is None:
        logger.warning("No Gemini client provided. Falling back to parent deal without expansion.")
        return [raw_deal]

    raw_name_val = (
        raw_deal.get("item_name")
        or raw_deal.get("product_name")
        or raw_deal.get("name")
        or raw_deal.get("clean_name")
        or ""
    )
    item_name: str = str(raw_name_val)

    if not needs_multi_item_expansion(item_name):
        logger.info("No multi-item expansion needed for deal '%s'. Returning parent deal.", item_name)
        return [raw_deal]

    target_model = model_name or os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")
    sem = semaphore or get_default_semaphore()
    async with sem:
        return await expand_and_normalize_deals_batch(
            deals=[raw_deal],
            client=client,
            model=target_model,
        )


async def expand_and_normalize_deals(
    raw_deals: List[Dict[str, Any]],
    client: Any,
    semaphore: Optional[asyncio.Semaphore] = None,
    model_name: Optional[str] = None,
    batch_size: int = 15,
) -> List[Dict[str, Any]]:
    """
    Batch helper to asynchronously expand and normalize a list of promotional deals,
    utilizing a rate-limiting semaphore across all concurrent LLM calls.
    """
    if not raw_deals:
        return []
    if client is None:
        logger.warning("No Gemini client provided. Returning deals without expansion.")
        return raw_deals

    target_model = model_name or os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")
    sem = semaphore or get_default_semaphore()

    batches = [raw_deals[i : i + batch_size] for i in range(0, len(raw_deals), batch_size)]

    async def process_batch(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        async with sem:
            return await expand_and_normalize_deals_batch(
                deals=batch,
                client=client,
                model=target_model,
            )

    tasks = [process_batch(batch) for batch in batches]
    results = await asyncio.gather(*tasks)
    return [d for sublist in results for d in sublist]


class DealNormalizer:
    """Service wrapper for asynchronous deal normalization."""

    def __init__(
        self,
        client: Optional[Any] = None,
        model_name: Optional[str] = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = client or (genai.Client(api_key=self.api_key) if (genai and self.api_key) else None)
        self.model_name = model_name or os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def normalize_deal(self, raw_deal: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self.client:
            logger.warning("Gemini client not initialized; skipping multi-item expansion.")
            return [raw_deal]
        return await expand_and_normalize_deal(
            raw_deal=raw_deal,
            client=self.client,
            semaphore=self.semaphore,
            model_name=self.model_name,
        )

    async def normalize_deals(
        self,
        raw_deals: List[Dict[str, Any]],
        batch_size: int = 15,
    ) -> List[Dict[str, Any]]:
        if not self.client:
            logger.warning("Gemini client not initialized; skipping multi-item expansion.")
            return raw_deals
        return await expand_and_normalize_deals(
            raw_deals=raw_deals,
            client=self.client,
            semaphore=self.semaphore,
            model_name=self.model_name,
            batch_size=batch_size,
        )

