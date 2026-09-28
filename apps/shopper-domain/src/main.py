import sys
from pathlib import Path

# Add shopper-domain root directory to sys.path if not present
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from main import *
from main import (
    ingest_store_on_demand,
    get_store_deals,
    get_deal_adapter_factory,
    get_deal_storage,
)
