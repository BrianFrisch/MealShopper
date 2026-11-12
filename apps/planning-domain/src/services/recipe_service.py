import json
from collections.abc import Mapping
from typing import Any, TypedDict
from uuid import UUID, uuid4

from src.models import MealPlanResponse, PlannedMeal
from src.services.base import BaseDatabaseService, DatabaseConnection, DatabasePool
from src.services.meal_plan_service import MealPlanService, StoredMealPlan
from src.services.shopping_list_service import ShoppingListService, StoredMealPlanIngredient

# Compatibility aliases
RecipeConnection = DatabaseConnection
RecipePool = DatabasePool


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


class RecipeService(BaseDatabaseService):
    def __init__(
        self,
        database_url: str,
        pool: DatabasePool | None = None,
        meal_plan_service: MealPlanService | None = None,
        shopping_list_service: ShoppingListService | None = None,
    ) -> None:
        super().__init__(database_url, pool)
        self._meal_plan_service = meal_plan_service or MealPlanService(
            database_url, pool=pool, recipe_service=self
        )
        self._shopping_list_service = shopping_list_service or ShoppingListService(
            database_url, pool=pool
        )

    def set_pool(self, pool: DatabasePool | None) -> None:
        super().set_pool(pool)
        self._meal_plan_service.set_pool(pool)
        self._shopping_list_service.set_pool(pool)

    async def connect(self) -> None:
        await super().connect()
        if self._pool is not None:
            self._meal_plan_service.set_pool(self._pool)
            self._shopping_list_service.set_pool(self._pool)

    # ---- Recipe Management ----

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

    async def get_user_recipe_page(
        self, user_id: UUID, start_index: int, page_size: int,
    ) -> tuple[list[StoredRecipe], int]:
        if start_index < 0 or page_size < 1:
            raise ValueError("start_index must be non-negative and page_size must be positive.")
        pool = self._require_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT page.*, totals.total_count
                FROM (SELECT count(*) AS total_count FROM user_recipe WHERE user_id = $1) AS totals
                LEFT JOIN LATERAL fn_get_user_recipe_page($1, $2, $3) AS page ON TRUE
                ORDER BY page.user_recipe_created_at DESC, page.recipe_id DESC
                """,
                user_id, start_index, page_size,
            )
        return (
            [self._to_stored_recipe(row) for row in rows if row["recipe_id"] is not None],
            rows[0]["total_count"],
        )

    async def get_recipes_for_meal_plan(self, meal_plan_id: UUID) -> list[StoredRecipe]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch("SELECT * FROM fn_get_recipes_for_meal_plan($1);", meal_plan_id)
        return [self._to_stored_recipe(row) for row in rows]

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

    # ---- Meal Plan Delegations (Backwards Compatibility) ----

    async def create_meal_plan(
        self,
        user_id: UUID,
        meal_plan_name: str,
        meal_plan_id: UUID | None = None,
    ) -> UUID:
        return await self._meal_plan_service.create_meal_plan(user_id, meal_plan_name, meal_plan_id)

    async def update_meal_plan(
        self,
        meal_plan_id: UUID,
        meal_plan_name: str,
        is_archived: bool | None = None,
    ) -> None:
        return await self._meal_plan_service.update_meal_plan(meal_plan_id, meal_plan_name, is_archived)

    async def get_meal_plan(self, meal_plan_id: UUID) -> StoredMealPlan | None:
        return await self._meal_plan_service.get_meal_plan(meal_plan_id)

    async def get_meal_plans_for_user(self, user_id: UUID) -> list[StoredMealPlan]:
        return await self._meal_plan_service.get_meal_plans_for_user(user_id)

    async def associate_meal_plan_with_recipe(self, meal_plan_id: UUID, recipe_id: UUID) -> None:
        return await self._meal_plan_service.associate_meal_plan_with_recipe(meal_plan_id, recipe_id)

    async def remove_recipe_from_meal_plan(self, meal_plan_id: UUID, recipe_id: UUID) -> None:
        return await self._meal_plan_service.remove_recipe_from_meal_plan(meal_plan_id, recipe_id)

    # ---- Shopping List Delegations (Backwards Compatibility) ----

    async def get_meal_plan_ingredients(
        self,
        meal_plan_id: UUID,
    ) -> list[StoredMealPlanIngredient]:
        return await self._shopping_list_service.get_meal_plan_ingredients(meal_plan_id)

    async def update_meal_plan_ingredient_purchase(
        self,
        meal_plan_id: UUID,
        ingredient_id: UUID,
        is_purchased: bool,
    ) -> bool:
        return await self._shopping_list_service.update_meal_plan_ingredient_purchase(
            meal_plan_id, ingredient_id, is_purchased
        )

    async def add_shopping_list_item(
        self,
        meal_plan_id: UUID,
        ingredient_name: str,
        ingredient_quantity: str,
    ) -> StoredMealPlanIngredient | None:
        return await self._shopping_list_service.add_shopping_list_item(
            meal_plan_id, ingredient_name, ingredient_quantity
        )

    async def remove_shopping_list_item(
        self,
        meal_plan_id: UUID,
        ingredient_id: UUID,
    ) -> str | None:
        return await self._shopping_list_service.remove_shopping_list_item(
            meal_plan_id, ingredient_id
        )


__all__ = [
    "DatabaseConnection",
    "DatabasePool",
    "RecipeConnection",
    "RecipePool",
    "StoredRecipe",
    "StoredMealPlan",
    "StoredMealPlanIngredient",
    "RecipeService",
]
