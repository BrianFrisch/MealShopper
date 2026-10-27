CREATE TABLE IF NOT EXISTS meal_plan (
    meal_plan_id UUID PRIMARY KEY,
    meal_plan_name TEXT NOT NULL,
    user_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE meal_plan
    ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_meal_plan_user_id ON meal_plan (user_id);

CREATE TABLE IF NOT EXISTS meal_plan_recipe (
    meal_plan_id UUID NOT NULL REFERENCES meal_plan (meal_plan_id) ON DELETE CASCADE,
    recipe_id UUID NOT NULL REFERENCES recipe (recipe_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (meal_plan_id, recipe_id)
);

CREATE INDEX IF NOT EXISTS ix_meal_plan_recipe_recipe_id ON meal_plan_recipe (recipe_id);

CREATE TABLE IF NOT EXISTS meal_plan_ingredient (
    meal_plan_ingredient_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meal_plan_id UUID NOT NULL REFERENCES meal_plan (meal_plan_id) ON DELETE CASCADE,
    recipe_id UUID REFERENCES recipe (recipe_id) ON DELETE CASCADE,
    ingredient_index INTEGER NOT NULL,
    deal_id TEXT,
    is_promotional BOOLEAN NOT NULL DEFAULT FALSE,
    ingredient_name TEXT NOT NULL,
    ingredient_quantity TEXT NOT NULL,
    is_purchased BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE meal_plan_ingredient
    ADD COLUMN IF NOT EXISTS ingredient_index INTEGER;

ALTER TABLE meal_plan_ingredient
    ALTER COLUMN recipe_id DROP NOT NULL;

WITH ranked_ingredients AS (
    SELECT meal_plan_ingredient_id,
           ROW_NUMBER() OVER (
               PARTITION BY meal_plan_id, recipe_id
               ORDER BY created_at, meal_plan_ingredient_id
           ) - 1 AS ingredient_index
    FROM meal_plan_ingredient
    WHERE ingredient_index IS NULL
)
UPDATE meal_plan_ingredient AS ingredient
SET ingredient_index = ranked_ingredients.ingredient_index
FROM ranked_ingredients
WHERE ingredient.meal_plan_ingredient_id = ranked_ingredients.meal_plan_ingredient_id;

ALTER TABLE meal_plan_ingredient
    ALTER COLUMN ingredient_index SET NOT NULL,
    DROP CONSTRAINT IF EXISTS uq_meal_plan_ingredient;

CREATE INDEX IF NOT EXISTS ix_meal_plan_ingredient_meal_plan_id
    ON meal_plan_ingredient (meal_plan_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_meal_plan_ingredient_source
    ON meal_plan_ingredient (meal_plan_id, recipe_id, ingredient_index);

INSERT INTO meal_plan_ingredient (
    meal_plan_id,
    recipe_id,
    ingredient_index,
    deal_id,
    is_promotional,
    ingredient_name,
    ingredient_quantity
)
SELECT DISTINCT
    mpr.meal_plan_id,
    mpr.recipe_id,
    (ingredients.ordinality - 1)::INTEGER,
    CASE
        WHEN COALESCE((ingredients.ingredient->>'is_promotional')::BOOLEAN, FALSE)
            THEN NULLIF(ingredients.ingredient->>'deal_id', '')
        ELSE NULL
    END,
    COALESCE((ingredients.ingredient->>'is_promotional')::BOOLEAN, FALSE),
    COALESCE(ingredients.ingredient->>'name', ''),
    COALESCE(ingredients.ingredient->>'quantity', '')
FROM meal_plan_recipe AS mpr
INNER JOIN recipe AS r ON r.recipe_id = mpr.recipe_id
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(r.ingredients, '[]'::JSONB))
    WITH ORDINALITY AS ingredients(ingredient, ordinality)
ON CONFLICT (meal_plan_id, recipe_id, ingredient_index) DO NOTHING;
