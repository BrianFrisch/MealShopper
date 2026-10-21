from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi import HTTPException

import main
from src.models import MealPlanResponse, PlannedMeal
from src.services.recipe_service import RecipeService


class FakeConnection:
    def __init__(self) -> None:
        self.fetchval_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_result: dict[str, Any] | None = None
        self.fetch_results: list[dict[str, Any]] = []
        self.next_recipe_id = UUID("8b8e74c3-b048-4b9d-810c-2bd756c62810")

    @asynccontextmanager
    async def transaction(self):
        yield

    async def fetchval(self, query: str, *args: Any) -> UUID:
        self.fetchval_calls.append((query, args))
        return args[0]

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((query, args))
        return "SELECT 1"

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        assert "fn_get_recipe" in query
        assert len(args) == 1
        assert args[0] == self.next_recipe_id
        return self.fetchrow_result

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        assert "fn_get_recipes_for_user" in query
        assert len(args) == 1
        return self.fetch_results


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


@pytest.mark.asyncio
async def test_persist_meal_plan_saves_and_associates_each_recipe() -> None:
    connection = FakeConnection()
    service = RecipeService("unused", pool=FakePool(connection))  # type: ignore[arg-type]
    user_id = UUID("207d2de7-919d-4f48-b6f2-4a475ae96426")
    meal_plan = MealPlanResponse(
        plan_id="plan-1",
        meals=[
            PlannedMeal(
                meal_id="meal-1",
                recipe_name="Herb chicken",
                description="Chicken with herbs",
                estimated_prep_time_minutes=30,
                servings=2,
                ingredients=[],
                instructions=["Cook chicken."]
            )
        ]
    )

    await service.persist_meal_plan(user_id, meal_plan)

    assert meal_plan.meals[0].meal_id == str(connection.fetchval_calls[0][1][0])
    assert len(connection.fetchval_calls) == 1
    query, args = connection.fetchval_calls[0]
    assert "CALL sp_create_recipe" in query
    assert isinstance(args[0], UUID)
    assert args[1:3] == ("plan-1", "meal-1")
    assert len(connection.execute_calls) == 1
    assert "CALL sp_associate_user_recipe" in connection.execute_calls[0][0]
    assert connection.execute_calls[0][1] == (user_id, args[0])


@pytest.mark.asyncio
async def test_get_recipe_deserializes_json_recipe_data() -> None:
    connection = FakeConnection()
    connection.fetchrow_result = {
        "recipe_id": connection.next_recipe_id,
        "meal_plan_id": "plan-1",
        "source_meal_id": "meal-1",
        "recipe_data": '{"meal_id":"recipe-id","recipe_name":"Herb chicken"}',
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    service = RecipeService("unused", pool=FakePool(connection))  # type: ignore[arg-type]

    recipe = await service.get_recipe(connection.next_recipe_id)

    assert recipe is not None
    assert recipe["recipe"]["recipe_name"] == "Herb chicken"
    assert recipe["recipe_id"] == str(connection.next_recipe_id)
    assert recipe["source_meal_id"] == "meal-1"


@pytest.mark.asyncio
async def test_generate_plan_persists_mock_result_for_request_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = UUID("207d2de7-919d-4f48-b6f2-4a475ae96426")
    persisted: list[tuple[UUID, MealPlanResponse]] = []

    class RecordingRecipeService:
        async def persist_meal_plan(self, requested_user_id: UUID, meal_plan: MealPlanResponse) -> None:
            persisted.append((requested_user_id, meal_plan))

    monkeypatch.setenv("PLANNER_USE_MOCK", "true")
    monkeypatch.setattr(main, "recipe_service", RecordingRecipeService())

    response = await main.generate_plan(
        main.MealPlanRequest(user_id=user_id, scored_deals=[])
    )

    assert persisted[0][0] == user_id
    assert persisted[0][1] is response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("generation_error", "expected_status"),
    [
        (RuntimeError("provider returned an invalid response"), 502),
        (RuntimeError("generation service is busy"), 503),
    ],
)
async def test_generate_plan_returns_provider_errors_without_mock_fallback(
    monkeypatch: pytest.MonkeyPatch,
    generation_error: Exception,
    expected_status: int,
) -> None:
    persisted: list[MealPlanResponse] = []
    mock_calls: list[bool] = []

    class FailingPlanner:
        client = object()
        model_name = "test-model"

        async def generate_plan(self, **kwargs: Any) -> MealPlanResponse:
            raise generation_error

    class RecordingMockPlanner:
        async def generate_mock_plan(self, request: main.MealPlanRequest) -> MealPlanResponse:
            mock_calls.append(True)
            raise AssertionError("Mock planner must not be called after a provider failure.")

    class RecordingRecipeService:
        async def persist_meal_plan(
            self,
            requested_user_id: UUID,
            meal_plan: MealPlanResponse,
        ) -> None:
            persisted.append(meal_plan)

    monkeypatch.setenv("PLANNER_USE_MOCK", "false")
    monkeypatch.setattr(main, "planner_service", FailingPlanner())
    monkeypatch.setattr(main, "mock_planner_service", RecordingMockPlanner())
    monkeypatch.setattr(main, "recipe_service", RecordingRecipeService())

    with pytest.raises(HTTPException) as exc_info:
        await main.generate_plan(
            main.MealPlanRequest(
                user_id=UUID("207d2de7-919d-4f48-b6f2-4a475ae96426"),
                scored_deals=[],
            )
        )

    assert exc_info.value.status_code == expected_status
    assert mock_calls == []
    assert persisted == []


@pytest.mark.asyncio
async def test_generate_plan_returns_unavailable_when_provider_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLANNER_USE_MOCK", "false")
    monkeypatch.setattr(main, "planner_service", SimpleNamespace(client=None))

    with pytest.raises(HTTPException) as exc_info:
        await main.generate_plan(
            main.MealPlanRequest(
                user_id=UUID("207d2de7-919d-4f48-b6f2-4a475ae96426"),
                scored_deals=[],
            )
        )

    assert exc_info.value.status_code == 503
