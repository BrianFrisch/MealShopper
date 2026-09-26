import asyncio
from datetime import datetime, timezone, timedelta
import redis.asyncio as redis
from src.storage.deal_storage import PartitionedDealStorage
from src.storage.cycle_helper import get_circular_cycle_key

async def run_test():
    now = datetime.now(timezone.utc)
    valid_from = now - timedelta(days=1)
    valid_to = now + timedelta(days=5)

    print(f"Testing Ralphs-101 Deal Ingestion...")
    print(f"Cycle Key: {get_circular_cycle_key(now)}")

    mock_deals = [
        {
            "product_name": "Fresh Heritage Farm Boneless Chicken Breast",
            "clean_name": "chicken breast boneless skinless",
            "category": "Meat & Seafood",
            "sale_price": 1.99,
            "pricing_unit": "lb",
            "raw_promotion_text": "$1.99 / lb with Card"
        },
        {
            "product_name": "Hass Avocados Large",
            "clean_name": "avocados hass",
            "category": "Produce",
            "sale_price": 0.75,
            "pricing_unit": "each",
            "raw_promotion_text": "4 for $3.00 with Card"
        },
        {
            "product_name": "Simple Truth Organic Extra Virgin Olive Oil 16.9 oz",
            "clean_name": "olive oil extra virgin",
            "category": "Pantry",
            "sale_price": 7.99,
            "pricing_unit": "each",
            "raw_promotion_text": "Save $2.00"
        }
    ]

    r_client = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
    storage = PartitionedDealStorage(redis_client=r_client)

    paths = await storage.save_deals(
        store_id="ralphs-101",
        deals=mock_deals,
        valid_from=valid_from,
        valid_to=valid_to
    )
    print("Partition files written:", paths)

    # Verify retrieval
    results = await storage.get_deals_for_stores(["ralphs-101"])
    fetched = results.get("ralphs-101", [])
    print(f"Successfully retrieved {len(fetched)} deals from store ralphs-101!")
    
    assert len(fetched) == 3
    assert fetched[0]["clean_name"] == "chicken breast boneless skinless"
    print("ALL ASSERTIONS PASSED!")

    await r_client.aclose()

if __name__ == "__main__":
    asyncio.run(run_test())