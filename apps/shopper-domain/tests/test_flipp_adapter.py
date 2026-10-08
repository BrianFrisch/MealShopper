import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import httpx
import pytest

_shopper_domain_dir = str(Path(__file__).resolve().parent.parent)
if _shopper_domain_dir not in sys.path:
    sys.path.insert(0, _shopper_domain_dir)

from src.ingestion.adapters.flipp_adapter import FlippAdapter
from src.ingestion.models import NormalizedDealItem


@pytest.mark.anyio
async def test_flipp_adapter():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/flipp/flyers/" in url_str and "/items" in url_str:
            items = [
                {
                    "name": "Fresh Heritage Farm Boneless Chicken Breast",
                    "current_price": 1.99,
                    "sale_story": "$1.99 / lb with Card",
                    "category": "Meat & Seafood",
                },
                {
                    "name": "Hass Avocados Large",
                    "current_price": None,
                    "sale_story": "4 for $3.00 with Card",
                    "category": "Produce",
                },
                {
                    "name": "Simple Truth Organic Extra Virgin Olive Oil 16.9 oz",
                    "current_price": 7.99,
                    "original_price": 9.99,
                    "sale_story": "Save $2.00",
                    "category": "Pantry",
                },
                {
                    "name": "Pork Loin Chops",
                    "current_price": None,
                    "sale_story": "Buy 1 Get 1 Free",
                    "pre_price_text": "$4.99/lb",
                    "category": "Meat",
                },
            ]
            return httpx.Response(200, json=items)
        elif "/flipp/flyers" in url_str:
            flyers = [
                {
                    "id": 12345,
                    "merchant": "Ralphs",
                    "valid_from": "2026-09-23T07:00:00Z",
                    "valid_to": "2026-09-30T06:59:59Z",
                },
                {
                    "id": 67890,
                    "merchant": "Sprouts",
                    "valid_from": "2026-09-23T07:00:00Z",
                    "valid_to": "2026-09-30T06:59:59Z",
                },
            ]
            return httpx.Response(200, json={"flyers": flyers})
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = FlippAdapter(client=client)

        # 1. Test flyer fetching and filtering
        flyers = await adapter.fetch_flyers_by_postal_code("90210", merchant_name="Ralphs")
        assert len(flyers) == 1
        assert flyers[0]["id"] == 12345

        # 2. Test promotion fetching
        items = await adapter.fetch_promotions_for_flyer(12345)
        assert len(items) == 4

        # 3. Test get_normalized_deals
        v_from, v_to, deals = await adapter.get_normalized_deals("90210", "ralphs-101", merchant_name="Ralphs")
        assert len(deals) == 4
        assert isinstance(deals[0], NormalizedDealItem)
        assert v_from == datetime(2026, 9, 23, 7, 0, tzinfo=timezone.utc)
        assert v_to == datetime(2026, 9, 30, 6, 59, 59, tzinfo=timezone.utc)

        d0 = deals[0]
        assert d0.item_name == "Fresh Heritage Farm Boneless Chicken Breast"
        assert d0.clean_name == "fresh heritage farm boneless chicken breast"
        assert d0.deal_price == 1.99
        assert d0.unit == "lb"
        assert d0.normalized_category == "Meat"
        assert d0.currency == "USD"
        assert d0.store_id == "ralphs-101"
        assert d0.store_name == "Ralphs"
        assert d0.deal_id.startswith("ralphs-101_")
        assert d0.raw_promotion_text == "$1.99 / lb with Card"

        d1 = deals[1]
        assert d1.item_name == "Hass Avocados Large"
        assert d1.clean_name == "hass avocados large"
        assert d1.deal_price == 0.75
        assert d1.unit == "each"
        assert d1.normalized_category == "Produce"
        assert d1.raw_promotion_text == "4 for $3.00 with Card"

        d2 = deals[2]
        assert d2.item_name == "Simple Truth Organic Extra Virgin Olive Oil 16.9 oz"
        assert d2.clean_name == "simple truth organic extra virgin olive oil"
        assert d2.deal_price == 7.99
        assert d2.original_price == 9.99
        assert d2.unit == "each"
        assert d2.normalized_category == "Pantry"

        d3 = deals[3]
        assert d3.deal_price == 4.99
        assert d3.unit == "lb"
        assert d3.normalized_category == "Meat"

        # 4. Test error handling on HTTP failure
        error_flyers = await adapter.fetch_flyers_by_postal_code("00000", merchant_name="UnknownStore")
        assert error_flyers == []

        v_from_err, v_to_err, err_deals = await adapter.get_normalized_deals("00000", "unknown-1", merchant_name="UnknownStore")
        assert err_deals == []
        assert v_from_err is not None
        assert v_to_err is not None

        print("All FlippAdapter tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(test_flipp_adapter())
