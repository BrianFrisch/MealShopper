# MealShopper
A meal shopping app

The authenticated **Recipe Library** at `/recipes` lists saved recipes in pages of
10, newest additions first. The remove control is a placeholder and does not
delete recipes. The gateway forwards the authenticated user to
`GET /v1/planner/recipes?start_index=0&page_size=10`, which returns `recipes`
and `total_count`; `start_index` is zero-based and `page_size` is limited to 100.

Planning-domain database scripts run on service startup. To run the optional
recipe-library PostgreSQL integration test, set `PLANNER_TEST_DATABASE_URL` to
a test database and run `pytest tests/test_recipe_library_database.py` from
`apps/planning-domain`. The test uses temporary tables and a temporary function.
