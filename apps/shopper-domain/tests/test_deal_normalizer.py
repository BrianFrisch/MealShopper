import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock

# Ensure shopper-domain directory is in sys.path
_shopper_domain_dir = str(Path(__file__).resolve().parent.parent)
if _shopper_domain_dir not in sys.path:
    sys.path.insert(0, _shopper_domain_dir)

from deal_normalizer import (
    VALID_CATEGORIES,
    NormalizedCategory,
    NormalizedDealItemOutput,
    DealExpansionItem,
    BatchDealExpansionResponse,
    NormalizedItem,
    DealExpansionResponse,
    needs_multi_item_expansion,
    expand_and_normalize_deals_batch,
    expand_and_normalize_deal,
    expand_and_normalize_deals,
    DealNormalizer,
    get_default_semaphore,
)


class TestDealNormalizerSchema:
    def test_normalized_item_valid_categories(self):
        for cat in VALID_CATEGORIES:
            item = NormalizedDealItemOutput(
                clean_name="test item",
                normalized_category=cat,
                unit="lb",
                qualifiers=["fresh"],
            )
            assert item.clean_name == "test item"
            assert item.normalized_category == cat
            assert item.unit == "lb"
            assert item.qualifiers == ["fresh"]

    def test_normalized_item_category_mapping(self):
        item = NormalizedDealItemOutput(
            clean_name="ground beef",
            normalized_category="meat",
            unit="lb",
        )
        assert item.normalized_category == "Meat"

        item_seafood = NormalizedDealItemOutput(
            clean_name="salmon fillet",
            normalized_category="fish",
            unit="lb",
        )
        assert item_seafood.normalized_category == "Seafood"

        item_produce = NormalizedDealItemOutput(
            clean_name="apples",
            normalized_category="fruits",
            unit="lb",
        )
        assert item_produce.normalized_category == "Produce"

        item_dairy = NormalizedDealItemOutput(
            clean_name="whole milk",
            normalized_category="milk",
            unit="gallon",
        )
        assert item_dairy.normalized_category == "Dairy"

        item_bakery = NormalizedDealItemOutput(
            clean_name="sourdough bread",
            normalized_category="bread",
            unit="each",
        )
        assert item_bakery.normalized_category == "Bakery"

        item_pantry = NormalizedDealItemOutput(
            clean_name="potato chips",
            normalized_category="snacks",
            unit="oz",
        )
        assert item_pantry.normalized_category == "Pantry"

    def test_batch_deal_expansion_response(self):
        resp = BatchDealExpansionResponse(
            expansions=[
                DealExpansionItem(
                    source_index=0,
                    items=[
                        NormalizedDealItemOutput(clean_name="honeycrisp apples", normalized_category="Produce", unit="lb"),
                        NormalizedDealItemOutput(clean_name="bartlett pears", normalized_category="Produce", unit="lb"),
                    ],
                ),
                DealExpansionItem(
                    source_index=1,
                    items=[
                        NormalizedDealItemOutput(clean_name="sirloin steak", normalized_category="Meat", unit="lb"),
                    ],
                ),
            ]
        )
        assert len(resp.expansions) == 2
        assert resp.expansions[0].source_index == 0
        assert len(resp.expansions[0].items) == 2
        assert resp.expansions[0].items[0].clean_name == "honeycrisp apples"
        assert resp.expansions[1].source_index == 1
        assert len(resp.expansions[1].items) == 1


class TestNeedsMultiItemExpansion:
    @pytest.mark.parametrize(
        "item_name",
        [
            "Honeycrisp Apples or Bartlett Pears",
            "Choice of Sirloin Steak or Salmon Fillet",
            "Coca-Cola, Diet Coke or Sprite 12-Pack",
            "T-Bone / Ribeye Steak",
            "Strawberries / Blackberries 16oz",
            "Fresh Atlantic Salmon or Tilapia Fillet",
            "Chef's Choice of Pork Chops or Chicken Breasts",
            "Doritos or Cheetos Snacks",
            "Pork Loin Chops or Boneless Chicken Thighs",
            "Red, Green or Black Seedless Grapes",
            "Yellow Peaches or Nectarines",
            "Tilapia/Catfish Fillets",
            "Choice of New York Strip or Ribeye",
        ],
    )
    def test_positive_multi_item_cases(self, item_name):
        assert needs_multi_item_expansion(item_name) is True

    @pytest.mark.parametrize(
        "item_name",
        [
            "Bacon and Eggs",
            "Mac and Cheese",
            "Strawberries and Cream Ice Cream",
            "Cookies and Cream",
            "Sweet and Sour Chicken",
            "Pork and Beans",
            "Salt and Pepper Grinder",
            "1/2 lb Organic Carrots",
            "3/4 oz Fresh Rosemary",
            "Chicken breast w/ broccoli",
            "Sandwich w/ cheese",
            "Salad w/o dressing",
            "Boneless Pork Chops",
            "Orange Juice",
            "Organic Sweet Corn",
            "Oreos 14.3 oz",
            "Flavor Blasted Goldfish",
            "Gala Apples $1.99/lb",
            "24/16.9 fl oz Water Bottles",
            "Ground Beef 80/20 1 lb",
            "Whole Milk 1 Gallon",
            "",
            None,
        ],
    )
    def test_negative_single_item_cases(self, item_name):
        assert needs_multi_item_expansion(item_name) is False


class TestExpandAndNormalizeDeal:
    @pytest.mark.anyio
    async def test_non_multi_item_deal_bypasses_llm(self):
        raw_deal = {
            "deal_id": "deal_001",
            "store_id": "store_123",
            "item_name": "Organic Honeycrisp Apples",
            "clean_name": "organic honeycrisp apples",
            "deal_price": 1.99,
            "unit": "lb",
            "valid_from": "2026-10-01T00:00:00Z",
            "valid_to": "2026-10-08T00:00:00Z",
        }
        mock_client = MagicMock()

        result = await expand_and_normalize_deal(raw_deal, mock_client)
        assert len(result) == 1
        assert result[0] == raw_deal
        mock_client.aio.models.generate_content.assert_not_called()

    @pytest.mark.anyio
    async def test_multi_item_expansion_success(self):
        raw_deal = {
            "deal_id": "deal_100",
            "store_id": "store_ralphs_1",
            "item_name": "Honeycrisp Apples or Bartlett Pears",
            "clean_name": "honeycrisp apples or bartlett pears",
            "category": "Produce",
            "deal_price": 1.49,
            "unit": "lb",
            "valid_from": datetime(2026, 10, 1, tzinfo=timezone.utc),
            "valid_to": datetime(2026, 10, 7, tzinfo=timezone.utc),
        }

        mock_expansion = DealExpansionResponse(
            items=[
                NormalizedItem(
                    clean_name="honeycrisp apples",
                    normalized_category="Produce",
                    unit="lb",
                    qualifiers=["honeycrisp"],
                ),
                NormalizedItem(
                    clean_name="bartlett pears",
                    normalized_category="Produce",
                    unit="lb",
                    qualifiers=["bartlett"],
                ),
            ]
        )

        mock_response = MagicMock()
        mock_response.parsed = mock_expansion

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        expanded = await expand_and_normalize_deal(raw_deal, mock_client)

        assert len(expanded) == 2

        # Item 0
        assert expanded[0]["deal_id"] == "deal_100_0"
        assert expanded[0]["clean_name"] == "honeycrisp apples"
        assert expanded[0]["normalized_category"] == "Produce"
        assert expanded[0]["unit"] == "lb"
        assert expanded[0]["store_id"] == "store_ralphs_1"
        assert expanded[0]["deal_price"] == 1.49
        assert expanded[0]["valid_from"] == raw_deal["valid_from"]
        assert expanded[0]["valid_to"] == raw_deal["valid_to"]

        # Item 1
        assert expanded[1]["deal_id"] == "deal_100_1"
        assert expanded[1]["clean_name"] == "bartlett pears"
        assert expanded[1]["normalized_category"] == "Produce"
        assert expanded[1]["unit"] == "lb"
        assert expanded[1]["store_id"] == "store_ralphs_1"
        assert expanded[1]["deal_price"] == 1.49
        assert expanded[1]["valid_from"] == raw_deal["valid_from"]
        assert expanded[1]["valid_to"] == raw_deal["valid_to"]

    @pytest.mark.anyio
    async def test_llm_failure_graceful_fallback(self):
        raw_deal = {
            "deal_id": "deal_200",
            "store_id": "store_albertsons_2",
            "item_name": "USDA Choice Ribeye or T-Bone Steak",
            "deal_price": 9.99,
            "unit": "lb",
            "valid_from": "2026-10-01",
            "valid_to": "2026-10-08",
        }

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("Rate limit exceeded"))

        expanded = await expand_and_normalize_deal(raw_deal, mock_client)
        assert len(expanded) == 1
        assert expanded[0] == raw_deal

    @pytest.mark.anyio
    async def test_batch_expansion_with_semaphore(self):
        deals = [
            {
                "deal_id": "deal_1",
                "store_id": "store_1",
                "item_name": "Gala Apples or Bosc Pears",
                "deal_price": 1.29,
                "unit": "lb",
            },
            {
                "deal_id": "deal_2",
                "store_id": "store_1",
                "item_name": "Fresh Atlantic Salmon",
                "deal_price": 7.99,
                "unit": "lb",
            },
            {
                "deal_id": "deal_3",
                "store_id": "store_1",
                "item_name": "Coke / Sprite 12pk",
                "deal_price": 5.00,
                "unit": "each",
            },
        ]

        mock_batch_response = BatchDealExpansionResponse(
            expansions=[
                DealExpansionItem(
                    source_index=0,
                    items=[
                        NormalizedDealItemOutput(clean_name="gala apples", normalized_category="Produce", unit="lb"),
                        NormalizedDealItemOutput(clean_name="bosc pears", normalized_category="Produce", unit="lb"),
                    ],
                ),
                DealExpansionItem(
                    source_index=1,
                    items=[
                        NormalizedDealItemOutput(clean_name="fresh atlantic salmon", normalized_category="Seafood", unit="lb"),
                    ],
                ),
                DealExpansionItem(
                    source_index=2,
                    items=[
                        NormalizedDealItemOutput(clean_name="coca-cola", normalized_category="Pantry", unit="each"),
                        NormalizedDealItemOutput(clean_name="sprite", normalized_category="Pantry", unit="each"),
                    ],
                ),
            ]
        )

        mock_response = MagicMock()
        mock_response.parsed = mock_batch_response

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        custom_semaphore = asyncio.Semaphore(2)
        results = await expand_and_normalize_deals(deals, mock_client, semaphore=custom_semaphore)

        # deal_1 expands to 2, deal_2 is single (1), deal_3 expands to 2 -> Total 5
        assert len(results) == 5
        deal_ids = [d["deal_id"] for d in results]
        assert "deal_1_0" in deal_ids
        assert "deal_1_1" in deal_ids
        assert "deal_2" in deal_ids
        assert "deal_3_0" in deal_ids
        assert "deal_3_1" in deal_ids

    @pytest.mark.anyio
    async def test_deal_normalizer_class_wrapper(self):
        deal = {
            "deal_id": "deal_999",
            "store_id": "store_aldi_1",
            "item_name": "Yellow Peaches or Nectarines",
            "deal_price": 1.19,
            "unit": "lb",
        }
        mock_expansion = BatchDealExpansionResponse(
            expansions=[
                DealExpansionItem(
                    source_index=0,
                    items=[
                        NormalizedDealItemOutput(clean_name="yellow peaches", normalized_category="Produce", unit="lb"),
                        NormalizedDealItemOutput(clean_name="nectarines", normalized_category="Produce", unit="lb"),
                    ],
                )
            ]
        )
        mock_response = MagicMock()
        mock_response.parsed = mock_expansion

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        normalizer = DealNormalizer(client=mock_client, max_concurrency=3)
        res = await normalizer.normalize_deal(deal)
        assert len(res) == 2
        assert res[0]["deal_id"] == "deal_999_0"
        assert res[0]["clean_name"] == "yellow peaches"
        assert res[1]["deal_id"] == "deal_999_1"
        assert res[1]["clean_name"] == "nectarines"


class TestExpandAndNormalizeDealsBatch:
    @pytest.mark.anyio
    async def test_expand_and_normalize_deals_batch_mixed_multi_and_single(self):
        deals = [
            {
                "deal_id": "d_1",
                "item_name": "Choice of Sirloin Steak or Salmon Fillet",
                "category": "Meat",
                "deal_price": 8.99,
                "unit": "lb",
            },
            {
                "deal_id": "d_2",
                "item_name": "Organic Whole Milk",
                "category": "Dairy",
                "deal_price": 3.49,
                "unit": "gallon",
            },
        ]

        mock_batch_resp = BatchDealExpansionResponse(
            expansions=[
                DealExpansionItem(
                    source_index=0,
                    items=[
                        NormalizedDealItemOutput(
                            clean_name="sirloin steak",
                            normalized_category="Meat",
                            unit="lb",
                            qualifiers=["sirloin"],
                        ),
                        NormalizedDealItemOutput(
                            clean_name="salmon fillet",
                            normalized_category="Seafood",
                            unit="lb",
                            qualifiers=["fillet"],
                        ),
                    ],
                ),
                DealExpansionItem(
                    source_index=1,
                    items=[
                        NormalizedDealItemOutput(
                            clean_name="organic whole milk",
                            normalized_category="Dairy",
                            unit="gallon",
                            qualifiers=["organic"],
                        ),
                    ],
                ),
            ]
        )

        mock_response = MagicMock()
        mock_response.parsed = mock_batch_resp

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await expand_and_normalize_deals_batch(
            deals=deals,
            client=mock_client,
            model="gemini-3.5-flash-lite",
        )

        assert len(result) == 3
        # First deal expanded into 2 items
        assert result[0]["deal_id"] == "d_1_0"
        assert result[0]["clean_name"] == "sirloin steak"
        assert result[0]["normalized_category"] == "Meat"
        assert result[0]["unit"] == "lb"
        assert result[0]["deal_price"] == 8.99

        assert result[1]["deal_id"] == "d_1_1"
        assert result[1]["clean_name"] == "salmon fillet"
        assert result[1]["normalized_category"] == "Seafood"
        assert result[1]["unit"] == "lb"
        assert result[1]["deal_price"] == 8.99

        # Second deal updated in-place (1 item)
        assert result[2]["deal_id"] == "d_2"
        assert result[2]["clean_name"] == "organic whole milk"
        assert result[2]["normalized_category"] == "Dairy"
        assert result[2]["unit"] == "gallon"
        assert result[2]["deal_price"] == 3.49

    @pytest.mark.anyio
    async def test_expand_and_normalize_deals_batch_api_error_fallback(self):
        deals = [
            {"deal_id": "d_1", "item_name": "Apples or Pears", "deal_price": 1.99},
        ]
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("429 Resource Exhausted"))

        result = await expand_and_normalize_deals_batch(deals=deals, client=mock_client)
        assert result == deals

    @pytest.mark.anyio
    async def test_expand_and_normalize_deals_batch_no_client(self):
        deals = [{"deal_id": "d_1", "item_name": "Apples"}]
        result = await expand_and_normalize_deals_batch(deals=deals, client=None)
        assert result == deals

    @pytest.mark.anyio
    async def test_expand_and_normalize_deals_batch_empty_deals(self):
        mock_client = MagicMock()
        result = await expand_and_normalize_deals_batch(deals=[], client=mock_client)
        assert result == []

    @pytest.mark.anyio
    async def test_expand_compound_brand_ocr_truncation(self):
        """
        Verifies that an item with OCR truncation like 'cray 5-6 oz. or Barilla Pesto Sauce 6.2-6.5 oz.'
        and compound brand 'PAM | Barilla' supplies the brand to Gemini prompt context
        and expands into two pantry items: cooking spray and pesto sauce.
        """
        deals = [
            {
                "deal_id": "deal_pam_barilla",
                "item_name": "cray 5-6 oz. or Barilla Pesto Sauce 6.2-6.5 oz.",
                "brand": "PAM | Barilla",
                "raw_category": "Grocery",
                "deal_price": 3.49,
                "unit": "each",
            }
        ]

        captured_contents = []

        async def fake_generate_content(model, contents, config):
            captured_contents.append(contents)
            return MagicMock(
                parsed=BatchDealExpansionResponse(
                    expansions=[
                        DealExpansionItem(
                            source_index=0,
                            items=[
                                NormalizedDealItemOutput(
                                    clean_name="cooking spray",
                                    normalized_category="Pantry",
                                    unit="each",
                                    qualifiers=["cooking spray"],
                                    brand="PAM",
                                ),
                                NormalizedDealItemOutput(
                                    clean_name="pesto sauce",
                                    normalized_category="Pantry",
                                    unit="each",
                                    qualifiers=["pesto"],
                                    brand="Barilla",
                                ),
                            ],
                        )
                    ]
                )
            )

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(side_effect=fake_generate_content)

        results = await expand_and_normalize_deals_batch(deals, mock_client)

        # Verify prompt contained brand and raw_category metadata
        assert len(captured_contents) == 1
        assert "PAM | Barilla" in captured_contents[0]
        assert "cray 5-6 oz." in captured_contents[0]

        # Verify expansion output
        assert len(results) == 2
        d0, d1 = results[0], results[1]

        assert d0["deal_id"] == "deal_pam_barilla_0"
        assert d0["clean_name"] == "cooking spray"
        assert d0["normalized_category"] == "Pantry"
        assert d0["brand"] == "PAM"
        assert d0["deal_price"] == 3.49

        assert d1["deal_id"] == "deal_pam_barilla_1"
        assert d1["clean_name"] == "pesto sauce"
        assert d1["normalized_category"] == "Pantry"
        assert d1["brand"] == "Barilla"
        assert d1["deal_price"] == 3.49


