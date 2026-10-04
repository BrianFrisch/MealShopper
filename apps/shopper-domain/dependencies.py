from typing import Optional
import redis.asyncio as redis

from config import REDIS_URL, SHOPPER_DATABASE_URL, DEALS_PATH
from geo_service import StoreRepository
from deal_service import DealRepository
from src.storage.deal_storage import PartitionedDealStorage
from src.ingestion.factory import DealAdapterFactory

redis_pool: Optional[redis.ConnectionPool] = None
store_repo = StoreRepository(SHOPPER_DATABASE_URL)
deal_repo = DealRepository(DEALS_PATH)


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
    factory = DealAdapterFactory()
    await factory.load_chains_from_db()
    return factory


def get_store_repository() -> StoreRepository:
    return store_repo


def get_deal_repository() -> DealRepository:
    return deal_repo
