# apps/shopper-domain/src/services/alltheplaces_importer.py
from typing import Any, Dict

import httpx

try:
    from src.services.store_import_base import StoreImporterBase
except ImportError:
    from .store_import_base import StoreImporterBase

ALL_THE_PLACES_BASE = "https://data.alltheplaces.xyz/runs/latest/output"
ATP_PREFIX = "atp:"


class AllThePlacesImporter(StoreImporterBase):
    def __init__(self, source: str):
        if not source.startswith(ATP_PREFIX):
            raise ValueError(f"AllThePlaces source must start with '{ATP_PREFIX}': {source!r}")
        self.spider = source[len(ATP_PREFIX):].strip()
        if not self.spider:
            raise ValueError("AllThePlaces source is missing a spider name")

    async def fetch_geojson(self) -> Dict[str, Any]:
        url = f"{ALL_THE_PLACES_BASE}/{self.spider}.geojson"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
