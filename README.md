# MealShopper
A meal shopping app

Store discovery resolves an address with the US Census Geocoder, then falls
back to approximate ZIP-code or city/state coordinates from Zippopotam.us.
If the address cannot be resolved, discovery reports an error instead of
using a default location.

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

## GeoJSON store banner names

For a shared GeoJSON file, `grocery_chain.spider_name` can specify exact source
names after the path, separated by `|`. Matching ignores case and apostrophes,
but does not match partial names. The import's state filter still applies.
Without names, imports retain the existing display-name matching behavior.
Colons separate the path from names and `|` separates names.

After deploying the shopper database scripts, for example:

```sql
UPDATE grocery_chain SET spider_name = 'geojsonfile:/data/us_supermarkets.geojson:Dan''s Fresh Market|Dan''s' WHERE chain_id = 'dans';
```

Restart the shopper service after updating the database to clear its chain
metadata cache, then rerun the store import. Add other names only when they
identify the same chain; similarly named independent stores may exist.
