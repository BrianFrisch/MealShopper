from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from main import app
from deal_service import DealRepository
from dependencies import get_deal_repository


@pytest.fixture
def client():
    return TestClient(app)


def test_batch_lookup_deals_endpoint(client):
    response = client.post(
        "/v1/shopper/deals/batch-lookup",
        json={
            "items": [
                {"deal_id": "deal_go_01", "store_id": "store_grocery_outlet_01"},
                {"deal_id": "deal_vons_01", "store_id": "store_vons_01"},
                {"deal_id": "non_existent_deal", "store_id": "store_vons_01"},
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "deals" in data
    assert "total_found" in data
    assert data["total_found"] == 2
    assert len(data["deals"]) == 2

    deal_ids = {d["deal_id"] for d in data["deals"]}
    assert "deal_go_01" in deal_ids
    assert "deal_vons_01" in deal_ids

    # Verify all deal fields are returned
    first_deal = next(d for d in data["deals"] if d["deal_id"] == "deal_go_01")
    assert first_deal["store_id"] == "store_grocery_outlet_01"
    assert first_deal["store_name"] == "Grocery Outlet"
    assert first_deal["item_name"] == "Boneless Skinless Chicken Breast"
    assert first_deal["category"] == "Meat & Poultry"
    assert first_deal["price"] == 2.49
    assert first_deal["unit"] == "lbs"
    assert first_deal["discount_percentage"] == 35.0
    assert first_deal["primary_ingredient"] == "Chicken Breast"


def test_batch_lookup_deals_empty_list(client):
    response = client.post(
        "/v1/shopper/deals/batch-lookup",
        json={"items": []},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_found"] == 0
    assert data["deals"] == []
