# MealShopper
A meal shopping app

The authenticated **Recipe Library** at `/recipes` lists saved recipes in pages of
10, newest additions first. The remove control is a placeholder and does not
delete recipes. The gateway forwards the authenticated user to
`GET /v1/planner/recipes?start_index=0&page_size=10`, which returns `recipes`
and `total_count`; `start_index` is zero-based and `page_size` is limited to 100.

Recipes can be created with `POST /v1/planner/recipes`, using a `PlannedMeal`
request body, or generated as part of a meal plan. Protein subtype and cuisine
are automatically added as tags when present. Automatic tags are normalized and
truncated to 16 characters; empty results are omitted.

Use `POST /v1/planner/recipes/{recipe_id}/tags` with `{"tags": ["..."]}` to add
tags to a recipe in the authenticated user's library. Tags are lowercased and
all characters other than letters, digits, and hyphens are removed. A normalized
tag must contain 1–16 characters; duplicates are ignored. Both endpoints
require the `X-User-Id` header supplied by the gateway.

Planning-domain database scripts run on service startup. To run the optional
recipe-library and tagging PostgreSQL integration tests, set `PLANNER_TEST_DATABASE_URL` to
a test database and run `pytest tests/test_recipe_library_database.py` from
`apps/planning-domain`. The test uses temporary tables and a temporary function.
