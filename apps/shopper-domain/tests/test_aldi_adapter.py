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
        assert d0.item_name == "Fresh Family Pack Boneless Skinless Chicken Thighs"
        assert d0.clean_name == "fresh family boneless skinless chicken thighs"
        assert d0.deal_price == 2.29
        assert d0.unit == "lb"
        assert d0.normalized_category == "Meat"
        assert d0.original_price is None
        assert d0.currency == "USD"
        assert d0.store_id == "aldi-chicago-01"
        assert d0.store_name == "ALDI"
        assert d0.deal_id.startswith("aldi-chicago-01_")

        d1 = deals[1]
        assert d1.item_name == "Fresh USDA Choice Black Angus Beef Chuck Roast"
        assert d1.deal_price == 4.99
        assert d1.unit == "lb"
        assert d1.normalized_category == "Meat"

        # 4. Test Produce pricing conventions
        d2 = deals[2]  # 49¢ each avocados
        assert d2.item_name == "Hass Avocados"
        assert d2.deal_price == 0.49
        assert d2.unit == "each"
        assert d2.normalized_category == "Produce"

        d3 = deals[3]  # Strawberries $1.49 each
        assert d3.item_name == "Strawberries 1 lb Pkg"
        assert d3.deal_price == 1.49
        assert d3.unit == "each"
        assert d3.normalized_category == "Produce"

        d4 = deals[4]  # Honeycrisp apples $1.29 per lb
        assert d4.item_name == "Honeycrisp Apples"
        assert d4.deal_price == 1.29
        assert d4.unit == "lb"
        assert d4.normalized_category == "Produce"

        # 5. Test Pantry category & regular_price omitted cleanly
        d5 = deals[5]
        assert d5.item_name == "Specially Selected Extra Virgin Olive Oil 16.9 oz"
        assert d5.deal_price == 5.99
        assert d5.original_price is None
        assert d5.normalized_category == "Pantry"

        # 6. Test Aldi Finds section / category hints
        d6 = deals[6]
        assert d6.item_name == "Crofton 12-Inch Cast Iron Skillet"
        assert d6.deal_price == 14.99
        assert d6.normalized_category == "Pantry"

        # 7. Test Dairy & regular price present
        d7 = deals[7]
        assert d7.item_name == "Friendly Farms Whole Milk 1 Gallon"
        assert d7.deal_price == 2.79
        assert d7.original_price == 3.19
        assert d7.unit == "each"
        assert d7.normalized_category == "Dairy"

        # 8. Test Snacks / Multi-buy pricing
        d8 = deals[8]
        assert d8.item_name == "Clancy's Sea Salt Kettle Chips"
        assert d8.deal_price == 1.50
        assert d8.normalized_category == "Pantry"

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
