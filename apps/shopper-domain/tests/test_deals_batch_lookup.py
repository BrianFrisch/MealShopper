import pytest
from fastapi.testclient import TestClient

from dependencies import get_deal_storage
from main import app


LIVE_DEALS = [
    {
        "deal_id": "vons-5605136_1046379157_1",
        "store_id": "vons-5605136",
        "store_name": "Vons",
        "item_name": "Boneless Skinless Chicken Breast",
        "normalized_category": "Meat",
        "deal_price": 2.99,
        "original_price": 4.99,
        "unit": "lb",
        "value_score": 8.5,
    },
    {
        "deal_id": "vons-5605136_1046379154",
        "store_id": "vons-5605136",
        "store_name": "Vons",
        "item_name": "Ground Beef",
        "normalized_category": "Meat",
        "deal_price": 3.99,
        "original_price": 5.99,
        "unit": "lb",
        "value_score": 8.0,
    },
]


class FakeDealStorage:
    async def get_deals_for_stores(self, store_ids, tier):
        return {
            store_id: [
                deal for deal in LIVE_DEALS if deal["store_id"] == store_id
            ]
            for store_id in store_ids
        }

    async def get_deals_by_keys(self, deal_store_pairs):
        pairs = set(deal_store_pairs)
        return [
            deal
            for deal in LIVE_DEALS
            if (deal["store_id"], deal["deal_id"]) in pairs
        ]


@pytest.fixture
def client():
    app.dependency_overrides[get_deal_storage] = FakeDealStorage
    yield TestClient(app)
    app.dependency_overrides.pop(get_deal_storage, None)


def test_batch_lookup_returns_live_deals_and_rejects_mismatched_store(client):
    response = client.post(
        "/v1/shopper/deals/batch-lookup",
        json={
            "items": [
                {
                    "deal_id": LIVE_DEALS[0]["deal_id"],
                    "store_id": LIVE_DEALS[0]["store_id"],
                },
                {
                    "deal_id": LIVE_DEALS[1]["deal_id"],
                    "store_id": LIVE_DEALS[1]["store_id"],
                },
                {
                    "deal_id": LIVE_DEALS[0]["deal_id"],
                    "store_id": "another-store",
                },
                {
                    "deal_id": "unknown-deal",
                    "store_id": LIVE_DEALS[0]["store_id"],
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_found"] == 2
    assert [deal["deal_id"] for deal in data["deals"]] == [
        LIVE_DEALS[0]["deal_id"],
        LIVE_DEALS[1]["deal_id"],
    ]
    assert data["deals"][0]["primary_ingredient"] == LIVE_DEALS[0]["item_name"]
    assert data["deals"][0]["price"] == LIVE_DEALS[0]["deal_price"]


def test_batch_lookup_empty_request(client):
    response = client.post("/v1/shopper/deals/batch-lookup", json={"items": []})

    assert response.status_code == 200
    assert response.json() == {"deals": [], "total_found": 0}


def test_score_deals_uses_live_data_and_avoid_filters(client):
    response = client.post(
        "/v1/shopper/deals/score",
        json={
            "store_ids": ["vons-5605136"],
            "avoid_ingredients": ["chicken"],
            "top_n": 10,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_scored"] == 1
    assert data["deals"][0]["deal_id"] == LIVE_DEALS[1]["deal_id"]
    assert data["deals"][0]["deal_score"] == 50.09


def test_match_ingredients_uses_live_data(client):
    response = client.post(
        "/v1/shopper/deals/match",
        json={
            "store_ids": ["vons-5605136"],
            "missing_ingredients": ["chicken breast"],
            "similarity_threshold": 65,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_matched"] == 1
    assert data["matches"][0]["deal_id"] == LIVE_DEALS[0]["deal_id"]
