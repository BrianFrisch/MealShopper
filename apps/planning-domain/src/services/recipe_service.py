import json
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, TypedDict, cast
from uuid import UUID, uuid4

try:
    import asyncpg  # type: ignore[reportMissingTypeStubs]
except ImportError:
    asyncpg = None

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
    title: str
    description: str | None
    protein_subtype: str | None
    cuisine: str | None
    image_url: str | None
    ingredients: list[dict[str, Any]]
    directions: list[str]
    created_at: str


class StoredMealPlan(TypedDict):
    meal_plan_id: str
    meal_plan_name: str
    user_id: str
    is_archived: bool
    recipe_count: int
    created_at: str
    updated_at: str


class StoredMealPlanIngredient(TypedDict):
    meal_plan_ingredient_id: str
    meal_plan_id: str
    recipe_id: str
    deal_id: str | None
    store_id: str | None
    is_promotional: bool
    ingredient_name: str
    ingredient_quantity: str
    is_purchased: bool
    created_at: str
    updated_at: str


def _resolve_meal_plan_uuid(plan_id: str) -> UUID:
    try:
        return UUID(str(plan_id))
    except (ValueError, TypeError):
        return uuid4()


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

    async def persist_meal_plan(
        self,
        user_id: UUID,
        meal_plan: MealPlanResponse,
    ) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                for meal in meal_plan.meals:
                    source_meal_id = meal.meal_id
                    candidate_recipe_id = uuid4()
                    recipe_id = await connection.fetchval(
                        "CALL sp_create_recipe($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb);",
                        candidate_recipe_id,
                        meal.recipe_name[:200],
                        meal.description,
                        meal.protein_subtype,
                        meal.cuisine,
                        meal.image_url,
                        json.dumps([ing.model_dump(mode="json") for ing in meal.ingredients]),
                        json.dumps(meal.instructions),
                    )
                    if recipe_id is None:
                        raise RuntimeError(f"Database did not return an ID for recipe {source_meal_id}.")

                    await connection.execute(
                        "CALL sp_associate_user_recipe($1, $2);",
                        user_id,
                        recipe_id,
                    )
                    meal.meal_id = str(recipe_id)

    async def create_meal_plan(
        self,
        user_id: UUID,
        meal_plan_name: str,
        meal_plan_id: UUID | None = None,
    ) -> UUID:
        pool = self._require_pool()
        candidate_id = meal_plan_id or uuid4()
        async with pool.acquire() as connection:
            persisted_id = await connection.fetchval(
                "CALL sp_create_meal_plan($1, $2, $3);",
                candidate_id,
                meal_plan_name,
                user_id,
            )
        if persisted_id is None:
            raise RuntimeError("Database did not return an ID for meal plan.")
        return persisted_id

    async def update_meal_plan(
        self,
        meal_plan_id: UUID,
        meal_plan_name: str,
        is_archived: bool | None = None,
    ) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "CALL sp_update_meal_plan($1, $2, $3);",
                meal_plan_id,
                meal_plan_name,
                is_archived,
            )

    async def get_meal_plan(self, meal_plan_id: UUID) -> StoredMealPlan | None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow("SELECT * FROM fn_get_meal_plan($1);", meal_plan_id)
            if row is None:
                return None
            plan = self._to_stored_meal_plan(row)
            if "recipe_count" not in row or row["recipe_count"] is None:
                recipe_rows = await connection.fetch(
                    "SELECT * FROM fn_get_recipes_for_meal_plan($1);",
                    meal_plan_id,
                )
                plan["recipe_count"] = len(recipe_rows)
            return plan

    async def get_meal_plans_for_user(self, user_id: UUID) -> list[StoredMealPlan]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch("SELECT * FROM fn_get_meal_plans_for_user($1);", user_id)
            plans: list[StoredMealPlan] = []
            for row in rows:
                plan = self._to_stored_meal_plan(row)
                if "recipe_count" not in row or row["recipe_count"] is None:
                    recipe_rows = await connection.fetch(
                        "SELECT * FROM fn_get_recipes_for_meal_plan($1);",
                        row["meal_plan_id"],
                    )
                    plan["recipe_count"] = len(recipe_rows)
                plans.append(plan)
        return plans

    async def create_recipe(
        self,
        meal: PlannedMeal,
    ) -> UUID:
        pool = self._require_pool()
        candidate_recipe_id = uuid4()
        async with pool.acquire() as connection:
            recipe_id = await connection.fetchval(
                "CALL sp_create_recipe($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb);",
                candidate_recipe_id,
                meal.recipe_name[:200],
                meal.description,
                meal.protein_subtype,
                meal.cuisine,
                meal.image_url,
                json.dumps([ing.model_dump(mode="json") for ing in meal.ingredients]),
                json.dumps(meal.instructions),
            )
        if recipe_id is None:
            raise RuntimeError(f"Database did not return an ID for recipe {meal.meal_id}.")
        return recipe_id

    async def associate_meal_plan_with_recipe(self, meal_plan_id: UUID, recipe_id: UUID) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "CALL sp_associate_meal_plan_recipe($1, $2);",
                meal_plan_id,
                recipe_id,
            )

    async def remove_recipe_from_meal_plan(self, meal_plan_id: UUID, recipe_id: UUID) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "CALL sp_remove_meal_plan_recipe($1, $2);",
                meal_plan_id,
                recipe_id,
            )

    async def get_meal_plan_ingredients(
        self,
        meal_plan_id: UUID,
    ) -> list[StoredMealPlanIngredient]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT meal_plan_ingredient_id, meal_plan_id, recipe_id, deal_id,
                       is_promotional, ingredient_name, ingredient_quantity,
                       is_purchased, created_at, updated_at
                FROM meal_plan_ingredient
                WHERE meal_plan_id = $1
                ORDER BY (deal_id IS NULL), deal_id, ingredient_name, created_at
                """,
                meal_plan_id,
            )
        return [self._to_stored_meal_plan_ingredient(row) for row in rows]

    async def update_meal_plan_ingredient_purchase(
        self,
        meal_plan_id: UUID,
        ingredient_id: UUID,
        is_purchased: bool,
    ) -> bool:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            updated_id = await connection.fetchval(
                """
                UPDATE meal_plan_ingredient
                SET is_purchased = $3,
                    updated_at = CLOCK_TIMESTAMP()
                WHERE meal_plan_id = $1
                  AND meal_plan_ingredient_id = $2
                RETURNING meal_plan_ingredient_id
                """,
                meal_plan_id,
                ingredient_id,
                is_purchased,
            )
        return updated_id is not None

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

    async def get_recipe_for_user(
        self,
        recipe_id: UUID,
        user_id: UUID,
    ) -> StoredRecipe | None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT r.*
                FROM recipe AS r
                INNER JOIN user_recipe AS ur ON ur.recipe_id = r.recipe_id
                WHERE r.recipe_id = $1
                  AND ur.user_id = $2
                """,
                recipe_id,
                user_id,
            )
        return self._to_stored_recipe(row) if row is not None else None

    async def get_recipes_for_user(self, user_id: UUID) -> list[StoredRecipe]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch("SELECT * FROM fn_get_recipes_for_user($1);", user_id)
        return [self._to_stored_recipe(row) for row in rows]

    async def get_recipes_for_meal_plan(self, meal_plan_id: UUID) -> list[StoredRecipe]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch("SELECT * FROM fn_get_recipes_for_meal_plan($1);", meal_plan_id)
        return [self._to_stored_recipe(row) for row in rows]

    def _require_pool(self) -> RecipePool:
        if self._pool is None:
            raise RuntimeError("RecipeService is not connected to the planner database.")
        return self._pool

    @staticmethod
    def _to_stored_recipe(row: Mapping[str, Any]) -> StoredRecipe:
        ingredients = row["ingredients"]
        if isinstance(ingredients, str):
            ingredients = json.loads(ingredients)

        directions = row["directions"]
        if isinstance(directions, str):
            directions = json.loads(directions)

        return {
            "recipe_id": str(row["recipe_id"]),
            "title": row["title"],
            "description": row.get("description"),
            "protein_subtype": row.get("protein_subtype"),
            "cuisine": row.get("cuisine"),
            "image_url": row.get("image_url"),
            "ingredients": ingredients,
            "directions": directions,
            "created_at": row["created_at"].isoformat(),
        }

    @staticmethod
    def _to_stored_meal_plan(row: Mapping[str, Any]) -> StoredMealPlan:
        raw_count = row.get("recipe_count", 0)
        return {
            "meal_plan_id": str(row["meal_plan_id"]),
            "meal_plan_name": row["meal_plan_name"],
            "user_id": str(row["user_id"]),
            "is_archived": bool(row.get("is_archived", False)),
            "recipe_count": int(raw_count or 0),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    @staticmethod
    def _to_stored_meal_plan_ingredient(
        row: Mapping[str, Any],
    ) -> StoredMealPlanIngredient:
        deal_id = row["deal_id"]
        store_id = deal_id.partition("_")[0] if deal_id and "_" in deal_id else None
        return {
            "meal_plan_ingredient_id": str(row["meal_plan_ingredient_id"]),
            "meal_plan_id": str(row["meal_plan_id"]),
            "recipe_id": str(row["recipe_id"]),
            "deal_id": deal_id,
            "store_id": store_id,
            "is_promotional": bool(row["is_promotional"]),
            "ingredient_name": row["ingredient_name"],
            "ingredient_quantity": row["ingredient_quantity"],
            "is_purchased": bool(row["is_purchased"]),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }
