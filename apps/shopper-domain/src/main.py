import sys
from pathlib import Path

# Add shopper-domain root directory to sys.path if not present
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from main import (
    app,
    deal_repo,
    get_deal_adapter_factory,
    get_deal_repository,
    get_deal_storage,
    get_store_deals,
    get_store_repository,
    health_check,
    ingest_store_on_demand,
    lifespan,
    store_repo,
)

__all__ = [
    "app",
    "lifespan",
    "health_check",
    "ingest_store_on_demand",
    "get_store_deals",
    "get_deal_storage",
    "get_deal_adapter_factory",
    "get_store_repository",
    "get_deal_repository",
    "store_repo",
    "deal_repo",
]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8001, reload=True)
