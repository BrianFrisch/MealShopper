from typing import Any, Dict, List
import unittest
from unittest.mock import AsyncMock, patch

from src.services.store_importer import (
    ParsedStore,
    StoreImportService,
    clean_store_number,
    deduplicate_stores,
    is_matching_banner,
    is_matching_state,
    normalize_state,
    parse_geojson_feature,
    resolve_address,
)


class TestStoreImporterHelpers(unittest.TestCase):
    def test_clean_store_number(self):
        self.assertEqual(clean_store_number("00123", "fallback-1"), "123")
        self.assertEqual(clean_store_number("Store #456", "fallback-1"), "456")
        self.assertEqual(clean_store_number(None, "node/789"), "789")
        self.assertEqual(clean_store_number(None, "abc"), "0")
        self.assertEqual(clean_store_number("", "fallback-99"), "0")

    def test_normalize_state(self):
        self.assertEqual(normalize_state("CA"), "CA")
        self.assertEqual(normalize_state("ny"), "NY")
        self.assertEqual(normalize_state(" TX "), "TX")

    def test_is_matching_state(self):
        self.assertTrue(is_matching_state("CA", "CA"))
        self.assertTrue(is_matching_state("ca", "CA"))
        self.assertFalse(is_matching_state("NY", "CA"))
        self.assertTrue(is_matching_state("", "CA"))
        self.assertTrue(is_matching_state("CA", ""))

    def test_is_matching_banner(self):
        self.assertTrue(is_matching_banner("Ralphs", "ralphs"))
        self.assertTrue(is_matching_banner("Ralphs Fresh Fare", "ralphs"))
        self.assertFalse(is_matching_banner("Food 4 Less", "ralphs"))
        self.assertFalse(is_matching_banner("Ralphs Fuel Center", "ralphs"))
        self.assertFalse(is_matching_banner("Ralphs Gas Station", "ralphs"))

    def test_resolve_address(self):
        props_full = {"addr:full": "123 Main St", "addr:city": "Los Angeles", "addr:postcode": "90001"}
        street, city, zip_code = resolve_address(props_full)
        self.assertEqual(street, "123 Main St")
        self.assertEqual(city, "Los Angeles")
        self.assertEqual(zip_code, "90001")

        props_parts = {"addr:housenumber": "456", "addr:street": "Oak Ave", "city": "Irvine"}
        street, city, zip_code = resolve_address(props_parts)
        self.assertEqual(street, "456 Oak Ave")
        self.assertEqual(city, "Irvine")
        self.assertEqual(zip_code, "00000")

        props_empty: Dict[str, Any] = {}
        street, city, zip_code = resolve_address(props_empty)
        self.assertEqual(street, "Address Unspecified")
        self.assertEqual(city, "Unknown")
        self.assertEqual(zip_code, "00000")

    def test_parse_geojson_feature(self):
        meta: Dict[str, str] = {
            "chain_id": "ralphs",
            "display_name": "Ralphs",
            "adapter_name": "ralphs",
            "spider": "kroger_us",
        }
        valid_feat: Dict[str, Any] = {
            "id": "node/100",
            "geometry": {"coordinates": [-118.25, 34.05]},
            "properties": {
                "name": "Ralphs",
                "ref": "00703",
                "addr:state": "CA",
                "street_address": "100 Grand Ave",
                "addr:city": "Los Angeles",
                "addr:postcode": "90012",
            },
        }

        parsed = parse_geojson_feature(valid_feat, "ralphs", meta, "CA")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["store_id"], "ralphs-703")
        self.assertEqual(parsed["store_number"], "703")
        self.assertEqual(parsed["store_name"], "Ralphs")
        self.assertEqual(parsed["street_address"], "100 Grand Ave")
        self.assertEqual(parsed["city"], "Los Angeles")
        self.assertEqual(parsed["postal_code"], "90012")
        self.assertEqual(parsed["longitude"], -118.25)
        self.assertEqual(parsed["latitude"], 34.05)

        # Filtered out by state
        feat_wrong_state: Dict[str, Any] = {**valid_feat, "properties": {**valid_feat["properties"], "addr:state": "NV"}}
        self.assertIsNone(parse_geojson_feature(feat_wrong_state, "ralphs", meta, "CA"))

        # Filtered out by banner
        feat_wrong_banner: Dict[str, Any] = {**valid_feat, "properties": {**valid_feat["properties"], "name": "Food 4 Less"}}
        self.assertIsNone(parse_geojson_feature(feat_wrong_banner, "ralphs", meta, "CA"))

    def test_deduplicate_stores(self):
        stores: List[ParsedStore] = [
            {
                "store_id": "ralphs-7030012009",
                "chain_id": "ralphs",
                "store_number": "7030012009",
                "store_name": "Ralphs Fuel",
                "street_address": "100 Main St",
                "city": "LA",
                "state_province": "CA",
                "postal_code": "90001",
                "longitude": -118.24368,
                "latitude": 34.05223,
            },
            {
                "store_id": "ralphs-120",
                "chain_id": "ralphs",
                "store_number": "120",
                "store_name": "Ralphs",
                "street_address": "100 Main St",
                "city": "LA",
                "state_province": "CA",
                "postal_code": "90001",
                "longitude": -118.24371,
                "latitude": 34.05221,
            },
        ]
        deduped = deduplicate_stores(stores)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["store_number"], "120")


class TestStoreImportService(unittest.IsolatedAsyncioTestCase):
    async def test_get_chain_metadata(self):
        mock_chain_service = AsyncMock()
        mock_chain_service.get_chain_metadata.return_value = {
            "chain_id": "ralphs",
            "display_name": "Ralphs",
            "adapter_name": "ralphs",
            "spider_name": "kroger_us",
            "flyer_source_type": "flipp",
        }
        service = StoreImportService(
            db_url="postgresql://mock:5432/mock",
            chain_service=mock_chain_service,
        )

        meta = await service.get_chain_metadata("ralphs")
        self.assertEqual(meta["chain_id"], "ralphs")
        self.assertEqual(meta["display_name"], "Ralphs")
        self.assertEqual(meta["adapter_name"], "ralphs")
        mock_chain_service.get_chain_metadata.assert_awaited_once_with("ralphs")

    async def test_get_chain_metadata_not_found(self):
        mock_chain_service = AsyncMock()
        mock_chain_service.get_chain_metadata.side_effect = ValueError("Unsupported chain")
        service = StoreImportService(
            db_url="postgresql://mock:5432/mock",
            chain_service=mock_chain_service,
        )

        with self.assertRaises(ValueError):
            await service.get_chain_metadata("unknown_chain")

    async def test_persist_stores_upserts_chain_through_chain_service(self):
        mock_chain_service = AsyncMock()
        service = StoreImportService(
            db_url="postgresql://mock:5432/mock",
            chain_service=mock_chain_service,
        )
        mock_conn = AsyncMock()
        metadata = {
            "display_name": "Ralphs",
            "adapter_name": "ralphs",
            "spider": "kroger_us",
            "flyer_source_type": "flipp",
        }

        with patch("src.services.store_importer.asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
            await service._persist_stores("ralphs", metadata, [])

        mock_chain_service.upsert_chain.assert_awaited_once_with(
            chain_id="ralphs",
            display_name="Ralphs",
            adapter_name="ralphs",
            spider_name="kroger_us",
            flyer_source_type="flipp",
        )
        mock_conn.execute.assert_awaited_once()

    async def test_store_import_service_orchestration(self):
        service = StoreImportService(db_url="postgresql://mock:5432/mock")

        mock_meta = {
            "chain_id": "aldi",
            "display_name": "ALDI",
            "adapter_name": "aldi",
            "spider": "aldi_sud_us",
            "spider_name": "aldi_sud_us",
            "flyer_source_type": "flipp",
        }

        mock_geojson = {
            "features": [
                {
                    "id": "node/1",
                    "geometry": {"coordinates": [-118.25, 34.05]},
                    "properties": {
                        "name": "ALDI",
                        "ref": "101",
                        "addr:state": "CA",
                        "street_address": "500 Main St",
                        "addr:city": "Los Angeles",
                        "addr:postcode": "90012",
                    },
                }
            ]
        }

        with patch.object(service, "get_chain_metadata", new=AsyncMock(return_value=mock_meta)), \
             patch.object(service, "_fetch_geojson", new=AsyncMock(return_value=mock_geojson)), \
             patch.object(service, "_persist_stores", new=AsyncMock()) as mock_persist:

            result = await service.run_import_alltheplaces("aldi", "CA")

            self.assertEqual(result["chain_id"], "aldi")
            self.assertEqual(result["display_name"], "ALDI")
            self.assertEqual(result["region"], "CA")
            self.assertEqual(result["imported_count"], 1)
            mock_persist.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
