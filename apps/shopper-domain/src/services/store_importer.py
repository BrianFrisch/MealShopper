# apps/shopper-domain/src/services/store_importer.py
import json
import logging
import re
from typing import Any, Dict, Optional
import asyncpg # type: ignore
import httpx

logger = logging.getLogger(__name__)

ALL_THE_PLACES_BASE = "https://data.alltheplaces.xyz/runs/latest/output"

CHAIN_METADATA = {
    "ralphs": {"display_name": "Ralphs", "adapter_name": "ralphs", "spider": "kroger_us"},
    "aldi": {"display_name": "ALDI", "adapter_name": "aldi", "spider": "aldi_sud_us"},
    "vons": {"display_name": "Vons", "adapter_name": "vons", "spider": "vons"},
    "trader-joes": {"display_name": "Trader Joe's", "adapter_name": "trader-joes", "spider": "trader_joes"},
}


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


class StoreImportService:
    def __init__(self, db_url: str):
        self.db_url = db_url

    async def run_import_alltheplaces(self, chain_id: str, region_state: str = "CA") -> Dict[str, Any]:
        chain_key = chain_id.strip().lower()
        meta = CHAIN_METADATA.get(chain_key)
        if not meta:
            raise ValueError(f"Unsupported chain: {chain_id}")

        spider_file = f"{meta['spider']}.geojson"
        url = f"{ALL_THE_PLACES_BASE}/{spider_file}"
        logger.info("Fetching store dataset from %s (region: %s)...", url, region_state)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            geojson = resp.json()

        features = geojson.get("features", [])
        
        target_state = region_state.strip().upper()
        if target_state in ("CALIFORNIA", "CA"):
            target_state = "CA"

        # Temporary dictionary to deduplicate locations by exact coordinates
        # This prevents fuel centers (store 12009) from duplicating main stores (store 120)
        unique_locations: Dict[str, Dict[str, Any]] = {}
        
        target_banner = meta["display_name"].lower()

        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            if not geom:
                continue
            coords = geom.get("coordinates", [])
            if not coords or len(coords) < 2:
                continue

            lon, lat = float(coords[0]), float(coords[1])
            store_state = (
                props.get("addr:state") or props.get("state") or props.get("addr:province") or ""
            ).strip().upper()

            if target_state and store_state and store_state != target_state:
                continue

            # 1. Strict Banner Enforcement (Filters Food 4 Less out of Ralphs)
            brand = (props.get("brand") or props.get("name") or "").strip()
            if target_banner not in brand.lower():
                continue
            
            # Filter out explicit fuel stations if tagged in name
            if "fuel" in brand.lower() or "gas" in brand.lower():
                continue

            raw_num = props.get("ref") or props.get("store_number") or props.get("@id")
            store_number = clean_store_number(raw_num, str(feat.get("id", "0")))
            store_id = f"{chain_key}-{store_number}"

            # 2. Aggressive Address Resolution
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

            parsed_store = {
                "store_id": store_id,
                "chain_id": chain_key,
                "store_number": store_number,
                "store_name": brand or f"{meta['display_name']} #{store_number}",
                "street_address": street.strip(),
                "city": city.strip(),
                "state_province": store_state or target_state or "CA",
                "postal_code": str(postal_code).strip(),
                "longitude": lon,
                "latitude": lat,
            }

            # 3. Suffix / Coordinate Deduplication
            # Round coordinates slightly to group main store and fuel center in same parking lot
            coord_key = f"{round(lon, 4)}_{round(lat, 4)}"
            
            # If we already have a store at this coordinate, prefer the one with the shorter store number
            # (e.g., store 70300120 wins over fuel center 7030012009)
            if coord_key in unique_locations:
                existing = unique_locations[coord_key]
                if len(store_number) < len(existing["store_number"]):
                    unique_locations[coord_key] = parsed_store
            else:
                unique_locations[coord_key] = parsed_store

        store_list = list(unique_locations.values())

        if not store_list:
            return {"chain_id": chain_key, "region": region_state, "imported_count": 0}

        # 4. Persist
        conn = await asyncpg.connect(self.db_url)
        try:
            await conn.execute(
                "CALL sp_upsert_grocery_chain($1, $2, $3, $4);",
                chain_key,
                meta["display_name"],
                meta["adapter_name"],
                "flipp",
            )
            await conn.execute(
                "CALL sp_import_grocery_stores_batch_v2($1::jsonb, NULL);",
                json.dumps(store_list),
            )
            
            return {
                "chain_id": chain_key,
                "display_name": meta["display_name"],
                "region": region_state,
                "imported_count": len(store_list),
            }
        finally:
            await conn.close()