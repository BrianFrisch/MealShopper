import json
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, TypedDict, cast
from uuid import UUID, uuid4

import asyncpg  # type: ignore[reportMissingTypeStubs]

from src.models import MealPlanResponse, PlannedMeal


class RecipeConnection(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[object]: ...

    async def fetchval(self, query: str, *args: object) -> UUID | None: ...

    async def execute(self, query: str, *args: object) -> str: ...

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None: ...

    async def fetch(self, query: str, *args: object) -> Sequence[Mapping[str, Any]]: ...


class RecipePool(Protocol):
    def acquire(self) -> AbstractAsyncContextManager[RecipeConnection]: ...

    async def close(self) -> None: ...


class StoredRecipe(TypedDict):
    recipe_id: str
    meal_plan_id: str
    source_meal_id: str
    recipe: dict[str, Any]
    created_at: str


class RecipeService:
    def __init__(self, database_url: str, pool: RecipePool | None = None) -> None:
        self._database_url = database_url
        self._pool = pool

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = cast(RecipePool, await asyncpg.create_pool(self._database_url))

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def persist_meal_plan(self, user_id: UUID, meal_plan: MealPlanResponse) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                for meal in meal_plan.meals:
                    source_meal_id = meal.meal_id
                    candidate_recipe_id = uuid4()
                    recipe_id = await connection.fetchval(
                        "CALL sp_create_recipe($1, $2, $3, $4::jsonb);",
                        candidate_recipe_id,
                        meal_plan.plan_id,
                        source_meal_id,
                        json.dumps(meal.model_dump(mode="json")),
                    )
                    if recipe_id is None:
                        raise RuntimeError(f"Database did not return an ID for recipe {source_meal_id}.")

                    await connection.execute(
                        "CALL sp_associate_user_recipe($1, $2);",
                        user_id,
                        recipe_id,
                    )
                    meal.meal_id = str(recipe_id)

    async def create_recipe(
        self,
        meal_plan_id: str,
        meal: PlannedMeal,
    ) -> UUID:
        pool = self._require_pool()
        candidate_recipe_id = uuid4()
        async with pool.acquire() as connection:
            recipe_id = await connection.fetchval(
                "CALL sp_create_recipe($1, $2, $3, $4::jsonb);",
                candidate_recipe_id,
                meal_plan_id,
                meal.meal_id,
                json.dumps(meal.model_dump(mode="json")),
            )
        if recipe_id is None:
            raise RuntimeError(f"Database did not return an ID for recipe {meal.meal_id}.")
        return recipe_id

    async def associate_user_with_recipe(self, user_id: UUID, recipe_id: UUID) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "CALL sp_associate_user_recipe($1, $2);",
                user_id,
                recipe_id,
            )

    async def get_recipe(self, recipe_id: UUID) -> StoredRecipe | None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow("SELECT * FROM fn_get_recipe($1);", recipe_id)
        return self._to_stored_recipe(row) if row is not None else None

    async def get_recipes_for_user(self, user_id: UUID) -> list[StoredRecipe]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch("SELECT * FROM fn_get_recipes_for_user($1);", user_id)
        return [self._to_stored_recipe(row) for row in rows]

    def _require_pool(self) -> RecipePool:
        if self._pool is None:
            raise RuntimeError("RecipeService is not connected to the planner database.")
        return self._pool

    @staticmethod
    def _to_stored_recipe(row: Mapping[str, Any]) -> StoredRecipe:
        recipe_data = row["recipe_data"]
        if isinstance(recipe_data, str):
            recipe_data = json.loads(recipe_data)

        return {
            "recipe_id": str(row["recipe_id"]),
            "meal_plan_id": row["meal_plan_id"],
            "source_meal_id": row["source_meal_id"],
            "recipe": recipe_data,
            "created_at": row["created_at"].isoformat(),
        }
