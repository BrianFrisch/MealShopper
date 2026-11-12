import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from src.models import PlannedMeal
from src.services.recipe_service import RecipeService


@pytest.mark.asyncio
async def test_user_recipe_tags_in_postgres() -> None:
    database_url = os.getenv("PLANNER_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set PLANNER_TEST_DATABASE_URL to run PostgreSQL integration tests.")
    asyncpg = pytest.importorskip("asyncpg")
    connection = await asyncpg.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute("""
                CREATE TEMP TABLE user_recipe (
                    user_id UUID NOT NULL, recipe_id UUID NOT NULL,
                    PRIMARY KEY (user_id, recipe_id)
                );
            """)
            init = Path(__file__).resolve().parents[1] / "Infrastructure" / "postgres" / "init"
            table_sql = (init / "01_tables" / "003_user_recipe_tag.sql").read_text(encoding="utf-8")
            await connection.execute(table_sql.replace(
                "CREATE TABLE IF NOT EXISTS user_recipe_tag", "CREATE TEMP TABLE user_recipe_tag", 1
            ))
            procedure_sql = (init / "03_procedures" / "009_sp_add_user_recipe_tags.sql").read_text(encoding="utf-8")
            await connection.execute(procedure_sql.replace(
                "PROCEDURE sp_add_user_recipe_tags(", "PROCEDURE pg_temp.sp_add_user_recipe_tags(", 1
            ))
            user_id, other_user, recipe_id = UUID(int=1), UUID(int=2), UUID(int=3)
            await connection.execute("INSERT INTO user_recipe VALUES ($1, $2)", user_id, recipe_id)
            await connection.execute(
                "CALL pg_temp.sp_add_user_recipe_tags($1, $2, $3::text[])",
                user_id, recipe_id, ["Tag", "tag", "tag", "a" * 16],
            )
            rows = await connection.fetch("SELECT tag, created_at FROM user_recipe_tag ORDER BY tag")
            assert {row["tag"] for row in rows} == {"Tag", "tag", "a" * 16}
            assert all(row["created_at"] is not None for row in rows)
            with pytest.raises(asyncpg.StringDataRightTruncationError):
                async with connection.transaction():
                    await connection.execute(
                        "CALL pg_temp.sp_add_user_recipe_tags($1, $2, $3::text[])",
                        user_id, recipe_id, ["a" * 17],
                    )
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                async with connection.transaction():
                    await connection.execute(
                        "CALL pg_temp.sp_add_user_recipe_tags($1, $2, $3::text[])",
                        other_user, recipe_id, ["tag"],
                    )
            await connection.execute("DELETE FROM user_recipe WHERE user_id = $1", user_id)
            assert await connection.fetchval("SELECT count(*) FROM user_recipe_tag") == 0
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_create_recipe_and_tags_are_transactional_in_postgres() -> None:
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
                    image_url TEXT, ingredients JSONB NOT NULL, directions JSONB NOT NULL
                );
                CREATE TEMP TABLE user_recipe (
                    user_id UUID NOT NULL, recipe_id UUID NOT NULL REFERENCES recipe,
                    PRIMARY KEY (user_id, recipe_id)
                );
            """)
            init = Path(__file__).resolve().parents[1] / "Infrastructure" / "postgres" / "init"
            table_sql = (init / "01_tables" / "003_user_recipe_tag.sql").read_text(encoding="utf-8")
            await connection.execute(table_sql.replace(
                "CREATE TABLE IF NOT EXISTS user_recipe_tag", "CREATE TEMP TABLE user_recipe_tag", 1
            ))
            for name in ("001_sp_create_recipe.sql", "002_sp_associate_user_recipe.sql", "009_sp_add_user_recipe_tags.sql"):
                sql = (init / "03_procedures" / name).read_text(encoding="utf-8")
                sql = sql.replace("PROCEDURE sp_", "PROCEDURE pg_temp.sp_")
                await connection.execute(sql)

            class Connection:
                fail_tags = False

                def transaction(self):
                    return connection.transaction()

                async def fetchval(self, query: str, *args: object):
                    return await connection.fetchval(query.replace("CALL sp_", "CALL pg_temp.sp_"), *args)

                async def execute(self, query: str, *args: object):
                    if self.fail_tags and "sp_add_user_recipe_tags" in query:
                        raise RuntimeError("tag write failed")
                    return await connection.execute(query.replace("CALL sp_", "CALL pg_temp.sp_"), *args)

            class Pool:
                def __init__(self):
                    self.connection = Connection()

                @asynccontextmanager
                async def acquire(self):
                    yield self.connection

            pool = Pool()
            service = RecipeService("unused", pool=pool)  # type: ignore[arg-type]
            meal = PlannedMeal(
                meal_id="new", recipe_name="Dinner", description="Dinner",
                protein_subtype="Chicken", cuisine="Thai",
                estimated_prep_time_minutes=20, servings=2, ingredients=[], instructions=[],
            )
            recipe_id = await service.create_recipe(meal, UUID(int=1))
            rows = await connection.fetch("SELECT tag FROM user_recipe_tag WHERE recipe_id = $1", recipe_id)
            assert {row["tag"] for row in rows} == {"chicken", "thai"}
            pool.connection.fail_tags = True
            with pytest.raises(RuntimeError, match="tag write failed"):
                await service.create_recipe(meal, UUID(int=1))
            assert await connection.fetchval("SELECT count(*) FROM recipe") == 1
            assert await connection.fetchval("SELECT count(*) FROM user_recipe") == 1
    finally:
        await connection.close()


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
                CREATE TEMP TABLE user_recipe_tag (
                    user_id UUID NOT NULL,
                    recipe_id UUID NOT NULL,
                    tag VARCHAR(16) COLLATE "C" NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (user_id, recipe_id, tag)
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
                    "INSERT INTO user_recipe VALUES ($1, $2, 0, $3, $3)",
                    user_id, recipe_id, created + timedelta(days=index // 2),
                )
            await connection.execute(
                "INSERT INTO user_recipe VALUES ($1, $2, 0, $3, $3)",
                other_user, UUID(int=10), created + timedelta(days=100),
            )
            await connection.execute(
                "INSERT INTO user_recipe_tag VALUES ($1, $2, 'comfort-food', $3)",
                user_id, UUID(int=10), created,
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
            # Verify tag mapping
            recipe_0 = [item for item in first + second if item["recipe_id"] == str(UUID(int=10))][0]
            assert recipe_0["tags"] == ["comfort-food"]
            recipe_1 = [item for item in first + second if item["recipe_id"] == str(UUID(int=11))][0]
            assert recipe_1["tags"] == []
            assert other[0]["tags"] == []
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_fn_get_recipe_and_meal_plan_recipes_include_tags_in_postgres() -> None:
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
                CREATE TEMP TABLE user_recipe_tag (
                    user_id UUID NOT NULL, recipe_id UUID NOT NULL,
                    tag VARCHAR(16) COLLATE "C" NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (user_id, recipe_id, tag)
                );
                CREATE TEMP TABLE meal_plan (
                    meal_plan_id UUID PRIMARY KEY,
                    meal_plan_name TEXT NOT NULL,
                    user_id UUID NOT NULL,
                    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TEMP TABLE meal_plan_recipe (
                    meal_plan_id UUID NOT NULL,
                    recipe_id UUID NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (meal_plan_id, recipe_id)
                );
            """)
            init = Path(__file__).resolve().parents[1] / "Infrastructure" / "postgres" / "init"
            fn1_sql = (init / "02_functions" / "001_fn_get_recipe.sql").read_text(encoding="utf-8")
            await connection.execute(fn1_sql.replace("FUNCTION fn_get_recipe(", "FUNCTION pg_temp.fn_get_recipe(", 1))
            fn2_sql = (init / "02_functions" / "002_fn_get_recipes_for_user.sql").read_text(encoding="utf-8")
            await connection.execute(fn2_sql.replace("FUNCTION fn_get_recipes_for_user(", "FUNCTION pg_temp.fn_get_recipes_for_user(", 1))
            fn5_sql = (init / "02_functions" / "005_fn_get_recipes_for_meal_plan.sql").read_text(encoding="utf-8")
            await connection.execute(fn5_sql.replace("FUNCTION fn_get_recipes_for_meal_plan(", "FUNCTION pg_temp.fn_get_recipes_for_meal_plan(", 1))

            user_id = UUID(int=1)
            other_user = UUID(int=2)
            recipe_id = UUID(int=42)
            meal_plan_id = UUID(int=99)
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)

            await connection.execute(
                "INSERT INTO recipe VALUES ($1, 'Spicy Tacos', NULL, 'Beef', 'Mexican', NULL, '[]', '[]', $2)",
                recipe_id, now,
            )
            await connection.execute("INSERT INTO user_recipe VALUES ($1, $2, 4, $3, $3)", user_id, recipe_id, now)
            await connection.execute("INSERT INTO user_recipe_tag VALUES ($1, $2, 'spicy', $3)", user_id, recipe_id, now)
            await connection.execute("INSERT INTO user_recipe_tag VALUES ($1, $2, 'quick', $3)", user_id, recipe_id, now)
            await connection.execute("INSERT INTO meal_plan VALUES ($1, 'Week 1', $2, FALSE, $3, $3)", meal_plan_id, user_id, now)
            await connection.execute("INSERT INTO meal_plan_recipe VALUES ($1, $2, $3)", meal_plan_id, recipe_id, now)

            # Test fn_get_recipe with user_id
            row_with_user = await connection.fetchrow("SELECT * FROM pg_temp.fn_get_recipe($1, $2);", recipe_id, user_id)
            assert row_with_user is not None
            assert row_with_user["tags"] == ["spicy", "quick"] or set(row_with_user["tags"]) == {"spicy", "quick"}

            # Test fn_get_recipe without user_id / other user
            row_no_user = await connection.fetchrow("SELECT * FROM pg_temp.fn_get_recipe($1);", recipe_id)
            assert row_no_user is not None
            assert row_no_user["tags"] == []

            row_other = await connection.fetchrow("SELECT * FROM pg_temp.fn_get_recipe($1, $2);", recipe_id, other_user)
            assert row_other is not None
            assert row_other["tags"] == []

            # Test fn_get_recipes_for_user
            user_recipes = await connection.fetch("SELECT * FROM pg_temp.fn_get_recipes_for_user($1);", user_id)
            assert len(user_recipes) == 1
            assert set(user_recipes[0]["tags"]) == {"spicy", "quick"}

            # Test fn_get_recipes_for_meal_plan
            mp_recipes = await connection.fetch("SELECT * FROM pg_temp.fn_get_recipes_for_meal_plan($1);", meal_plan_id)
            assert len(mp_recipes) == 1
            assert set(mp_recipes[0]["tags"]) == {"spicy", "quick"}
    finally:
        await connection.close()
