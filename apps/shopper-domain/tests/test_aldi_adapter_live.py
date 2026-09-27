import asyncio
from datetime import datetime, timezone
import json
import os
import httpx
import redis.asyncio as redis

from src.ingestion.factory import DealAdapterFactory
from src.storage.deal_storage import PartitionedDealStorage


async def test_live_aldi_ingestion() -> None:
    postal_code = "90260"
    store_chain = "aldi"
    store_id = "aldi-90260"

    print("==================================================")
    print(f"Starting Live ALDI Ingestion Test for {store_chain} ({postal_code})")
    print("==================================================")

    # 1. Initialize PartitionedDealStorage and DealAdapterFactory
    r_client = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
    storage = PartitionedDealStorage(redis_client=r_client)

    try:
        async with httpx.AsyncClient() as http_client:
            factory = DealAdapterFactory(client=http_client)

            # 2 & 3. Target postal code "90260" with store_chain "aldi" and store_id "aldi-90260"
            # Retrieve the adapter from the factory and call get_normalized_deals
            adapter = factory.get_adapter(store_chain)

            # Discover flyer ID for logging / reporting
            flyers = []
            if hasattr(adapter, "fetch_flyers_by_postal_code"):
                flyers = await adapter.fetch_flyers_by_postal_code(postal_code)
            active_flyer_id = flyers[0].get("id") if flyers else "N/A"

            valid_from, valid_to, deals = await adapter.get_normalized_deals(
                postal_code=postal_code,
                store_id=store_id,
            )

        # 4. Assertions:
        # - Returned deals list is non-empty
        assert len(deals) > 0, "Expected non-empty list of deals"
        # - Each item has sale_price > 0
        for deal in deals:
            assert deal.sale_price > 0, f"Deal '{deal.product_name}' has invalid sale_price: {deal.sale_price}"

        # - Start and end dates are valid UTC datetimes
        assert isinstance(valid_from, datetime), "valid_from must be a datetime"
        assert isinstance(valid_to, datetime), "valid_to must be a datetime"
        assert valid_from.tzinfo is not None, "valid_from must be timezone-aware"
        assert valid_to.tzinfo is not None, "valid_to must be timezone-aware"

        valid_from_utc = valid_from.astimezone(timezone.utc)
        valid_to_utc = valid_to.astimezone(timezone.utc)
        assert valid_to_utc > valid_from_utc, f"valid_to ({valid_to_utc}) must be after valid_from ({valid_from_utc})"

        # 5. Print output:
        # - Discovered Aldi Flyer ID and validity window
        print(f"\nDiscovered Aldi Flyer ID: {active_flyer_id}")
        print(f"Validity Window: {valid_from.isoformat()} to {valid_to.isoformat()}")
        # - Total items extracted
        print(f"Total Items Extracted: {len(deals)}")
        # - Top 5 deals formatted as: [category] product_name -> $sale_price / pricing_unit (raw_promotion_text)
        print("\nTop 5 Deals:")
        for deal in deals[:5]:
            print(f"[{deal.category}] {deal.product_name} -> ${deal.sale_price:.2f} / {deal.pricing_unit} ({deal.raw_promotion_text})")

        # 6. Save deals using PartitionedDealStorage and assert retrieval from both Redis and local partition files
        deals_payload = [deal.model_dump(mode="json") for deal in deals]
        written_paths = await storage.save_deals(
            store_id=store_id,
            deals=deals_payload,
            valid_from=valid_from,
            valid_to=valid_to,
        )

        print(f"\nSuccessfully persisted {len(deals)} deals to local partitions:")
        for path in written_paths:
            print(f"  - {path}")

        # Assert local partition files exist and verify content
        assert len(written_paths) > 0, "Expected at least one partition file written"
        for path in written_paths:
            assert os.path.exists(path), f"Partition file does not exist: {path}"
            with open(path, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
                assert disk_data["store_id"] == store_id
                assert len(disk_data["deals"]) == len(deals)

        # Assert retrieval from Redis
        retrieved_redis = await storage.get_deals_for_stores([store_id])
        stored_deals_redis = retrieved_redis.get(store_id, [])
        print(f"Retrieved {len(stored_deals_redis)} deals from Redis cache for store '{store_id}'")
        assert len(stored_deals_redis) == len(deals), f"Expected {len(deals)} stored deals from Redis, got {len(stored_deals_redis)}"

        # Assert retrieval from local partition files fallback by clearing Redis key
        await r_client.delete(f"deals:store:{store_id}")
        retrieved_disk = await storage.get_deals_for_stores([store_id])
        stored_deals_disk = retrieved_disk.get(store_id, [])
        print(f"Retrieved {len(stored_deals_disk)} deals from local partition file fallback for store '{store_id}'")
        assert len(stored_deals_disk) == len(deals), f"Expected {len(deals)} stored deals from local partition files, got {len(stored_deals_disk)}"

    finally:
        await r_client.aclose()

    print("\nALL ALDI LIVE INGESTION CHECKS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(test_live_aldi_ingestion())
