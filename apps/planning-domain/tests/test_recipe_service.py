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
        self.ingredient_fetch_results: list[dict[str, Any]] = []
        self.fetchval_override: UUID | None = None
        self.next_recipe_id = UUID("8b8e74c3-b048-4b9d-810c-2bd756c62810")

    @asynccontextmanager
    async def transaction(self):
        yield

    async def fetchval(self, query: str, *args: Any) -> UUID:
        self.fetchval_calls.append((query, args))
        if self.fetchval_override is not None:
            return self.fetchval_override
        return args[0]

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((query, args))
        return "SELECT 1"

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        if "user_recipe" in query:
            assert len(args) == 2
            assert args[0] == self.next_recipe_id
            return self.fetchrow_result
        assert "fn_get_recipe" in query
        assert len(args) == 1
        assert args[0] == self.next_recipe_id
        return self.fetchrow_result

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        if "FROM meal_plan_ingredient" in query:
            assert len(args) == 1
            return self.ingredient_fetch_results
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
                protein_subtype="Chicken",
                cuisine="Mediterranean",
                image_url="https://example.com/chicken.jpg",
                estimated_prep_time_minutes=30,
                servings=2,
                ingredients=[],
                instructions=["Cook chicken."]
            )
        ]
    )

    await service.persist_meal_plan(user_id, meal_plan)

    assert len(connection.fetchval_calls) == 1
    recipe_query, recipe_args = connection.fetchval_calls[0]
    assert "CALL sp_create_recipe" in recipe_query
    assert isinstance(recipe_args[0], UUID)
    assert meal_plan.meals[0].meal_id == str(recipe_args[0])
    assert recipe_args[1:6] == (
        "Herb chicken",
        "Chicken with herbs",
        "Chicken",
        "Mediterranean",
        "https://example.com/chicken.jpg",
    )
    assert recipe_args[6:8] == ("[]", '["Cook chicken."]')

    assert len(connection.execute_calls) == 1
    assert "CALL sp_associate_user_recipe" in connection.execute_calls[0][0]
    assert connection.execute_calls[0][1] == (user_id, recipe_args[0])


@pytest.mark.asyncio
async def test_get_recipe_deserializes_json_fields() -> None:
    connection = FakeConnection()
    connection.fetchrow_result = {
        "recipe_id": connection.next_recipe_id,
        "title": "Herb chicken",
        "description": "Chicken with herbs",
        "protein_subtype": "Chicken",
        "cuisine": "Mediterranean",
        "image_url": "https://example.com/chicken.jpg",
        "ingredients": '[{"name":"Chicken","quantity":"1 lb","is_promotional":true}]',
        "directions": '["Cook chicken."]',
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    service = RecipeService("unused", pool=FakePool(connection))  # type: ignore[arg-type]

    recipe = await service.get_recipe(connection.next_recipe_id)

    assert recipe is not None
    assert recipe["recipe_id"] == str(connection.next_recipe_id)
    assert recipe["title"] == "Herb chicken"
    assert recipe["description"] == "Chicken with herbs"
    assert recipe["protein_subtype"] == "Chicken"
    assert recipe["cuisine"] == "Mediterranean"
    assert recipe["image_url"] == "https://example.com/chicken.jpg"
    assert recipe["ingredients"][0]["name"] == "Chicken"
    assert recipe["directions"] == ["Cook chicken."]


@pytest.mark.asyncio
async def test_get_recipe_for_user_checks_user_association() -> None:
    connection = FakeConnection()
    connection.fetchrow_result = {
        "recipe_id": connection.next_recipe_id,
        "title": "Herb chicken",
        "description": "Chicken with herbs",
        "protein_subtype": "Chicken",
        "cuisine": "Mediterranean",
        "image_url": "https://example.com/chicken.jpg",
        "ingredients": '[{"name":"Chicken","quantity":"1 lb"}]',
        "directions": '["Cook chicken."]',
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    service = RecipeService("unused", pool=FakePool(connection))  # type: ignore[arg-type]
    user_id = UUID("207d2de7-919d-4f48-b6f2-4a475ae96426")

    recipe = await service.get_recipe_for_user(connection.next_recipe_id, user_id)

    assert recipe is not None
    assert recipe["recipe_id"] == str(connection.next_recipe_id)


@pytest.mark.asyncio
async def test_update_meal_plan_passes_archive_state_to_database() -> None:
    connection = FakeConnection()
    service = RecipeService("unused", pool=FakePool(connection))  # type: ignore[arg-type]
    meal_plan_id = UUID("11111111-1111-1111-1111-111111111111")

    await service.update_meal_plan(meal_plan_id, "Weeknight Favorites", True)

    assert connection.execute_calls == [
        (
            "CALL sp_update_meal_plan($1, $2, $3);",
            (meal_plan_id, "Weeknight Favorites", True),
        )
    ]


@pytest.mark.asyncio
async def test_meal_plan_recipe_add_and_remove_use_sync_procedures() -> None:
    connection = FakeConnection()
    service = RecipeService("unused", pool=FakePool(connection))  # type: ignore[arg-type]
    meal_plan_id = UUID("11111111-1111-1111-1111-111111111111")
    recipe_id = UUID("33333333-3333-3333-3333-333333333333")

    await service.associate_meal_plan_with_recipe(meal_plan_id, recipe_id)
    await service.remove_recipe_from_meal_plan(meal_plan_id, recipe_id)

    assert connection.execute_calls == [
        (
            "CALL sp_associate_meal_plan_recipe($1, $2);",
            (meal_plan_id, recipe_id),
        ),
        (
            "CALL sp_remove_meal_plan_recipe($1, $2);",
            (meal_plan_id, recipe_id),
        ),
    ]


@pytest.mark.asyncio
async def test_get_meal_plan_ingredients_derives_store_from_deal_id() -> None:
    connection = FakeConnection()
    meal_plan_id = UUID("11111111-1111-1111-1111-111111111111")
    recipe_id = UUID("33333333-3333-3333-3333-333333333333")
    ingredient_id = UUID("44444444-4444-4444-4444-444444444444")
    connection.ingredient_fetch_results = [
        {
            "meal_plan_ingredient_id": ingredient_id,
            "meal_plan_id": meal_plan_id,
            "recipe_id": recipe_id,
            "deal_id": "store-123_deal-456",
            "is_promotional": True,
            "ingredient_name": "Chicken",
            "ingredient_quantity": "1 lb",
            "is_purchased": False,
            "created_at": datetime(2026, 10, 25, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 10, 25, tzinfo=timezone.utc),
        },
        {
            "meal_plan_ingredient_id": UUID("55555555-5555-5555-5555-555555555555"),
            "meal_plan_id": meal_plan_id,
            "recipe_id": recipe_id,
            "deal_id": None,
            "is_promotional": False,
            "ingredient_name": "Rice",
            "ingredient_quantity": "2 cups",
            "is_purchased": True,
            "created_at": datetime(2026, 10, 25, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 10, 25, tzinfo=timezone.utc),
        },
    ]
    service = RecipeService("unused", pool=FakePool(connection))  # type: ignore[arg-type]

    ingredients = await service.get_meal_plan_ingredients(meal_plan_id)

    assert ingredients[0]["store_id"] == "store-123"
    assert ingredients[0]["deal_id"] == "store-123_deal-456"
    assert ingredients[0]["ingredient_name"] == "Chicken"
    assert ingredients[1]["store_id"] is None
    assert ingredients[1]["is_purchased"] is True


@pytest.mark.asyncio
async def test_update_meal_plan_ingredient_purchase_updates_status_and_timestamp() -> None:
    connection = FakeConnection()
    meal_plan_id = UUID("11111111-1111-1111-1111-111111111111")
    ingredient_id = UUID("44444444-4444-4444-4444-444444444444")
    connection.fetchval_override = ingredient_id
    service = RecipeService("unused", pool=FakePool(connection))  # type: ignore[arg-type]

    updated = await service.update_meal_plan_ingredient_purchase(
        meal_plan_id,
        ingredient_id,
        True,
    )

    assert updated is True
    query, args = connection.fetchval_calls[0]
    assert "SET is_purchased = $3" in query
    assert "updated_at = CLOCK_TIMESTAMP()" in query
    assert args == (meal_plan_id, ingredient_id, True)


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


@pytest.mark.asyncio
async def test_meal_plan_endpoints_create_associate_and_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = UUID("207d2de7-919d-4f48-b6f2-4a475ae96426")
    meal_plan_id = UUID("11111111-1111-1111-1111-111111111111")
    recipe_id = UUID("33333333-3333-3333-3333-333333333333")
    associations: list[tuple[UUID, UUID]] = []
    removals: list[tuple[UUID, UUID]] = []
    plans: dict[UUID, dict[str, Any]] = {}
    update_calls: list[tuple[UUID, str, bool | None]] = []

    class StubRecipeService:
        async def create_meal_plan(
            self,
            user_id: UUID,
            meal_plan_name: str,
            meal_plan_id: UUID | None = None,
        ) -> UUID:
            resolved_id = meal_plan_id or UUID("11111111-1111-1111-1111-111111111111")
            plans[resolved_id] = {
                "meal_plan_id": str(resolved_id),
                "meal_plan_name": meal_plan_name,
                "user_id": str(user_id),
                "is_archived": False,
                "created_at": "2026-10-24T18:00:00+00:00",
                "updated_at": "2026-10-24T18:00:00+00:00",
            }
            return resolved_id

        async def get_meal_plan(self, requested_id: UUID) -> dict[str, Any] | None:
            return plans.get(requested_id)

        async def associate_meal_plan_with_recipe(
            self,
            meal_plan_id: UUID,
            recipe_id: UUID,
        ) -> None:
            associations.append((meal_plan_id, recipe_id))

        async def remove_recipe_from_meal_plan(
            self,
            meal_plan_id: UUID,
            recipe_id: UUID,
        ) -> None:
            removals.append((meal_plan_id, recipe_id))

        async def update_meal_plan(
            self,
            meal_plan_id: UUID,
            meal_plan_name: str,
            is_archived: bool | None = None,
        ) -> None:
            update_calls.append((meal_plan_id, meal_plan_name, is_archived))
            plans[meal_plan_id]["meal_plan_name"] = meal_plan_name
            if is_archived is not None:
                plans[meal_plan_id]["is_archived"] = is_archived
            plans[meal_plan_id]["updated_at"] = "2026-10-24T18:05:00+00:00"

    monkeypatch.setattr(main, "recipe_service", StubRecipeService())

    created = await main.create_meal_plan(
        main.CreateMealPlanRequest(meal_plan_name="Weeknight Favorites", meal_plan_id=meal_plan_id),
        x_user_id=str(user_id),
    )
    assert created.meal_plan_id == str(meal_plan_id)
    assert created.meal_plan_name == "Weeknight Favorites"
    assert created.user_id == str(user_id)

    assoc_res = await main.associate_recipe_to_meal_plan(
        meal_plan_id=meal_plan_id,
        request=main.AssociateMealPlanRecipeRequest(recipe_id=recipe_id),
        x_user_id=str(user_id),
    )
    assert assoc_res == {
        "status": "associated",
        "meal_plan_id": str(meal_plan_id),
        "recipe_id": str(recipe_id),
    }
    assert associations == [(meal_plan_id, recipe_id)]

    remove_result = await main.remove_recipe_from_meal_plan(
        meal_plan_id=meal_plan_id,
        recipe_id=recipe_id,
        x_user_id=str(user_id),
    )
    assert remove_result == {
        "status": "removed",
        "meal_plan_id": str(meal_plan_id),
        "recipe_id": str(recipe_id),
    }
    assert removals == [(meal_plan_id, recipe_id)]

    updated = await main.update_meal_plan_name(
        meal_plan_id=meal_plan_id,
        request=main.UpdateMealPlanNameRequest(meal_plan_name="Renamed Meal Plan"),
        x_user_id=str(user_id),
    )
    assert updated.meal_plan_name == "Renamed Meal Plan"
    assert updated.updated_at == "2026-10-24T18:05:00+00:00"
    assert updated.is_archived is False
    assert update_calls == [(meal_plan_id, "Renamed Meal Plan", False)]

    archived = await main.update_meal_plan_name(
        meal_plan_id=meal_plan_id,
        request=main.UpdateMealPlanNameRequest(
            meal_plan_name="Renamed Meal Plan",
            is_archived=True,
        ),
        x_user_id=str(user_id),
    )
    assert archived.is_archived is True

    unarchived = await main.update_meal_plan_name(
        meal_plan_id=meal_plan_id,
        request=main.UpdateMealPlanNameRequest(
            meal_plan_name="Renamed Meal Plan",
            is_archived=False,
        ),
        x_user_id=str(user_id),
    )
    assert unarchived.is_archived is False


@pytest.mark.asyncio
async def test_list_meal_plans_for_user_includes_recipe_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = UUID("207d2de7-919d-4f48-b6f2-4a475ae96426")
    meal_plan_id = UUID("11111111-1111-1111-1111-111111111111")

    class StubRecipeService:
        async def get_meal_plans_for_user(self, requested_user_id: UUID) -> list[dict[str, Any]]:
            assert requested_user_id == user_id
            return [
                {
                    "meal_plan_id": str(meal_plan_id),
                    "meal_plan_name": "Oct 25, 2026",
                    "user_id": str(user_id),
                    "recipe_count": 3,
                    "created_at": "2026-10-25T15:00:00+00:00",
                    "updated_at": "2026-10-25T15:10:00+00:00",
                }
            ]

    monkeypatch.setattr(main, "recipe_service", StubRecipeService())

    listed = await main.list_meal_plans_for_user(x_user_id=str(user_id))
    assert len(listed) == 1
    assert listed[0].meal_plan_id == str(meal_plan_id)
    assert listed[0].meal_plan_name == "Oct 25, 2026"
    assert listed[0].recipe_count == 3


@pytest.mark.asyncio
async def test_get_recipe_by_id_returns_only_recipe_owned_by_request_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = UUID("207d2de7-919d-4f48-b6f2-4a475ae96426")
    recipe_id = UUID("33333333-3333-3333-3333-333333333333")
    expected_recipe = {
        "recipe_id": str(recipe_id),
        "title": "Herb chicken",
        "description": "Chicken with herbs",
        "protein_subtype": "Chicken",
        "cuisine": "Mediterranean",
        "image_url": None,
        "ingredients": [{"name": "Chicken", "quantity": "1 lb"}],
        "directions": ["Cook chicken."],
        "created_at": "2026-01-01T00:00:00+00:00",
    }

    class StubRecipeService:
        async def get_recipe_for_user(
            self,
            requested_recipe_id: UUID,
            requested_user_id: UUID,
        ) -> dict[str, Any] | None:
            assert requested_recipe_id == recipe_id
            assert requested_user_id == user_id
            return expected_recipe

    monkeypatch.setattr(main, "recipe_service", StubRecipeService())

    result = await main.get_recipe_by_id(recipe_id, x_user_id=str(user_id))

    assert result == expected_recipe
