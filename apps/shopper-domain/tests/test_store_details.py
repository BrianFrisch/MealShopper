from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from dependencies import get_store_repository
from main import app


class FakeStoreRepository:
    async def get_store_context(self, store_id: str):
        if store_id != "smartfinal-529":
            return None
        return SimpleNamespace(
            id="smartfinal-529",
            name="Smart & Final",
            street="123 Main St",
            city="Los Angeles",
            state="CA",
            zip_code="90007",
        )


@pytest.fixture
def client():
    app.dependency_overrides[get_store_repository] = FakeStoreRepository
    yield TestClient(app)
    app.dependency_overrides.pop(get_store_repository, None)


def test_get_store_details_returns_name_and_address(client):
    response = client.get("/v1/shopper/stores/smartfinal-529")

    assert response.status_code == 200
    assert response.json() == {
        "id": "smartfinal-529",
        "store_id": "smartfinal-529",
        "name": "Smart & Final",
        "address": "123 Main St",
        "street": "123 Main St",
        "city": "Los Angeles",
        "state": "CA",
        "zip_code": "90007",
        "postal_code": "90007",
    }


def test_get_store_details_returns_not_found_for_unknown_store(client):
    response = client.get("/v1/shopper/stores/unknown-store")

    assert response.status_code == 404
