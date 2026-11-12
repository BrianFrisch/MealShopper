from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import UUID, uuid4

from src.services.base import BaseDatabaseService, DatabasePool

if TYPE_CHECKING:
    from src.services.recipe_service import RecipeService, StoredRecipe


class StoredMealPlan(TypedDict):
    meal_plan_id: str
    meal_plan_name: str
    user_id: str
    is_archived: bool
    recipe_count: int
    created_at: str
    updated_at: str


class MealPlanService(BaseDatabaseService):
    def __init__(
        self,
        database_url: str,
        pool: DatabasePool | None = None,
        recipe_service: "RecipeService | None" = None,
    ) -> None:
        super().__init__(database_url, pool)
        self._recipe_service = recipe_service

    def set_recipe_service(self, recipe_service: "RecipeService | None") -> None:
        self._recipe_service = recipe_service

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

    async def get_recipes_for_meal_plan(self, meal_plan_id: UUID) -> "list[StoredRecipe]":
        if self._recipe_service is not None:
            return await self._recipe_service.get_recipes_for_meal_plan(meal_plan_id)
        from src.services.recipe_service import RecipeService
        pool = self._require_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch("SELECT * FROM fn_get_recipes_for_meal_plan($1);", meal_plan_id)
        return [RecipeService._to_stored_recipe(row) for row in rows]

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
