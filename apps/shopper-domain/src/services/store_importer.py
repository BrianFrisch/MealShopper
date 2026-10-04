# apps/shopper-domain/src/services/store_importer.py
import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypedDict
import asyncpg # type: ignore
import httpx

try:
    from src.services.grocery_chain_service import GroceryChainService
except ImportError:
    from .grocery_chain_service import GroceryChainService

logger = logging.getLogger(__name__)

ALL_THE_PLACES_BASE = "https://data.alltheplaces.xyz/runs/latest/output"


class ParsedStore(TypedDict):
    store_id: str
    chain_id: str
    store_number: str
    store_name: str
    street_address: str
    city: str
    state_province: str
    postal_code: str
    longitude: float
    latitude: float


def clean_store_number(raw_num: Optional[Any], fallback_id: str) -> str:
    if raw_num is None:
        digits = re.findall(r"\d+", fallback_id)
        return digits[0] if digits else "0"
    num_str = str(raw_num).strip()
    match = re.search(r"\d+", num_str)
    if match:
        val = match.group(0).lstrip("0")
        return val if val else "0"
    return re.sub(r"[^a-zA-Z0-9]", "", num_str)[:16] or "0"


def normalize_state(region_state: str) -> str:
    state = region_state.strip().upper()
    return state


def is_matching_state(store_state: str, target_state: str) -> bool:
    if not target_state or not store_state:
        return True
    return store_state.strip().upper() == target_state.strip().upper()


def is_matching_banner(brand: str, target_banner: str) -> bool:
    brand_lower = brand.lower()
    if target_banner.lower() not in brand_lower:
        return False
    if "fuel" in brand_lower or "gas" in brand_lower:
        return False
    return True


def resolve_address(props: Dict[str, Any]) -> Tuple[str, str, str]:
    street = (
        props.get("street_address")
        or props.get("addr:full")
        or props.get("addr_full")
        or f"{props.get('addr:housenumber', '')} {props.get('addr:street', '')}".strip()
        or props.get("address")
        or props.get("addr:street_address")
        or props.get("street")
        or "Address Unspecified"
    )
    city = props.get("addr:city") or props.get("city") or "Unknown"
    postal_code = props.get("addr:postcode") or props.get("postcode") or "00000"
    return street.strip(), city.strip(), str(postal_code).strip()


def parse_geojson_feature(
    feat: Dict[str, Any],
    chain_key: str,
    meta: Dict[str, str],
    target_state: str,
    include_all_brands: bool = False,
) -> Optional[ParsedStore]:
    props = feat.get("properties", {})
    geom = feat.get("geometry", {})
    if not geom:
        return None

    coords = geom.get("coordinates", [])
    if not coords or len(coords) < 2:
        return None

    lon, lat = float(coords[0]), float(coords[1])
    store_state = (
        props.get("addr:state") or props.get("state") or props.get("addr:province") or ""
    ).strip().upper()

    if not is_matching_state(store_state, target_state):
        return None

    brand = (props.get("brand") or props.get("name") or "").strip()
    target_banner = meta["display_name"].lower()
    if not is_matching_banner(brand, target_banner) and not include_all_brands:
        return None

    raw_num = props.get("ref") or props.get("store_number") or props.get("@id")
    store_number = clean_store_number(raw_num, str(feat.get("id", "0")))
    store_id = f"{chain_key}-{store_number}"

    street, city, postal_code = resolve_address(props)

    return {
        "store_id": store_id,
        "chain_id": chain_key,
        "store_number": store_number,
        "store_name": brand or f"{meta['display_name']} #{store_number}",
        "street_address": street,
        "city": city,
        "state_province": store_state or target_state or "CA",
        "postal_code": postal_code,
        "longitude": lon,
        "latitude": lat,
    }


def deduplicate_stores(stores: Sequence[ParsedStore]) -> List[ParsedStore]:
    """Deduplicate stores sharing approximately the same coordinates, preferring shorter store numbers."""
    unique_locations: Dict[str, ParsedStore] = {}
    for store in stores:
        coord_key = f"{round(store['longitude'], 4)}_{round(store['latitude'], 4)}"
        if coord_key in unique_locations:
            existing = unique_locations[coord_key]
            if len(store["store_number"]) < len(existing["store_number"]):
                unique_locations[coord_key] = store
        else:
            unique_locations[coord_key] = store
    return list(unique_locations.values())


class StoreImportService:
    def __init__(self, db_url: str, chain_service: Optional[GroceryChainService] = None):
        self.db_url = db_url
        self.chain_service = chain_service or GroceryChainService(db_url=db_url)

    async def get_chain_metadata(self, chain_id: str) -> Dict[str, str]:
        """Retrieve grocery chain metadata through the shared chain service."""
        return await self.chain_service.get_chain_metadata(chain_id)

    async def _fetch_geojson(self, spider: str) -> Dict[str, Any]:
        spider_file = f"{spider}.geojson"
        url = f"{ALL_THE_PLACES_BASE}/{spider_file}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def _persist_stores(
        self, chain_key: str, meta: Dict[str, str], stores: List[ParsedStore]
    ) -> None:
        await self.chain_service.upsert_chain(
            chain_id=chain_key,
            display_name=meta["display_name"],
            adapter_name=meta["adapter_name"],
            spider_name=meta.get("spider") or meta.get("spider_name"),
            flyer_source_type=meta.get("flyer_source_type", "flipp"),
        )
        conn = await asyncpg.connect(self.db_url)
        try:
            await conn.execute(
                "CALL sp_import_grocery_stores_batch_v2($1::jsonb, NULL);",
                json.dumps(stores),
            )
        finally:
            await conn.close()

    async def run_import_alltheplaces(self, chain_id: str, region_state: str = "CA", include_all_brands: bool = False) -> Dict[str, Any]:
        meta = await self.get_chain_metadata(chain_id)
        chain_key = meta["chain_id"]
        target_state = normalize_state(region_state)

        logger.info("Fetching store dataset for %s (spider: %s, region: %s)...", chain_key, meta["spider"], target_state)
        geojson = await self._fetch_geojson(meta["spider"])

        features = geojson.get("features", [])
        parsed_stores: List[ParsedStore] = []
        for feat in features:
            parsed = parse_geojson_feature(feat, chain_key, meta, target_state, include_all_brands)
            if parsed:
                parsed_stores.append(parsed)

        unique_stores = deduplicate_stores(parsed_stores)

        if not unique_stores:
            return {"chain_id": chain_key, "region": region_state, "imported_count": 0}

        await self._persist_stores(chain_key, meta, unique_stores)

        return {
            "chain_id": chain_key,
            "display_name": meta["display_name"],
            "region": region_state,
            "imported_count": len(unique_stores),
        }