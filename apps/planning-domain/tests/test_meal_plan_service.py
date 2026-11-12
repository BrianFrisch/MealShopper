from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest

from src.services.meal_plan_service import MealPlanService


class FakeConnection:
    def __init__(self) -> None:
        self.fetchval_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_result: dict[str, Any] | None = None
        self.fetch_results: list[dict[str, Any]] = []

    async def fetchval(self, query: str, *args: Any) -> UUID:
        self.fetchval_calls.append((query, args))
        return args[0]

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
async def test_create_meal_plan() -> None:
    connection = FakeConnection()
    service = MealPlanService("unused", pool=FakePool(connection))  # type: ignore[arg-type]
    user_id = UUID("207d2de7-919d-4f48-b6f2-4a475ae96426")
    plan_id = UUID("11111111-1111-1111-1111-111111111111")

    result_id = await service.create_meal_plan(user_id, "Weekly Dinners", plan_id)

    assert result_id == plan_id
    assert len(connection.fetchval_calls) == 1
    assert "CALL sp_create_meal_plan" in connection.fetchval_calls[0][0]
    assert connection.fetchval_calls[0][1] == (plan_id, "Weekly Dinners", user_id)


@pytest.mark.asyncio
async def test_update_meal_plan() -> None:
    connection = FakeConnection()
    service = MealPlanService("unused", pool=FakePool(connection))  # type: ignore[arg-type]
    plan_id = UUID("11111111-1111-1111-1111-111111111111")

    await service.update_meal_plan(plan_id, "Renamed Dinners", True)

    assert connection.execute_calls == [
        ("CALL sp_update_meal_plan($1, $2, $3);", (plan_id, "Renamed Dinners", True))
    ]


@pytest.mark.asyncio
async def test_associate_and_remove_recipe() -> None:
    connection = FakeConnection()
    service = MealPlanService("unused", pool=FakePool(connection))  # type: ignore[arg-type]
    plan_id = UUID("11111111-1111-1111-1111-111111111111")
    recipe_id = UUID("22222222-2222-2222-2222-222222222222")

    await service.associate_meal_plan_with_recipe(plan_id, recipe_id)
    await service.remove_recipe_from_meal_plan(plan_id, recipe_id)

    assert connection.execute_calls == [
        ("CALL sp_associate_meal_plan_recipe($1, $2);", (plan_id, recipe_id)),
        ("CALL sp_remove_meal_plan_recipe($1, $2);", (plan_id, recipe_id)),
    ]


@pytest.mark.asyncio
async def test_get_meal_plan() -> None:
    connection = FakeConnection()
    plan_id = UUID("11111111-1111-1111-1111-111111111111")
    user_id = UUID("207d2de7-919d-4f48-b6f2-4a475ae96426")
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    connection.fetchrow_result = {
        "meal_plan_id": plan_id,
        "meal_plan_name": "Test Plan",
        "user_id": user_id,
        "is_archived": False,
        "recipe_count": 2,
        "created_at": now,
        "updated_at": now,
    }
    service = MealPlanService("unused", pool=FakePool(connection))  # type: ignore[arg-type]

    plan = await service.get_meal_plan(plan_id)

    assert plan is not None
    assert plan["meal_plan_id"] == str(plan_id)
    assert plan["meal_plan_name"] == "Test Plan"
    assert plan["recipe_count"] == 2
