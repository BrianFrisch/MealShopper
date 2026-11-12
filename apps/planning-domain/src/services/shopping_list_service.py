from collections.abc import Mapping
from typing import Any, TypedDict
from uuid import UUID

from src.services.base import BaseDatabaseService, DatabasePool


class StoredMealPlanIngredient(TypedDict):
    meal_plan_ingredient_id: str
    meal_plan_id: str
    recipe_id: str | None
    deal_id: str | None
    store_id: str | None
    is_promotional: bool
    ingredient_name: str
    ingredient_quantity: str
    is_purchased: bool
    created_at: str
    updated_at: str


class ShoppingListService(BaseDatabaseService):
    def __init__(self, database_url: str, pool: DatabasePool | None = None) -> None:
        super().__init__(database_url, pool)

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

    async def add_shopping_list_item(
        self,
        meal_plan_id: UUID,
        ingredient_name: str,
        ingredient_quantity: str,
    ) -> StoredMealPlanIngredient | None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO meal_plan_ingredient (
                    meal_plan_ingredient_id,
                    meal_plan_id,
                    recipe_id,
                    ingredient_index,
                    deal_id,
                    is_promotional,
                    ingredient_name,
                    ingredient_quantity,
                    is_purchased
                )
                VALUES (
                    gen_random_uuid(),
                    $1,
                    NULL,
                    COALESCE(
                        (
                            SELECT MAX(ingredient_index) + 1
                            FROM meal_plan_ingredient
                            WHERE meal_plan_id = $1
                              AND recipe_id IS NULL
                        ),
                        0
                    ),
                    NULL,
                    FALSE,
                    $2,
                    $3,
                    FALSE
                )
                RETURNING meal_plan_ingredient_id, meal_plan_id, recipe_id, deal_id,
                          is_promotional, ingredient_name, ingredient_quantity,
                          is_purchased, created_at, updated_at
                """,
                meal_plan_id,
                ingredient_name,
                ingredient_quantity,
            )
        return self._to_stored_meal_plan_ingredient(row) if row is not None else None

    async def remove_shopping_list_item(
        self,
        meal_plan_id: UUID,
        ingredient_id: UUID,
    ) -> str | None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT recipe_id
                FROM meal_plan_ingredient
                WHERE meal_plan_id = $1
                  AND meal_plan_ingredient_id = $2
                """,
                meal_plan_id,
                ingredient_id,
            )
            if row is None:
                return None

            if row["recipe_id"] is None:
                await connection.execute(
                    """
                    DELETE FROM meal_plan_ingredient
                    WHERE meal_plan_id = $1
                      AND meal_plan_ingredient_id = $2
                    """,
                    meal_plan_id,
                    ingredient_id,
                )
                return "removed"

            await connection.execute(
                """
                UPDATE meal_plan_ingredient
                SET is_purchased = TRUE,
                    updated_at = CLOCK_TIMESTAMP()
                WHERE meal_plan_id = $1
                  AND meal_plan_ingredient_id = $2
                """,
                meal_plan_id,
                ingredient_id,
            )
        return "purchased"

    @staticmethod
    def _to_stored_meal_plan_ingredient(
        row: Mapping[str, Any],
    ) -> StoredMealPlanIngredient:
        deal_id = row["deal_id"]
        store_id = deal_id.partition("_")[0] if deal_id and "_" in deal_id else None
        return {
            "meal_plan_ingredient_id": str(row["meal_plan_ingredient_id"]),
            "meal_plan_id": str(row["meal_plan_id"]),
            "recipe_id": str(row["recipe_id"]) if row["recipe_id"] is not None else None,
            "deal_id": deal_id,
            "store_id": store_id,
            "is_promotional": bool(row["is_promotional"]),
            "ingredient_name": row["ingredient_name"],
            "ingredient_quantity": row["ingredient_quantity"],
            "is_purchased": bool(row["is_purchased"]),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }
