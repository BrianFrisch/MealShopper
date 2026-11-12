from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest

from src.services.shopping_list_service import ShoppingListService


class FakeConnection:
    def __init__(self) -> None:
        self.fetchval_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_result: dict[str, Any] | None = None
        self.fetch_results: list[dict[str, Any]] = []

    async def fetchval(self, query: str, *args: Any) -> UUID | None:
        self.fetchval_calls.append((query, args))
        return args[0] if args else None

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((query, args))
        return "SELECT 1"

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        return self.fetchrow_result

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        return self.fetch_results


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


@pytest.mark.asyncio
async def test_get_meal_plan_ingredients() -> None:
    connection = FakeConnection()
    plan_id = UUID("11111111-1111-1111-1111-111111111111")
    ing_id = UUID("22222222-2222-2222-2222-222222222222")
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    connection.fetch_results = [
        {
            "meal_plan_ingredient_id": ing_id,
            "meal_plan_id": plan_id,
            "recipe_id": None,
            "deal_id": "store1_deal123",
            "is_promotional": True,
            "ingredient_name": "Garlic",
            "ingredient_quantity": "3 cloves",
            "is_purchased": False,
            "created_at": now,
            "updated_at": now,
        }
    ]
    service = ShoppingListService("unused", pool=FakePool(connection))  # type: ignore[arg-type]

    items = await service.get_meal_plan_ingredients(plan_id)

    assert len(items) == 1
    assert items[0]["ingredient_name"] == "Garlic"
    assert items[0]["store_id"] == "store1"
    assert items[0]["is_promotional"] is True


@pytest.mark.asyncio
async def test_add_shopping_list_item() -> None:
    connection = FakeConnection()
    plan_id = UUID("11111111-1111-1111-1111-111111111111")
    ing_id = UUID("33333333-3333-3333-3333-333333333333")
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    connection.fetchrow_result = {
        "meal_plan_ingredient_id": ing_id,
        "meal_plan_id": plan_id,
        "recipe_id": None,
        "deal_id": None,
        "is_promotional": False,
        "ingredient_name": "Olive oil",
        "ingredient_quantity": "1 bottle",
        "is_purchased": False,
        "created_at": now,
        "updated_at": now,
    }
    service = ShoppingListService("unused", pool=FakePool(connection))  # type: ignore[arg-type]

    added = await service.add_shopping_list_item(plan_id, "Olive oil", "1 bottle")

    assert added is not None
    assert added["meal_plan_ingredient_id"] == str(ing_id)
    assert added["ingredient_name"] == "Olive oil"
    assert added["store_id"] is None


@pytest.mark.asyncio
async def test_remove_shopping_list_item_custom_deletes() -> None:
    connection = FakeConnection()
    plan_id = UUID("11111111-1111-1111-1111-111111111111")
    ing_id = UUID("33333333-3333-3333-3333-333333333333")
    # Custom item has recipe_id = None
    connection.fetchrow_result = {"recipe_id": None}
    service = ShoppingListService("unused", pool=FakePool(connection))  # type: ignore[arg-type]

    status = await service.remove_shopping_list_item(plan_id, ing_id)

    assert status == "removed"
    assert any("DELETE FROM meal_plan_ingredient" in call[0] for call in connection.execute_calls)


@pytest.mark.asyncio
async def test_remove_shopping_list_item_recipe_ingredient_marks_purchased() -> None:
    connection = FakeConnection()
    plan_id = UUID("11111111-1111-1111-1111-111111111111")
    ing_id = UUID("33333333-3333-3333-3333-333333333333")
    # Recipe ingredient has recipe_id != None
    connection.fetchrow_result = {"recipe_id": UUID("44444444-4444-4444-4444-444444444444")}
    service = ShoppingListService("unused", pool=FakePool(connection))  # type: ignore[arg-type]

    status = await service.remove_shopping_list_item(plan_id, ing_id)

    assert status == "purchased"
    assert any("SET is_purchased = TRUE" in call[0] for call in connection.execute_calls)
