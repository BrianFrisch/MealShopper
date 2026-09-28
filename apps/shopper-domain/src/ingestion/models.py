from datetime import datetime, timezone
import re
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


def clean_product_name(raw_name: str) -> str:
    """
    Cleans a product name by:
    - Converting text to lowercase.
    - Stripping common package sizing strings (e.g., '16 oz', '1 lb', 'ct', 'pk').
    - Removing special characters and extra whitespace.
    """
    if not raw_name:
        return ""

    text = raw_name.lower()

    # 1. Strip multipack dimension patterns like "12 x 12 oz", "24/16.9 oz", "6 x 0.5 l"
    text = re.sub(
        r"\b\d+\s*(?:x|\*|\/)\s*\d+(?:\.\d+)?\s*(?:fl(?:uid)?\.?\s*oz\.?|oz\.?|ounces?|lbs?\.?|pounds?|grams?|g\.?|kilograms?|kg\.?|milliliters?|ml\.?|liters?|l\.?|gallons?|gal\.?|quarts?|qt\.?|pints?|pt\.?|counts?|ct\.?|packs?|pks?\.?|pkgs?\.?)\b",
        " ",
        text,
    )

    # 2. Strip quantity + unit sizing patterns (e.g. "16 oz", "16.9 fl oz", "1 lb", "1-lb", "500g", "12 ct", "24 pack", "7.25oz", "1/2 lb")
    unit_pattern = (
        r"(?:fl(?:uid)?\.?\s*oz\.?|oz\.?|ounces?|lbs?\.?|pounds?|grams?|g\.?|kilograms?|kg\.?|"
        r"milliliters?|ml\.?|liters?|l\.?|gallons?|gal\.?|quarts?|qt\.?|pints?|pt\.?|"
        r"counts?|ct\.?|packs?|pks?\.?|pkgs?\.?|pieces?|pcs?\.?)"
    )
    # Match numbers (decimals, fractions, ranges) attached to or followed by units
    text = re.sub(
        rf"\b(?:\d+(?:\.\d+)?|\d+\/\d+|\d+\s*-\s*\d+)\s*(?:-|/)?\s*{unit_pattern}\b",
        " ",
        text,
    )
    # Also handle cases where number is directly prefixed like 16oz, 1lb, 12ct, 6pk
    text = re.sub(
        rf"\b\d+(?:\.\d+)?{unit_pattern}\b",
        " ",
        text,
    )

    # 3. Strip standalone pack / count / sizing keywords: e.g. "ct", "pk", "pkg", "pack", "count"
    text = re.sub(r"\b(?:ct|cnt|count|pk|pck|pack|pkg|package)\b", " ", text)

    # 4. Remove special characters (keep alphanumeric and whitespace)
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # 5. Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


class CoordinatesDto(BaseModel):
    latitude: float = 33.8895
    longitude: float = -118.3533


class RegionContextDto(BaseModel):
    coordinates: CoordinatesDto = Field(default_factory=CoordinatesDto)
    store_ids: list[str] = Field(default_factory=list)


class NormalizedDealItem(BaseModel):
    deal_id: str
    store_id: str
    store_name: str
    item_name: str
    clean_name: str
    normalized_category: str = "Pantry"
    deal_price: float
    original_price: Optional[float] = None
    currency: str = "USD"
    unit: str = "each"
    value_score: float = 8.0
    raw_promotion_text: str = ""
    valid_from: datetime
    valid_to: datetime

    @model_validator(mode="before")
    @classmethod
    def populate_clean_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("clean_name"):
                name = data.get("item_name") or data.get("product_name")
                if isinstance(name, str):
                    data["clean_name"] = clean_product_name(name)
                elif "clean_name" not in data:
                    data["clean_name"] = ""
        return data


class TopDealsResponse(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    region_context: RegionContextDto
    deals: list[NormalizedDealItem]
