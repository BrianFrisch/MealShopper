import asyncio
from typing import Optional
import redis.asyncio as redis

from config import REDIS_URL, SHOPPER_DATABASE_URL
from geo_service import StoreRepository
from src.storage.deal_storage import PartitionedDealStorage
from src.ingestion.factory import DealAdapterFactory

redis_pool: Optional[redis.ConnectionPool] = None
adapter_factory: Optional[DealAdapterFactory] = None
_adapter_factory_lock = asyncio.Lock()
store_repo = StoreRepository(SHOPPER_DATABASE_URL)


def get_redis_pool() -> redis.ConnectionPool:
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    return redis_pool


def set_redis_pool(pool: Optional[redis.ConnectionPool]) -> None:
    global redis_pool
    redis_pool = pool


def get_deal_storage() -> PartitionedDealStorage:
    pool = get_redis_pool()
    client = redis.Redis(connection_pool=pool)
    return PartitionedDealStorage(redis_client=client)


async def get_deal_adapter_factory() -> DealAdapterFactory:
    global adapter_factory
    if adapter_factory is not None and adapter_factory.supported_chains():
        return adapter_factory

    async with _adapter_factory_lock:
        if adapter_factory is None:
            adapter_factory = DealAdapterFactory()
        if not adapter_factory.supported_chains():
            await adapter_factory.load_chains_from_db()
        return adapter_factory


def get_store_repository() -> StoreRepository:
    return store_repo
