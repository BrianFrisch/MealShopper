import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

# Ensure shopper-domain root directory is in sys.path
_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

from config import REDIS_URL
import dependencies
from dependencies import (
    deal_repo,
    get_deal_adapter_factory,
    get_deal_repository,
    get_deal_storage,
    get_store_repository,
    store_repo,
)
from src.api.routers.admin import router as admin_router
from src.api.routers.circulars import get_store_deals, router as circulars_router
from src.api.routers.deals import router as deals_router
from src.api.routers.stores import router as stores_router
from src.services.on_demand_ingestion import ingest_store_on_demand

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Redis connection pool for Shopper Domain at %s", REDIS_URL)
    pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    dependencies.set_redis_pool(pool)
    yield
    if dependencies.redis_pool:
        await dependencies.redis_pool.disconnect()


app = FastAPI(title="MealShopper - Shopper Domain Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


# Mount domain routers
app.include_router(stores_router)
app.include_router(deals_router)
app.include_router(circulars_router)
app.include_router(admin_router)

# Compatibility exports
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

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)