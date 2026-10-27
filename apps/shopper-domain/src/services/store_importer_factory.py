# apps/shopper-domain/src/services/store_importer_factory.py
try:
    from src.services.store_import_base import StoreImporterBase
    from src.services.alltheplaces_importer import AllThePlacesImporter, ATP_PREFIX
    from src.services.geojson_file_importer import GeoJsonFileImporter, GEOJSON_FILE_PREFIX
except ImportError:
    from .store_import_base import StoreImporterBase
    from .alltheplaces_importer import AllThePlacesImporter, ATP_PREFIX
    from .geojson_file_importer import GeoJsonFileImporter, GEOJSON_FILE_PREFIX

import logging

logger = logging.getLogger(__name__)


def create_store_importer(spider_name: str) -> StoreImporterBase:
    if spider_name.startswith(GEOJSON_FILE_PREFIX):
        return GeoJsonFileImporter(spider_name)
    if spider_name.startswith(ATP_PREFIX):
        return AllThePlacesImporter(spider_name)
    # Legacy values are bare AllThePlaces spider names (e.g. "kroger_us").
    if ":" not in spider_name and spider_name.strip():
        return AllThePlacesImporter(f"{ATP_PREFIX}{spider_name.strip()}")
    raise ValueError(f"Unsupported store import source: {spider_name!r}")
