# apps/shopper-domain/src/services/geojson_file_importer.py
import asyncio
import json
from pathlib import Path
from typing import Any, Dict

try:
    from src.services.store_import_base import StoreImporterBase
except ImportError:
    from .store_import_base import StoreImporterBase

GEOJSON_FILE_PREFIX = "geojsonfile:"


class GeoJsonFileImporter(StoreImporterBase):
    """Reads a GeoJSON file from local disk; the path is relative to the working directory."""

    def __init__(self, source: str):
        if not source.startswith(GEOJSON_FILE_PREFIX):
            raise ValueError(
                f"GeoJSON file source must start with '{GEOJSON_FILE_PREFIX}': {source!r}"
            )
        raw_path = source[len(GEOJSON_FILE_PREFIX):].strip()
        self.banner_names: tuple[str, ...] = ()
        separator = raw_path.rfind(":")
        is_drive_separator = (
            separator == 1 and raw_path[0].isalpha() and raw_path[2:3] in ("/", "\\")
        )
        if separator >= 0 and not is_drive_separator:
            raw_path, raw_banners = raw_path[:separator].strip(), raw_path[separator + 1:]
            self.banner_names = tuple(name.strip() for name in raw_banners.split("|"))
            if any(not any(char.isalnum() for char in name) for name in self.banner_names):
                raise ValueError("GeoJSON banner names must not be empty")
        if not raw_path:
            raise ValueError("GeoJSON file source is missing a file path")
        # A leading slash (e.g. "/data/x.geojson") still means relative to the working directory.
        self.path = Path(raw_path.lstrip("/\\"))

    def _read(self) -> Dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    async def fetch_geojson(self) -> Dict[str, Any]:
        return await asyncio.to_thread(self._read)
