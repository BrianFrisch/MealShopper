import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Optional

# Ensure apps/shopper-domain is in sys.path
shopper_dir = str(Path(__file__).resolve().parent.parent)
if shopper_dir not in sys.path:
    sys.path.insert(0, shopper_dir)

from src.ingestion.adapters.base import BaseDealAdapter
from src.ingestion.adapters.flipp_adapter import FlippAdapter
from src.ingestion.adapters.aldi_adapter import AldiAdapter
from src.ingestion.factory import DealAdapterFactory
from src.ingestion.models import NormalizedDealItem
# from src.storage.deal_storage import PartitionedDealStorage


class DummyRedis:
    """Mock in-memory Redis client for testing storage integration."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self._store.get(k) for k in keys]

    async def aclose(self) -> None:
        pass


import pytest

@pytest.mark.anyio
async def test_factory_registry_and_lookup():
    chain_metadata = [
        {"chain_id": "ralphs", "display_name": "Ralphs", "adapter_name": "ralphs"},
        {"chain_id": "aldi", "display_name": "ALDI", "adapter_name": "aldi"},
        {"chain_id": "vons", "display_name": "Vons", "adapter_name": "vons"},
    ]

    class MockChainService:
        async def get_all_chains(self) -> list[dict[str, str]]:
            return chain_metadata

        async def get_chain_metadata(self, chain_id: str) -> dict[str, str]:
            for metadata in chain_metadata:
                if metadata["chain_id"] == chain_id:
                    return metadata
            raise ValueError(f"Unsupported chain: {chain_id}")

    factory = DealAdapterFactory(chain_service=MockChainService())

    # The adapter registry is populated using the injected chain service.
    chains = factory.supported_chains()
    assert chains == []
    await factory.load_chains_from_db()
    chains = factory.supported_chains()
    assert "ralphs" in chains
    assert "aldi" in chains

    # Case-insensitive resolution
    ralphs_adapter = factory.get_adapter("Ralphs")
    assert isinstance(ralphs_adapter, FlippAdapter)
    assert ralphs_adapter.default_merchant == "Ralphs"

    ralphs_lower = factory.get_adapter("ralphs")
    assert ralphs_lower is ralphs_adapter

    aldi_adapter = factory.get_adapter("ALDI")
    assert isinstance(aldi_adapter, AldiAdapter)

    aldi_lower = factory.get_adapter("aldi")
    assert aldi_lower is aldi_adapter

    # Unsupported chain returns None
    assert factory.get_adapter("trader_joes") is None

    # Empty chain returns None
    assert factory.get_adapter("") is None

    # Register custom adapter
    class CustomAdapter(BaseDealAdapter):
        async def fetch_flyer_metadata(
            self, postal_code: str, chain_id: Optional[str] = None, **kwargs: Any
        ) -> tuple[Optional[str], datetime, datetime]:
            now = datetime.now(timezone.utc)
            return "custom-flyer-1", now, now

        async def fetch_raw_items(self, flyer_id: Any) -> list[dict[str, Any]]:
            return []

        def extract_product_name(self, item: dict[str, Any]) -> str:
            return ""

        def extract_pricing(
            self, item: dict[str, Any]
        ) -> tuple[Optional[float], Optional[float], str]:
            return None, None, "each"

        def extract_raw_category(self, item: dict[str, Any]) -> str:
            return ""

        async def get_normalized_deals(
            self,
            postal_code: str,
            store_id: str,
            merchant_name: str | None = None,
            **kwargs: Any,
        ) -> tuple[datetime, datetime, list[NormalizedDealItem]]:
            now = datetime.now(timezone.utc)
            return now, now, []

    custom = CustomAdapter()
    factory.register_adapter("custom_store", custom)
    assert "custom_store" in factory.supported_chains()
    assert factory.get_adapter("CUSTOM_STORE") is custom

    chain_metadata.append({
        "chain_id": "sprouts",
        "display_name": "Sprouts Farmers Market",
        "adapter_name": "sprouts",
    })
    sprouts_adapter = await factory.get_or_load_adapter("sprouts")
    assert isinstance(sprouts_adapter, FlippAdapter)
    assert sprouts_adapter.default_merchant == "Sprouts Farmers Market"

    await factory.close()
    print("test_factory_registry_and_lookup passed!")


# async def test_fetch_and_persist_ralphs_and_aldi():
#     def mock_handler(request: httpx.Request) -> httpx.Response:
#         url_str = str(request.url)
#         if "/flipp/flyers/" in url_str and "/items" in url_str:
#             if "101" in url_str:
#                 # Ralphs flyer items
#                 return httpx.Response(
#                     200,
#                     json=[
#                         {
#                             "name": "Fresh Heritage Farm Boneless Chicken Breast",
#                             "current_price": 1.99,
#                             "sale_story": "$1.99 / lb",
#                             "category": "Meat & Seafood",
#                         },
#                         {
#                             "name": "Hass Avocados Large",
#                             "current_price": 0.75,
#                             "sale_story": "4 for $3.00",
#                             "category": "Produce",
#                         },
#                     ],
#                 )
#             elif "202" in url_str:
#                 # Aldi flyer items
#                 return httpx.Response(
#                     200,
#                     json=[
#                         {
#                             "name": "Fresh USDA Choice Black Angus Beef Chuck Roast",
#                             "sale_story": "Fresh Meat Special $4.99 per lb",
#                             "current_price": 4.99,
#                         },
#                         {
#                             "name": "Hass Avocados",
#                             "sale_story": "49¢ each",
#                             "current_price": "49¢",
#                         },
#                     ],
#                 )
#         elif "/flipp/flyers" in url_str:
#             return httpx.Response(
#                 200,
#                 json={
#                     "flyers": [
#                         {
#                             "id": 101,
#                             "merchant": "Ralphs",
#                             "valid_from": "2026-09-23T07:00:00Z",
#                             "valid_to": "2026-09-30T06:59:59Z",
#                         },
#                         {
#                             "id": 202,
#                             "merchant": "ALDI",
#                             "valid_from": "2026-09-23T07:00:00Z",
#                             "valid_to": "2026-09-30T06:59:59Z",
#                         },
#                     ]
#                 },
#             )
#         return httpx.Response(404)

#     transport = httpx.MockTransport(mock_handler)
#     mock_redis = DummyRedis()

#     with tempfile.TemporaryDirectory() as temp_dir:
#         storage = PartitionedDealStorage(redis_client=mock_redis, base_storage_dir=temp_dir)  # type: ignore

#         async with httpx.AsyncClient(transport=transport) as client:
#             factory = DealAdapterFactory(client=client)

#             # 1. Test Ralphs fetch_and_persist
#             ralphs_summary = await factory.fetch_and_persist(
#                 store_chain="Ralphs",
#                 store_id="ralphs-90260",
#                 postal_code="90260",
#                 storage=storage,
#             )

#             assert ralphs_summary["store_chain"] == "ralphs"
#             assert ralphs_summary["store_id"] == "ralphs-90260"
#             assert ralphs_summary["deal_count"] == 2
#             assert len(ralphs_summary["partitions"]) > 0
#             for partition_path in ralphs_summary["partitions"]:
#                 assert os.path.exists(partition_path)
#                 with open(partition_path, "r", encoding="utf-8") as f:
#                     data = json.load(f)
#                     assert data["store_id"] == "ralphs-90260"
#                     assert len(data["deals"]) == 2

#             # 2. Test Aldi fetch_and_persist
#             aldi_summary = await factory.fetch_and_persist(
#                 store_chain="aldi",
#                 store_id="aldi-60601",
#                 postal_code="60601",
#                 storage=storage,
#             )

#             assert aldi_summary["store_chain"] == "aldi"
#             assert aldi_summary["store_id"] == "aldi-60601"
#             assert aldi_summary["deal_count"] == 2
#             assert len(aldi_summary["partitions"]) > 0

#             # 3. Test standalone module-level fetch_and_persist
#             func_summary = await fetch_and_persist(
#                 store_chain="ALDI",
#                 store_id="aldi-func-test",
#                 postal_code="60601",
#                 storage=storage,
#                 client=client,
#             )
#             assert func_summary["store_chain"] == "aldi"
#             assert func_summary["store_id"] == "aldi-func-test"
#             assert func_summary["deal_count"] == 2

#     print("test_fetch_and_persist_ralphs_and_aldi passed!")


if __name__ == "__main__":
    asyncio.run(test_factory_registry_and_lookup())
    # asyncio.run(test_fetch_and_persist_ralphs_and_aldi())
    print("All DealAdapterFactory tests completed successfully!")
