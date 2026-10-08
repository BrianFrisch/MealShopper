import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import tempfile
from typing import Any, Optional

# Ensure apps/shopper-domain is in sys.path
shopper_dir = str(Path(__file__).resolve().parent.parent)
if shopper_dir not in sys.path:
    sys.path.insert(0, shopper_dir)

import httpx
from fastapi.testclient import TestClient

from main import app, ingest_store_on_demand, get_deal_storage, get_deal_adapter_factory
from src.ingestion.adapters.base import BaseDealAdapter
from src.ingestion.factory import DealAdapterFactory
from src.ingestion.models import NormalizedDealItem
from src.storage.deal_storage import PartitionedDealStorage


import pytest

class MockRedis:
    def __init__(self):
        self._store: dict[str, str] = {}
        self._zsets: dict[str, dict[str, float]] = {}
        self.lock_attempts = []
        self.deleted_keys = []

    async def set(self, key: str, value: str, nx: bool = False, ex: Optional[int] = None) -> bool:
        self.lock_attempts.append((key, value, nx, ex))
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True

    async def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    async def mget(self, keys: list[str]) -> list[Optional[str]]:
        return [self._store.get(k) for k in keys]

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        if key not in self._zsets:
            self._zsets[key] = {}
        self._zsets[key].update(mapping)
        return len(mapping)

    async def zrangebyscore(self, key: str, min: float = 0.0, max: float = float("inf")) -> list[str]:
        if key not in self._zsets:
            return []
        items = [(member, score) for member, score in self._zsets[key].items() if min <= score <= max]
        items.sort(key=lambda x: x[1])
        return [member for member, score in items]

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            self.deleted_keys.append(k)
            if k in self._store:
                del self._store[k]
                count += 1
            if k in self._zsets:
                del self._zsets[k]
                count += 1
        return count

    async def aclose(self) -> None:
        pass


class MockAdapter(BaseDealAdapter):
    def __init__(self, deals: Optional[list[NormalizedDealItem]] = None):
        self.deals = deals if deals is not None else []
        self.called_with = []

    async def fetch_flyer_metadata(
        self, postal_code: str, chain_id: Optional[str] = None, **kwargs: Any
    ) -> tuple[Optional[str], datetime, datetime]:
        now = datetime.now(timezone.utc)
        return "mock-flyer-1", now, now + timedelta(days=7)

    async def fetch_raw_items(self, flyer_id: Any) -> list[dict[str, Any]]:
        return []

    def extract_product_name(self, item: dict[str, Any]) -> str:
        return item.get("item_name", "")

    def extract_pricing(
        self, item: dict[str, Any]
    ) -> tuple[Optional[float], Optional[float], str]:
        return item.get("deal_price"), item.get("original_price"), item.get("unit", "each")

    def extract_raw_category(self, item: dict[str, Any]) -> str:
        return item.get("category", "Pantry")

    async def get_normalized_deals(
        self, postal_code: str, store_id: str, merchant_name: Optional[str] = None, **kwargs: Any
    ) -> tuple[datetime, datetime, list[NormalizedDealItem]]:
        self.called_with.append((postal_code, store_id, merchant_name))
        now = datetime.now(timezone.utc)
        return now, now + timedelta(days=7), self.deals


@pytest.mark.anyio
async def test_ingest_store_on_demand_lock_acquired():
    mock_redis = MockRedis()
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = PartitionedDealStorage(redis_client=mock_redis, base_storage_dir=temp_dir)  # type: ignore

        deal_item = NormalizedDealItem(
            deal_id="ralphs-101_1",
            store_id="ralphs-101",
            store_name="Ralphs",
            item_name="Chicken Breast",
            clean_name="chicken breast",
            normalized_category="Meat",
            deal_price=2.99,
            original_price=4.99,
            currency="USD",
            unit="lb",
            value_score=8.5,
            raw_promotion_text="$2.99/lb",
            valid_from=datetime.now(timezone.utc),
            valid_to=datetime.now(timezone.utc) + timedelta(days=7),
        )
        mock_adapter = MockAdapter(deals=[deal_item])
        factory = DealAdapterFactory()
        factory.register_adapter("ralphs", mock_adapter)

        result = await ingest_store_on_demand(
            store_id="ralphs-101",
            chain="ralphs",
            postal_code="90260",
            storage=storage,
            factory=factory,
        )

        # Lock was checked with nx=True and ex=20
        assert ("lock:ingest:ralphs-101", "1", True, 20) in mock_redis.lock_attempts
        # Lock was released
        assert "lock:ingest:ralphs-101" in mock_redis.deleted_keys
        # Adapter was invoked
        assert len(mock_adapter.called_with) == 1
        assert mock_adapter.called_with[0] == ("90260", "ralphs-101", "ralphs")
        # Deals were saved and returned
        assert len(result) == 1
        assert result[0]["item_name"] == "Chicken Breast"
        assert result[0]["deal_price"] == 2.99

        # Verify storage now has the deals
        stored = await storage.get_deals_for_stores(["ralphs-101"])
        assert len(stored.get("ralphs-101", [])) == 1

        await factory.close()
    print("test_ingest_store_on_demand_lock_acquired passed!")


@pytest.mark.anyio
async def test_ingest_store_on_demand_lock_held_by_another():
    mock_redis = MockRedis()
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = PartitionedDealStorage(redis_client=mock_redis, base_storage_dir=temp_dir)  # type: ignore

        # Pre-set the lock key to simulate another process holding it
        await mock_redis.set("lock:ingest:ralphs-101", "1")

        # In parallel, populate storage after a short sleep to simulate the other request finishing
        async def mock_other_worker():
            await asyncio.sleep(0.1)
            now = datetime.now(timezone.utc)
            await storage.save_deals(
                store_id="ralphs-101",
                deals=[{"deal_id": "d1", "item_name": "Apples", "deal_price": 1.50}],
                valid_from=now,
                valid_to=now + timedelta(days=7),
            )

        factory = DealAdapterFactory()
        task = asyncio.create_task(mock_other_worker())

        result = await ingest_store_on_demand(
            store_id="ralphs-101",
            chain="ralphs",
            postal_code="90260",
            storage=storage,
            factory=factory,
        )
        await task

        # Returns deals retrieved after sleep
        assert len(result) == 1
        assert result[0]["item_name"] == "Apples"

        await factory.close()
    print("test_ingest_store_on_demand_lock_held_by_another passed!")


def test_get_store_deals_endpoint():
    mock_redis = MockRedis()
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = PartitionedDealStorage(redis_client=mock_redis, base_storage_dir=temp_dir)  # type: ignore

        deal_item = NormalizedDealItem(
            deal_id="ralphs-101_1",
            store_id="ralphs-101",
            store_name="Ralphs",
            item_name="Chicken Breast",
            clean_name="chicken breast",
            normalized_category="Meat",
            deal_price=2.99,
            original_price=4.99,
            currency="USD",
            unit="lb",
            value_score=8.5,
            raw_promotion_text="$2.99/lb",
            valid_from=datetime.now(timezone.utc),
            valid_to=datetime.now(timezone.utc) + timedelta(days=7),
        )
        mock_adapter = MockAdapter(deals=[deal_item])
        factory = DealAdapterFactory()
        factory.register_adapter("ralphs", mock_adapter)

        empty_adapter = MockAdapter(deals=[])
        factory.register_adapter("empty_chain", empty_adapter)

        app.dependency_overrides[get_deal_storage] = lambda: storage
        app.dependency_overrides[get_deal_adapter_factory] = lambda: factory

        client = TestClient(app)

        # 1. 404 when no deals and no postal_code/chain supplied
        res1 = client.get("/v1/deals/stores/ralphs-101")
        assert res1.status_code == 404

        # 2. On-demand ingestion triggered when postal_code and chain supplied
        res2 = client.get("/v1/deals/stores/ralphs-101?postal_code=90260&chain=ralphs")
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2["deals"]) == 1
        assert data2["deals"][0]["item_name"] == "Chicken Breast"

        # 3. Subsequent request uses cached deals without re-invoking adapter
        call_count_before = len(mock_adapter.called_with)
        res3 = client.get("/v1/deals/stores/ralphs-101")
        assert res3.status_code == 200
        assert len(mock_adapter.called_with) == call_count_before

        # 4. 404 when on-demand ingestion yields 0 items
        res4 = client.get("/v1/deals/stores/store-empty?postal_code=90260&chain=empty_chain")
        assert res4.status_code == 404

        app.dependency_overrides.clear()
    print("test_get_store_deals_endpoint passed!")


if __name__ == "__main__":
    asyncio.run(test_ingest_store_on_demand_lock_acquired())
    asyncio.run(test_ingest_store_on_demand_lock_held_by_another())
    test_get_store_deals_endpoint()
    print("All on-demand ingestion tests passed successfully!")
