import asyncio
from datetime import datetime, timezone
import httpx

from src.ingestion.adapters.aldi_adapter import AldiAdapter
from src.ingestion.models import NormalizedDealItem


async def test_aldi_adapter():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)

        if "/flipp/flyers/" in url_str and "/items" in url_str:
            items = [
                {
                    "name": "Fresh Family Pack Boneless Skinless Chicken Thighs",
                    "sale_story": "Fresh Meat Special! $2.29 per lb",
                    "current_price": 2.29,
                    "category": "Meat",
                },
                {
                    "name": "Fresh USDA Choice Black Angus Beef Chuck Roast",
                    "sale_story": "Fresh Meat Special",
                    "pre_price_text": "$4.99/lb",
                    "current_price": None,
                },
                {
                    "name": "Hass Avocados",
                    "sale_story": "49¢ each",
                    "current_price": "49¢",
                    "category": "Produce",
                },
                {
                    "name": "Strawberries 1 lb Pkg",
                    "sale_story": "$1.49 each",
                    "current_price": 1.49,
                    "category": "Produce",
                },
                {
                    "name": "Honeycrisp Apples",
                    "sale_story": "$1.29 per lb",
                    "current_price": 1.29,
                    "category": "Produce",
                },
                {
                    "name": "Specially Selected Extra Virgin Olive Oil 16.9 oz",
                    "sale_story": "Great Low Price",
                    "current_price": 5.99,
                    "original_price": None,
                },
                {
                    "name": "Crofton 12-Inch Cast Iron Skillet",
                    "sale_story": "Aldi Finds Special Buy",
                    "current_price": 14.99,
                    "section": "Aldi Finds",
                },
                {
                    "name": "Friendly Farms Whole Milk 1 Gallon",
                    "sale_story": "$2.79 each",
                    "current_price": 2.79,
                    "regular_price": 3.19,
                },
                {
                    "name": "Clancy's Sea Salt Kettle Chips",
                    "sale_story": "2 for $3.00",
                    "current_price": None,
                },
            ]
            return httpx.Response(200, json=items)

        elif "/flipp/flyers" in url_str:
            postal_code = request.url.params.get("postal_code", "")
            if postal_code == "60601":
                flyers = [
                    {
                        "id": 11111,
                        "merchant": "ALDI",
                        "name": "ALDI Weekly Ad",
                        "valid_from": "2026-09-23T07:00:00Z",
                        "valid_to": "2026-09-30T06:59:59Z",
                    },
                    {
                        "id": 22222,
                        "merchant": "Ralphs",
                        "name": "Ralphs Weekly Circular",
                        "valid_from": "2026-09-23T07:00:00Z",
                        "valid_to": "2026-09-30T06:59:59Z",
                    },
                ]
                return httpx.Response(200, json={"flyers": flyers})
            elif postal_code == "99999":
                return httpx.Response(200, json={"flyers": []})
            elif postal_code == "50000":
                return httpx.Response(500, json={"error": "Internal Server Error"})

        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = AldiAdapter(client=client)

        # 1. Test merchant matching defaults to ALDI / Aldi
        flyers = await adapter.fetch_flyers_by_postal_code("60601")
        assert len(flyers) == 1
        assert flyers[0]["id"] == 11111
        assert flyers[0]["merchant"] == "ALDI"

        # 2. Test get_normalized_deals with (postal_code, store_id)
        valid_from, valid_to, deals = await adapter.get_normalized_deals("60601", "aldi-chicago-01")
        assert len(deals) == 9
        assert isinstance(deals[0], NormalizedDealItem)
        assert valid_from == datetime(2026, 9, 23, 7, 0, tzinfo=timezone.utc)
        assert valid_to == datetime(2026, 9, 30, 6, 59, 59, tzinfo=timezone.utc)

        # 3. Test Aldi Fresh Meat Special items
        d0 = deals[0]
        assert d0.product_name == "Fresh Family Pack Boneless Skinless Chicken Thighs"
        assert d0.sale_price == 2.29
        assert d0.pricing_unit == "lb"
        assert d0.category == "Fresh Meat"
        assert d0.regular_price is None

        d1 = deals[1]
        assert d1.product_name == "Fresh USDA Choice Black Angus Beef Chuck Roast"
        assert d1.sale_price == 4.99
        assert d1.pricing_unit == "lb"
        assert d1.category == "Fresh Meat"

        # 4. Test Produce pricing conventions
        d2 = deals[2]  # 49¢ each avocados
        assert d2.product_name == "Hass Avocados"
        assert d2.sale_price == 0.49
        assert d2.pricing_unit == "each"
        assert d2.category == "Produce"

        d3 = deals[3]  # Strawberries $1.49 each
        assert d3.sale_price == 1.49
        assert d3.pricing_unit == "each"
        assert d3.category == "Produce"

        d4 = deals[4]  # Honeycrisp apples $1.29 per lb
        assert d4.sale_price == 1.29
        assert d4.pricing_unit == "lb"
        assert d4.category == "Produce"

        # 5. Test Pantry category & regular_price omitted cleanly
        d5 = deals[5]
        assert d5.product_name == "Specially Selected Extra Virgin Olive Oil 16.9 oz"
        assert d5.sale_price == 5.99
        assert d5.regular_price is None
        assert d5.category == "Pantry"

        # 6. Test Aldi Finds section / category hints
        d6 = deals[6]
        assert d6.product_name == "Crofton 12-Inch Cast Iron Skillet"
        assert d6.sale_price == 14.99
        assert d6.category == "Aldi Finds"

        # 7. Test Dairy & regular price present
        d7 = deals[7]
        assert d7.sale_price == 2.79
        assert d7.regular_price == 3.19
        assert d7.pricing_unit == "each"
        assert d7.category == "Dairy & Eggs"

        # 8. Test Snacks / Multi-buy pricing
        d8 = deals[8]
        assert d8.sale_price == 1.50
        assert d8.category == "Snacks"

        # 9. Test no active circulars for postal code
        empty_from, empty_to, empty_deals = await adapter.get_normalized_deals("99999", "aldi-empty-01")
        assert empty_deals == []
        assert empty_from is not None
        assert empty_to is not None

        # 10. Test HTTP error handling
        err_from, err_to, err_deals = await adapter.get_normalized_deals("50000", "aldi-err-01")
        assert err_deals == []
        assert err_from is not None
        assert err_to is not None

        print("All AldiAdapter tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(test_aldi_adapter())
