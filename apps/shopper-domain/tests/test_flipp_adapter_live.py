import asyncio
from datetime import datetime, timezone
import httpx
import redis.asyncio as redis

from src.ingestion.adapters.flipp_adapter import FlippAdapter
from src.storage.deal_storage import PartitionedDealStorage


async def test_live_flipp_ingestion() -> None:
    postal_code = "90260"
    merchant_name = "Ralphs"
    store_id = "ralphs-90260"

    print("==================================================")
    print(f"Starting Live Flipp Ingestion Test for {merchant_name} ({postal_code})")
    print("==================================================")

    # 1 & 2. Instantiate FlippAdapter using httpx.AsyncClient
    async with httpx.AsyncClient() as http_client:
        adapter = FlippAdapter(client=http_client)

        # Discover flyers to get flyer ID details
        flyers = await adapter.fetch_flyers_by_postal_code(postal_code, merchant_name=merchant_name)
        active_flyer_id = flyers[0].get("id") if flyers else None

        # 3. Call get_normalized_deals
        valid_from, valid_to, deals = await adapter.get_normalized_deals(
            postal_code=postal_code,
            store_id=store_id,
            merchant_name=merchant_name,
        )

    # 4. Assertions
    assert len(deals) > 0, "Expected non-empty list of deals"
    for deal in deals:
        assert deal.sale_price > 0, f"Deal '{deal.product_name}' has invalid sale_price: {deal.sale_price}"

    now_utc = datetime.now(timezone.utc)
    valid_to_utc = valid_to.astimezone(timezone.utc) if valid_to.tzinfo else valid_to.replace(tzinfo=timezone.utc)
    assert valid_to_utc > now_utc, f"Expected valid_to ({valid_to_utc}) to be a future UTC datetime (now: {now_utc})"

    # 5. Print output
    print(f"\nDiscovered Flyer ID: {active_flyer_id}")
    print(f"Date Window: {valid_from.isoformat()} to {valid_to.isoformat()}")
    print(f"Total Items Extracted: {len(deals)}")
    print("\nTop 5 Extracted Deals:")
    for deal in deals[:5]:
        print(f"[{deal.category}] {deal.product_name} -> ${deal.sale_price:.2f} / {deal.pricing_unit} ({deal.raw_promotion_text})")

    # 6. Pipe returned deals into PartitionedDealStorage
    r_client = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
    try:
        storage = PartitionedDealStorage(redis_client=r_client)
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

        # Verify cached retrieval
        retrieved = await storage.get_deals_for_stores([store_id])
        stored_deals = retrieved.get(store_id, [])
        print(f"Retrieved {len(stored_deals)} deals from Redis cache for store '{store_id}'")
        assert len(stored_deals) == len(deals), f"Expected {len(deals)} stored deals, got {len(stored_deals)}"

    finally:
        await r_client.aclose()

    print("\nALL LIVE INGESTION CHECKS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(test_live_flipp_ingestion())
