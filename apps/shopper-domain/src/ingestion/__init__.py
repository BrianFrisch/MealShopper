from .models import (
    CoordinatesDto,
    NormalizedDealItem,
    RegionContextDto,
    TopDealsResponse,
    clean_product_name,
)
from .adapters.base import BaseDealAdapter
from .adapters.flipp_adapter import FlippAdapter
from .adapters.aldi_adapter import AldiAdapter
from .factory import DealAdapterFactory

__all__ = [
    "CoordinatesDto",
    "RegionContextDto",
    "TopDealsResponse",
    "NormalizedDealItem",
    "clean_product_name",
    "BaseDealAdapter",
    "FlippAdapter",
    "AldiAdapter",
    "DealAdapterFactory",
]

