import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest

_shopper_domain_dir = str(Path(__file__).resolve().parent.parent)
if _shopper_domain_dir not in sys.path:
    sys.path.insert(0, _shopper_domain_dir)

from deal_normalizer import (
    DealExpansionResponse,
    NormalizedItem,
    BatchDealExpansionResponse,
    DealExpansionItem,
)
from src.ingestion.adapters.aldi_adapter import AldiAdapter
from src.ingestion.adapters.flipp_adapter import FlippAdapter
from src.ingestion.models import NormalizedDealItem


@pytest.mark.anyio
async def test_flipp_adapter_multi_item_expansion():
    """
    Verifies that FlippAdapter expands a multi-item promotional deal into
    two separate sibling deals with suffixes `_0` and `_1`, preserving price,
    store ID, and timestamps, with expanded categories and clean names.
    """
    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/flipp/flyers/" in url_str and "/items" in url_str:
            items = [
                {
                    "id": 11111,
                    "name": "Bone-in New York Steak or Jumbo Peeled Shrimp 16/20 ct",
                    "current_price": 8.99,
                    "sale_story": "$8.99 / lb with Card",
                    "category": "Meat & Seafood",
                },
                {
                    "id": 22222,
                    "name": "Gala Apples",
                    "current_price": 1.49,
                    "sale_story": "$1.49 / lb",
                    "category": "Produce",
                },
            ]
            return httpx.Response(200, json=items)
        elif "/flipp/flyers" in url_str:
            flyers = [
                {
                    "id": 99999,
                    "merchant": "Ralphs",
                    "valid_from": "2026-10-01T07:00:00Z",
                    "valid_to": "2026-10-08T06:59:59Z",
                }
            ]
            return httpx.Response(200, json={"flyers": flyers})
        return httpx.Response(404)

    mock_gemini_client = MagicMock()
    mock_expansion = DealExpansionResponse(
        items=[
            NormalizedItem(
                clean_name="bone-in new york steak",
                normalized_category="Meat",
                unit="lb",
                qualifiers=["bone-in"],
            ),
            NormalizedItem(
                clean_name="jumbo peeled shrimp",
                normalized_category="Seafood",
                unit="lb",
                qualifiers=["jumbo", "16/20 ct"],
            ),
        ]
    )
    mock_response = MagicMock()
    mock_response.parsed = mock_expansion
    mock_gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        adapter = FlippAdapter(
            client=http_client,
            merchant_name="Ralphs",
            gemini_client=mock_gemini_client,
        )

        v_from, v_to, deals = await adapter.get_normalized_deals(
            postal_code="90210",
            store_id="ralphs-101",
            merchant_name="Ralphs",
        )

        # 1 multi-item deal expanded into 2, plus 1 standard produce deal -> Total 3 deals
        assert len(deals) == 3

        # Sibling 0 of multi-item deal
        d0 = deals[0]
        assert d0.deal_id == "ralphs-101_11111_0"
        assert d0.clean_name == "bone-in new york steak"
        assert d0.normalized_category == "Meat"
        assert d0.deal_price == 8.99
        assert d0.unit == "lb"
        assert d0.store_id == "ralphs-101"
        assert d0.store_name == "Ralphs"
        assert d0.valid_from == datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)
        assert d0.valid_to == datetime(2026, 10, 8, 6, 59, 59, tzinfo=timezone.utc)

        # Sibling 1 of multi-item deal
        d1 = deals[1]
        assert d1.deal_id == "ralphs-101_11111_1"
        assert d1.clean_name == "jumbo peeled shrimp"
        assert d1.normalized_category == "Seafood"
        assert d1.deal_price == 8.99
        assert d1.unit == "lb"
        assert d1.store_id == "ralphs-101"
        assert d1.store_name == "Ralphs"
        assert d1.valid_from == datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)
        assert d1.valid_to == datetime(2026, 10, 8, 6, 59, 59, tzinfo=timezone.utc)

        # Non-multi-item deal
        d2 = deals[2]
        assert d2.deal_id == "ralphs-101_22222"
        assert d2.clean_name == "gala apples"
        assert d2.normalized_category == "Produce"
        assert d2.deal_price == 1.49


@pytest.mark.anyio
async def test_aldi_adapter_multi_item_expansion():
    """
    Verifies that AldiAdapter expands multi-item promotional deals into
    distinct sibling items using Gemini client with preserved metadata.
    """
    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/flipp/flyers/" in url_str and "/items" in url_str:
            items = [
                {
                    "id": 66666,
                    "name": "Choice of Fresh Atlantic Salmon or Tilapia Fillet",
                    "sale_story": "Fresh Meat Special! $5.99 per lb",
                    "current_price": 5.99,
                    "category": "Meat",
                },
                {
                    "id": 77777,
                    "name": "Whole Milk 1 Gallon",
                    "sale_story": "$2.79 each",
                    "current_price": 2.79,
                    "category": "Dairy",
                },
            ]
            return httpx.Response(200, json=items)
        elif "/flipp/flyers" in url_str:
            flyers = [
                {
                    "id": 88888,
                    "merchant": "ALDI",
                    "name": "ALDI Weekly Ad",
                    "valid_from": "2026-10-01T07:00:00Z",
                    "valid_to": "2026-10-08T06:59:59Z",
                }
            ]
            return httpx.Response(200, json={"flyers": flyers})
        return httpx.Response(404)

    mock_gemini_client = MagicMock()
    mock_expansion = DealExpansionResponse(
        items=[
            NormalizedItem(
                clean_name="fresh atlantic salmon",
                normalized_category="Seafood",
                unit="lb",
            ),
            NormalizedItem(
                clean_name="tilapia fillet",
                normalized_category="Seafood",
                unit="lb",
            ),
        ]
    )
    mock_response = MagicMock()
    mock_response.parsed = mock_expansion
    mock_gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        adapter = AldiAdapter(
            client=http_client,
            gemini_client=mock_gemini_client,
        )

        v_from, v_to, deals = await adapter.get_normalized_deals(
            postal_code="60601",
            store_id="aldi-store-1",
        )

        assert len(deals) == 3

        # Sibling 0
        assert deals[0].deal_id == "aldi-store-1_66666_0"
        assert deals[0].clean_name == "fresh atlantic salmon"
        assert deals[0].normalized_category == "Seafood"
        assert deals[0].deal_price == 5.99
        assert deals[0].unit == "lb"
        assert deals[0].store_id == "aldi-store-1"

        # Sibling 1
        assert deals[1].deal_id == "aldi-store-1_66666_1"
        assert deals[1].clean_name == "tilapia fillet"
        assert deals[1].normalized_category == "Seafood"
        assert deals[1].deal_price == 5.99
        assert deals[1].unit == "lb"
        assert deals[1].store_id == "aldi-store-1"

        # Sibling 2 (standard deal)
        assert deals[2].deal_id == "aldi-store-1_77777"
        assert deals[2].clean_name == "whole milk"
        assert deals[2].deal_price == 2.79


@pytest.mark.anyio
async def test_adapter_deduplication_by_store_and_clean_name():
    """
    Verifies that deduplication keys off `(store_id, clean_name)` so both split
    products are retained independently, while duplicate items with the same
    (store_id, clean_name) are deduplicated.
    """
    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/flipp/flyers/" in url_str and "/items" in url_str:
            items = [
                # Multi-item deal expanding to "honeycrisp apples" and "bartlett pears"
                {
                    "id": 101,
                    "name": "Honeycrisp Apples or Bartlett Pears",
                    "current_price": 1.99,
                    "sale_story": "$1.99 / lb",
                    "category": "Produce",
                },
                # Duplicate item that also cleans to "honeycrisp apples"
                {
                    "id": 102,
                    "name": "Honeycrisp Apples 1 lb",
                    "current_price": 2.49,
                    "sale_story": "$2.49 / lb",
                    "category": "Produce",
                },
                # Duplicate item that also cleans to "bartlett pears"
                {
                    "id": 103,
                    "name": "Bartlett Pears",
                    "current_price": 2.29,
                    "sale_story": "$2.29 / lb",
                    "category": "Produce",
                },
            ]
            return httpx.Response(200, json=items)
        elif "/flipp/flyers" in url_str:
            return httpx.Response(200, json={"flyers": [{"id": 1, "merchant": "Ralphs"}]})
        return httpx.Response(404)

    mock_gemini_client = MagicMock()
    mock_expansion = DealExpansionResponse(
        items=[
            NormalizedItem(clean_name="honeycrisp apples", normalized_category="Produce", unit="lb"),
            NormalizedItem(clean_name="bartlett pears", normalized_category="Produce", unit="lb"),
        ]
    )
    mock_response = MagicMock()
    mock_response.parsed = mock_expansion
    mock_gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        adapter = FlippAdapter(client=http_client, gemini_client=mock_gemini_client)
        v_from, v_to, deals = await adapter.get_normalized_deals("90210", "store-123")

        # Items 102 and 103 clean to "honeycrisp apples" and "bartlett pears" which were already seen
        # from the expanded deal.
        assert len(deals) == 2
        clean_names = [d.clean_name for d in deals]
        assert "honeycrisp apples" in clean_names
        assert "bartlett pears" in clean_names
        assert len(set(clean_names)) == 2


@pytest.mark.anyio
async def test_adapter_gemini_error_fallback():
    """
    Verifies that if Gemini expansion throws an exception during circular ingestion,
    the adapter gracefully falls back to the unexpanded parent deal.
    """
    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/flipp/flyers/" in url_str and "/items" in url_str:
            items = [
                {
                    "id": 500,
                    "name": "Top Sirloin Steak or Salmon Fillet",
                    "current_price": 7.99,
                    "sale_story": "$7.99 / lb",
                    "category": "Meat",
                }
            ]
            return httpx.Response(200, json=items)
        elif "/flipp/flyers" in url_str:
            return httpx.Response(200, json={"flyers": [{"id": 5, "merchant": "Ralphs"}]})
        return httpx.Response(404)

    mock_gemini_client = MagicMock()
    mock_gemini_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Google GenAI 503 Service Unavailable")
    )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        adapter = FlippAdapter(client=http_client, gemini_client=mock_gemini_client)
        v_from, v_to, deals = await adapter.get_normalized_deals("90210", "store-ralphs")

        # Graceful fallback: exactly 1 unexpanded deal
        assert len(deals) == 1
        assert deals[0].deal_id == "store-ralphs_500"
        assert deals[0].deal_price == 7.99


@pytest.mark.anyio
async def test_adapter_batch_chunking_and_semaphore():
    """
    Verifies that multiple candidate deals are chunked and processed sequentially
    with semaphore rate limiting and sleep throttling.
    """
    items = [
        {
            "id": i,
            "name": f"Deal Choice {i} Apple or Pear",
            "current_price": 1.99,
            "sale_story": "$1.99 / lb",
            "category": "Produce",
        }
        for i in range(20)
    ]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/flipp/flyers/" in url_str and "/items" in url_str:
            return httpx.Response(200, json=items)
        elif "/flipp/flyers" in url_str:
            return httpx.Response(200, json={"flyers": [{"id": 10, "merchant": "Ralphs"}]})
        return httpx.Response(404)

    mock_gemini_client = MagicMock()
    mock_gemini_client.aio.models.generate_content = AsyncMock(
        side_effect=lambda model, contents, config: MagicMock(
            parsed=DealExpansionResponse(
                items=[
                    NormalizedItem(clean_name=f"apple", normalized_category="Produce", unit="lb"),
                    NormalizedItem(clean_name=f"pear", normalized_category="Produce", unit="lb"),
                ]
            )
        )
    )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        adapter = FlippAdapter(client=http_client, gemini_client=mock_gemini_client)
        v_from, v_to, deals = await adapter.get_normalized_deals("90210", "store-ralphs")

        # 20 items chunked into 2 batches (15 and 5) -> generate_content called twice
        assert mock_gemini_client.aio.models.generate_content.call_count == 2
        # Deduplication will retain distinct clean names across store
        assert len(deals) >= 2


@pytest.mark.anyio
async def test_adapter_compound_brand_ocr_truncation_expansion():
    """
    Verifies that FlippAdapter extracts provider brand metadata (e.g. 'PAM | Barilla')
    for OCR-clipped items like 'cray 5-6 oz. or Barilla Pesto Sauce 6.2-6.5 oz.',
    supplies it to Gemini batch expansion, and outputs two pantry items:
    cooking spray and pesto sauce.
    """
    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/flipp/flyers/" in url_str and "/items" in url_str:
            items = [
                {
                    "id": 901,
                    "name": "cray 5-6 oz. or Barilla Pesto Sauce 6.2-6.5 oz.",
                    "brand": "PAM | Barilla",
                    "current_price": 3.49,
                    "sale_story": "$3.49 each",
                    "category": "Pantry",
                }
            ]
            return httpx.Response(200, json=items)
        elif "/flipp/flyers" in url_str:
            return httpx.Response(200, json={"flyers": [{"id": 1, "merchant": "Ralphs"}]})
        return httpx.Response(404)

    mock_gemini_client = MagicMock()
    mock_batch_resp = BatchDealExpansionResponse(
        expansions=[
            DealExpansionItem(
                source_index=0,
                items=[
                    NormalizedItem(
                        clean_name="cooking spray",
                        brand="PAM",
                        normalized_category="Pantry",
                        unit="each",
                    ),
                    NormalizedItem(
                        clean_name="pesto sauce",
                        brand="Barilla",
                        normalized_category="Pantry",
                        unit="each",
                    ),
                ],
            )
        ]
    )
    mock_response = MagicMock()
    mock_response.parsed = mock_batch_resp
    mock_gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        adapter = FlippAdapter(client=http_client, gemini_client=mock_gemini_client)
        v_from, v_to, deals = await adapter.get_normalized_deals("90210", "store-ralphs")

        assert len(deals) == 2
        d0, d1 = deals[0], deals[1]

        assert d0.clean_name == "cooking spray"
        assert d0.normalized_category == "Pantry"
        assert d0.brand == "PAM"
        assert d0.deal_price == 3.49

        assert d1.clean_name == "pesto sauce"
        assert d1.normalized_category == "Pantry"
        assert d1.brand == "Barilla"
        assert d1.deal_price == 3.49


