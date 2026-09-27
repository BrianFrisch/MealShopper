from .models import NormalizedDealItem, clean_product_name
from .adapters.base import BaseDealAdapter
from .adapters.flipp_adapter import FlippAdapter
from .adapters.aldi_adapter import AldiAdapter
from .factory import DealAdapterFactory, fetch_and_persist

__all__ = [
    "NormalizedDealItem",
    "clean_product_name",
    "BaseDealAdapter",
    "FlippAdapter",
    "AldiAdapter",
    "DealAdapterFactory",
    "fetch_and_persist",
]

