import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import httpx
import pytest

# Ensure apps/shopper-domain is in sys.path
_shopper_domain_dir = str(Path(__file__).resolve().parent.parent)
if _shopper_domain_dir not in sys.path:
    sys.path.insert(0, _shopper_domain_dir)

from src.ingestion.adapters.trader_joes_adapter import (
    TraderJoesAdapter,
    TRADER_JOES_GRAPHQL_URL,
)
from src.ingestion.models import NormalizedDealItem
from src.ingestion.factory import DealAdapterFactory


SAMPLE_GRAPHQL_ITEMS = [
    {
        "sku": "061437",
        "item_title": "EMMA REICHART DRY RIESLING",
        "name": "EMMA REICHART DRY RIESLING",
        "retail_price": "6.99",
        "sales_size": 750,
        "sales_uom_description": "ml",
        "fun_tags": ["Date Night", "Picnic"],
        "category_hierarchy": [
            {"id": 2, "name": "Products", "level": 1},
            {"id": 182, "name": "Beverages", "level": 2},
            {"id": 200, "name": "Wine, Beer & Liquor", "level": 3},
        ],
        "primary_image": "/content/dam/trjo/products/m306/wine/61437.png",
        "primary_image_meta": {
            "url": "/content/dam/trjo/products/m306/wine/61437.png",
        },
        "price_range": {
            "minimum_price": {
                "final_price": {"value": 6.99, "currency": "USD"},
                "regular_price": {"value": 6.99, "currency": "USD"},
            }
        },
    },
    {
        "sku": "075290",
        "item_title": "HOL GNOCCHI PUMPKIN",
        "name": "HOL GNOCCHI PUMPKIN",
        "retail_price": "2.99",
        "sales_size": 1,
        "sales_uom_description": "Each",
        "product_label": "LIMITED TIME",
        "item_story_marketing": "<p>Look no further than the pages of this Flyer for evidence.</p>",
        "category_hierarchy": [
            {"id": 2, "name": "Products", "level": 1},
            {"id": 8, "name": "Food", "level": 2},
            {"id": 137, "name": "For the Pantry", "level": 3},
        ],
        "primary_image": "/content/dam/trjo/products/m4/75290.png",
        "price_range": {
            "minimum_price": {
                "final_price": {"value": 2.99, "currency": "USD"},
                "regular_price": {"value": 3.49, "currency": "USD"},
            }
        },
    },
    {
        "sku": "092558",
        "item_title": "Organic Ground Beef 85/15",
        "name": "ORGANIC GROUND BEEF 85/15",
        "retail_price": "7.99",
        "sales_size": 1,
        "sales_uom_description": "Pound",
        "category_hierarchy": [
            {"id": 2, "name": "Products", "level": 1},
            {"id": 8, "name": "Food", "level": 2},
            {"id": 131, "name": "Meat, Seafood & Plant-based", "level": 3},
        ],
        "primary_image": "https://www.traderjoes.com/content/dam/trjo/products/m1/92558.png",
        "price_range": {
            "minimum_price": {
                "final_price": {"value": 7.99, "currency": "USD"},
                "regular_price": {"value": 7.99, "currency": "USD"},
            }
        },
    },
    {
        "sku": "044168",
        "item_title": "Green Onions 6 oz",
        "name": "GREEN ONIONS",
        "retail_price": "1.29",
        "sales_size": 6,
        "sales_uom_description": "Each",
        "category_hierarchy": [
            {"id": 2, "name": "Products", "level": 1},
            {"id": 8, "name": "Food", "level": 2},
            {"id": 135, "name": "Fresh Fruits & Veggies", "level": 3},
        ],
        "primary_image": "/content/dam/trjo/products/m2/44168.png",
        "price_range": {
            "minimum_price": {
                "final_price": {"value": 1.29, "currency": "USD"},
                "regular_price": {"value": 1.29, "currency": "USD"},
            }
        },
    },
]


@pytest.mark.anyio
async def test_fetch_flyer_metadata():
    adapter = TraderJoesAdapter()
    flyer_id, valid_from, valid_to = await adapter.fetch_flyer_metadata("90210")
    assert flyer_id == "tj-fearless-flyer-34"
    assert isinstance(valid_from, datetime)
    assert isinstance(valid_to, datetime)
    assert valid_from.tzinfo == timezone.utc
    assert valid_to.tzinfo == timezone.utc
    assert valid_to > valid_from

    # Custom store_code kwargs
    f_id, _, _ = await adapter.fetch_flyer_metadata("60601", store_code="701")
    assert f_id == "tj-fearless-flyer-701"


@pytest.mark.anyio
async def test_fetch_raw_items_graphql():
    requested_bodies = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == TRADER_JOES_GRAPHQL_URL
        assert request.method == "POST"
        body = json.loads(request.content.decode("utf-8"))
        requested_bodies.append(body)

        response_data = {
            "data": {
                "products": {
                    "total_count": len(SAMPLE_GRAPHQL_ITEMS),
                    "page_info": {
                        "current_page": 1,
                        "page_size": 50,
                        "total_pages": 1,
                    },
                    "items": SAMPLE_GRAPHQL_ITEMS,
                }
            }
        }
        return httpx.Response(200, json=response_data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = TraderJoesAdapter(client=client, store_code="138")
        items = await adapter.fetch_raw_items("tj-fearless-flyer-138")

        assert len(items) == 4
        # Verify storeCode was forwarded with default FearlessFlyerProducts
        assert len(requested_bodies) == 1
        assert requested_bodies[0]["operationName"] == "FearlessFlyerProducts"
        assert requested_bodies[0]["variables"]["storeCode"] == "138"

        # Verify SKU was set as id and item_id
        assert items[0]["id"] == "061437"
        assert items[0]["item_id"] == "061437"
        assert items[1]["id"] == "075290"

    # Also test with explicit default_search
    async with httpx.AsyncClient(transport=transport) as client:
        adapter_search = TraderJoesAdapter(client=client, store_code="138", default_search="fearless flyer")
        await adapter_search.fetch_raw_items("tj-fearless-flyer-138")
        assert requested_bodies[-1]["operationName"] == "SearchProducts"
        assert requested_bodies[-1]["variables"]["search"] == "fearless flyer"


@pytest.mark.anyio
async def test_fetch_raw_items_pagination():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        page = body["variables"]["currentPage"]

        if page == 1:
            return httpx.Response(200, json={
                "data": {
                    "products": {
                        "total_count": 4,
                        "page_info": {"current_page": 1, "page_size": 2, "total_pages": 2},
                        "items": SAMPLE_GRAPHQL_ITEMS[:2],
                    }
                }
            })
        elif page == 2:
            return httpx.Response(200, json={
                "data": {
                    "products": {
                        "total_count": 4,
                        "page_info": {"current_page": 2, "page_size": 2, "total_pages": 2},
                        "items": SAMPLE_GRAPHQL_ITEMS[2:],
                    }
                }
            })
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = TraderJoesAdapter(client=client, max_pages=3)
        items = await adapter.fetch_raw_items("tj-fearless-flyer-34")
        assert len(items) == 4


@pytest.mark.anyio
async def test_extraction_methods():
    adapter = TraderJoesAdapter()

    # 1. Product Name Extraction
    assert adapter.extract_product_name(SAMPLE_GRAPHQL_ITEMS[0]) == "EMMA REICHART DRY RIESLING"
    assert adapter.extract_product_name(SAMPLE_GRAPHQL_ITEMS[2]) == "Organic Ground Beef 85/15"

    # 2. Pricing Extraction
    # Item 0: regular price $6.99
    sale_price, original_price, unit = adapter.extract_pricing(SAMPLE_GRAPHQL_ITEMS[0])
    assert sale_price == 6.99
    assert original_price is None
    assert unit == "each"

    # Item 1: sale price $2.99, regular price $3.49
    sale_price, original_price, unit = adapter.extract_pricing(SAMPLE_GRAPHQL_ITEMS[1])
    assert sale_price == 2.99
    assert original_price == 3.49
    assert unit == "each"

    # Item 2: beef sold by pound
    sale_price, original_price, unit = adapter.extract_pricing(SAMPLE_GRAPHQL_ITEMS[2])
    assert sale_price == 7.99
    assert unit == "lb"

    # Special price override
    item_special = {
        "special_price": "3.49",
        "retail_price": "4.99",
        "sales_uom_description": "Each",
    }
    s_p, o_p, u = adapter.extract_pricing(item_special)
    assert s_p == 3.49
    assert o_p == 4.99
    assert u == "each"

    # 3. Raw Category Extraction
    cat0 = adapter.extract_raw_category(SAMPLE_GRAPHQL_ITEMS[0])
    assert cat0 == "Wine, Beer & Liquor"
    assert adapter.standardize_category(cat0) == "Pantry"

    cat1 = adapter.extract_raw_category(SAMPLE_GRAPHQL_ITEMS[1])
    assert cat1 == "For the Pantry"
    assert adapter.standardize_category(cat1) == "Pantry"

    cat2 = adapter.extract_raw_category(SAMPLE_GRAPHQL_ITEMS[2])
    assert cat2 == "Meat, Seafood & Plant-based"
    assert adapter.standardize_category(cat2, "Organic Ground Beef 85/15") == "Meat"

    cat3 = adapter.extract_raw_category(SAMPLE_GRAPHQL_ITEMS[3])
    assert cat3 == "Fresh Fruits & Veggies"
    assert adapter.standardize_category(cat3) == "Produce"

    # 4. Brand Extraction
    assert adapter.extract_brand(SAMPLE_GRAPHQL_ITEMS[0]) == "Trader Joe's"
    assert adapter.extract_brand({"brand": "Kerrygold"}) == "Kerrygold"

    # 5. Image URL Extraction
    img0 = adapter.extract_image_url(SAMPLE_GRAPHQL_ITEMS[0])
    assert img0 == "https://www.traderjoes.com/content/dam/trjo/products/m306/wine/61437.png"

    img2 = adapter.extract_image_url(SAMPLE_GRAPHQL_ITEMS[2])
    assert img2 == "https://www.traderjoes.com/content/dam/trjo/products/m1/92558.png"

    # Primary image meta with JSON string
    item_json_img = {
        "primary_image_meta": {
            "metadata": json.dumps({"srcOriginal": "/content/dam/trjo/sample.png"})
        }
    }
    assert adapter.extract_image_url(item_json_img) == "https://www.traderjoes.com/content/dam/trjo/sample.png"


@pytest.mark.anyio
async def test_get_normalized_deals():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "data": {
                "products": {
                    "total_count": len(SAMPLE_GRAPHQL_ITEMS),
                    "page_info": {"current_page": 1, "page_size": 50, "total_pages": 1},
                    "items": SAMPLE_GRAPHQL_ITEMS,
                }
            }
        })

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = TraderJoesAdapter(client=client)
        valid_from, valid_to, deals = await adapter.get_normalized_deals(
            postal_code="90210",
            store_id="tj-34",
        )

        assert len(deals) == 4
        assert all(isinstance(d, NormalizedDealItem) for d in deals)
        assert valid_to > valid_from

        # Check deals content
        d0 = next(d for d in deals if d.deal_id == "tj-34_061437")
        assert d0.item_name == "EMMA REICHART DRY RIESLING"
        assert d0.clean_name == "emma reichart dry riesling"
        assert d0.deal_price == 6.99
        assert d0.currency == "USD"
        assert d0.unit == "each"
        assert d0.store_id == "tj-34"
        assert d0.store_name == "Trader Joe's"
        assert d0.image_url == "https://www.traderjoes.com/content/dam/trjo/products/m306/wine/61437.png"

        d2 = next(d for d in deals if d.deal_id == "tj-34_092558")
        assert d2.item_name == "Organic Ground Beef 85/15"
        assert d2.deal_price == 7.99
        assert d2.unit == "lb"
        assert d2.normalized_category == "Meat"


@pytest.mark.anyio
async def test_error_and_circuit_breaker_handling():
    def mock_500_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Internal Server Error"})

    transport = httpx.MockTransport(mock_500_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = TraderJoesAdapter(client=client)
        # Should gracefully return empty list without crashing
        items = await adapter.fetch_raw_items("tj-fearless-flyer-34")
        assert items == []


@pytest.mark.anyio
async def test_factory_resolves_trader_joes_adapter():
    chain_metadata = [
        {"chain_id": "trader-joes", "display_name": "Trader Joe's", "adapter_name": "trader-joes"},
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
    await factory.load_chains_from_db()

    adapter = factory.get_adapter("Trader Joe's")
    assert isinstance(adapter, TraderJoesAdapter)
    assert adapter.default_merchant == "Trader Joe's"

    adapter_by_id = factory.get_adapter("trader-joes")
    assert adapter_by_id is adapter
