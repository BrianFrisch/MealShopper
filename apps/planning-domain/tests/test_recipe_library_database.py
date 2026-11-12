import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from src.services.recipe_service import RecipeService


@pytest.mark.asyncio
async def test_user_recipe_page_in_postgres() -> None:
    database_url = os.getenv("PLANNER_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set PLANNER_TEST_DATABASE_URL to run PostgreSQL integration tests.")
    asyncpg = pytest.importorskip("asyncpg")
    connection = await asyncpg.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute("""
                CREATE TEMP TABLE recipe (
                    recipe_id UUID PRIMARY KEY, title VARCHAR(200) NOT NULL,
                    description TEXT, protein_subtype VARCHAR(50), cuisine VARCHAR(50),
                    image_url TEXT, ingredients JSONB NOT NULL, directions JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
                CREATE TEMP TABLE user_recipe (
                    user_id UUID NOT NULL, recipe_id UUID NOT NULL,
                    rating INTEGER NOT NULL DEFAULT 0,
                    associated_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (user_id, recipe_id)
                );
            """)
            function_path = (
                Path(__file__).resolve().parents[1] / "Infrastructure" / "postgres" / "init"
                / "02_functions" / "006_fn_get_user_recipe_page.sql"
            )
            sql = function_path.read_text(encoding="utf-8").replace(
                "FUNCTION fn_get_user_recipe_page(", "FUNCTION pg_temp.fn_get_user_recipe_page(", 1
            )
            await connection.execute(sql)
            user_id = UUID(int=1)
            other_user = UUID(int=2)
            created = datetime(2026, 1, 1, tzinfo=timezone.utc)
            for index in range(12):
                recipe_id = UUID(int=index + 10)
                await connection.execute(
                    "INSERT INTO recipe VALUES ($1, $2, NULL, NULL, NULL, NULL, '[]', '[]', $3)",
                    recipe_id, f"Recipe {index}", created - timedelta(days=index),
                )
                await connection.execute(
                    "INSERT INTO user_recipe VALUES ($1, $2, $3, $3)",
                    user_id, recipe_id, created + timedelta(days=index // 2),
                )
            await connection.execute(
                "INSERT INTO user_recipe VALUES ($1, $2, $3, $3)",
                other_user, UUID(int=10), created + timedelta(days=100),
            )

            class Connection:
                async def fetch(self, query: str, *args: object):
                    return await connection.fetch(
                        query.replace("fn_get_user_recipe_page(", "pg_temp.fn_get_user_recipe_page("),
                        *args,
                    )

            class Pool:
                @asynccontextmanager
                async def acquire(self):
                    yield Connection()

            service = RecipeService("unused", pool=Pool())  # type: ignore[arg-type]
            first, count = await service.get_user_recipe_page(user_id, 0, 10)
            second, second_count = await service.get_user_recipe_page(user_id, 10, 10)
            empty, empty_count = await service.get_user_recipe_page(user_id, 30, 10)
            other, other_count = await service.get_user_recipe_page(other_user, 0, 10)
            none, none_count = await service.get_user_recipe_page(UUID(int=3), 0, 10)
            assert [item["title"] for item in first + second] == [
                f"Recipe {index}" for index in range(11, -1, -1)
            ]
            assert (count, second_count, empty_count) == (12, 12, 12)
            assert empty == []
            assert ([item["title"] for item in other], other_count) == (["Recipe 0"], 1)
            assert (none, none_count) == ([], 0)
    finally:
        await connection.close()
