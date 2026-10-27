# apps/shopper-domain/src/services/store_import_base.py
from abc import ABC, abstractmethod
from typing import Any, Dict


class StoreImporterBase(ABC):
    """Base class for store data sources."""

    @abstractmethod
    async def fetch_geojson(self) -> Dict[str, Any]:
        """Return a GeoJSON FeatureCollection dict (with a "features" list)."""
