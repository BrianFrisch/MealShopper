import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
import pytest

_shopper_domain_dir = str(Path(__file__).resolve().parent.parent)
if _shopper_domain_dir not in sys.path:
    sys.path.insert(0, _shopper_domain_dir)

from src.storage.deal_storage import PartitionedDealStorage, normalize_category_key


class FakeRedis:
    """In-memory Redis mock supporting string keys, mget, zadd, zrangebyscore, expire."""

    def __init__(self):
        self.strings: dict[str, str] = {}
        self.zsets: dict[str, dict[str, float]] = {}

    async def get(self, key: str) -> Any:
        return self.strings.get(key)

    async def set(self, key: str, value: str, ex: Any = None) -> bool:
        self.strings[key] = value
        return True

    async def mget(self, keys: list[str]) -> list[Any]:
        return [self.strings.get(k) for k in keys]

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        if key not in self.zsets:
            self.zsets[key] = {}
        self.zsets[key].update(mapping)
        return len(mapping)

    async def zrangebyscore(self, key: str, min: float = 0.0, max: float = float("inf")) -> list[str]:
        if key not in self.zsets:
            return []
        items = [(member, score) for member, score in self.zsets[key].items() if min <= score <= max]
        items.sort(key=lambda x: x[1])
        return [member for member, score in items]

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self.strings:
                del self.strings[k]
                count += 1
            if k in self.zsets:
                del self.zsets[k]
                count += 1
        return count


@pytest.mark.anyio
async def test_redis_deal_caching_and_category_indexing(tmp_path):
    fake_redis = FakeRedis()
    storage = PartitionedDealStorage(redis_client=fake_redis, base_storage_dir=str(tmp_path))

    store_id = "ralphs-101"
    valid_from = datetime(2026, 10, 1, tzinfo=timezone.utc)
    valid_to = datetime(2026, 10, 8, tzinfo=timezone.utc)

    # Multi-item split deals
    split_deal_0 = {
        "deal_id": "ralphs-101_11111_0",
        "store_id": store_id,
        "store_name": "Ralphs",
        "item_name": "Bone-in New York Steak",
        "clean_name": "bone-in new york steak",
        "normalized_category": "Meat & Poultry",
        "deal_price": 8.99,
        "unit": "lb",
        "valid_from": valid_from.isoformat(),
        "valid_to": valid_to.isoformat(),
    }
    split_deal_1 = {
        "deal_id": "ralphs-101_11111_1",
        "store_id": store_id,
        "store_name": "Ralphs",
        "item_name": "Jumbo Peeled Shrimp",
        "clean_name": "jumbo peeled shrimp",
        "normalized_category": "Seafood",
        "deal_price": 8.99,
        "unit": "lb",
        "valid_from": valid_from.isoformat(),
        "valid_to": valid_to.isoformat(),
    }
    produce_deal = {
        "deal_id": "ralphs-101_22222",
        "store_id": store_id,
        "store_name": "Ralphs",
        "item_name": "Gala Apples",
        "clean_name": "gala apples",
        "normalized_category": "Produce",
        "deal_price": 1.49,
        "unit": "lb",
        "valid_from": valid_from.isoformat(),
        "valid_to": valid_to.isoformat(),
    }

    all_deals = [split_deal_0, split_deal_1, produce_deal]

    # Save deals to Redis & disk
    await storage.save_deals(
        flyer_id=store_id,
        deals=all_deals,
        valid_from=valid_from,
        valid_to=valid_to,
    )

    # 1. Verify deals:data:{deal_id} entries
    assert f"deals:data:{split_deal_0['deal_id']}" in fake_redis.strings
    assert f"deals:data:{split_deal_1['deal_id']}" in fake_redis.strings
    assert f"deals:data:{produce_deal['deal_id']}" in fake_redis.strings

    # 2. Verify category query for "Meat & Poultry"
    meat_deals = await storage.get_deals_by_category(store_id, "Meat & Poultry")
    assert len(meat_deals) == 1
    assert meat_deals[0]["deal_id"] == "ralphs-101_11111_0"
    assert meat_deals[0]["clean_name"] == "bone-in new york steak"

    # 3. Verify category query for "Seafood" (no cross-contamination from meat)
    seafood_deals = await storage.get_deals_by_category(store_id, "Seafood")
    assert len(seafood_deals) == 1
    assert seafood_deals[0]["deal_id"] == "ralphs-101_11111_1"
    assert seafood_deals[0]["clean_name"] == "jumbo peeled shrimp"

    # 4. Verify category query for "Produce"
    produce_deals = await storage.get_deals_by_category(store_id, "Produce")
    assert len(produce_deals) == 1
    assert produce_deals[0]["deal_id"] == "ralphs-101_22222"
    assert produce_deals[0]["clean_name"] == "gala apples"


# def test_postgres_sql_migration_syntax():
#     """Verify Postgres table and procedure files exist and contain valid length and ON CONFLICT statements."""
#     table_sql_path = Path(__file__).resolve().parent.parent / "Infrastructure" / "postgres" / "init" / "01_tables" / "003_grocery_deal.sql"
#     sp_upsert_path = Path(__file__).resolve().parent.parent / "Infrastructure" / "postgres" / "init" / "03_procedures" / "007_sp_upsert_grocery_deal.sql"
#     sp_batch_path = Path(__file__).resolve().parent.parent / "Infrastructure" / "postgres" / "init" / "03_procedures" / "008_sp_import_grocery_deals_batch.sql"

#     assert table_sql_path.exists()
#     assert sp_upsert_path.exists()
#     assert sp_batch_path.exists()

#     table_content = table_sql_path.read_text(encoding="utf-8")
#     assert "deal_id VARCHAR(128) PRIMARY KEY" in table_content

#     sp_upsert_content = sp_upsert_path.read_text(encoding="utf-8")
#     assert "p_deal_id VARCHAR(128)" in sp_upsert_content
#     assert "ON CONFLICT (deal_id) DO UPDATE SET" in sp_upsert_content

#     sp_batch_content = sp_batch_path.read_text(encoding="utf-8")
#     assert "(elem->>'deal_id')::VARCHAR(128) AS deal_id" in sp_batch_content
#     assert "ON CONFLICT (deal_id) DO UPDATE SET" in sp_batch_content
