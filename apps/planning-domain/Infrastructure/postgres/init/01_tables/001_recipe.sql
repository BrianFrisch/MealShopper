CREATE TABLE IF NOT EXISTS recipe (
    recipe_id UUID PRIMARY KEY,
    meal_plan_id TEXT NOT NULL,
    source_meal_id TEXT NOT NULL,
    recipe_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_recipe_meal_plan_meal UNIQUE (meal_plan_id, source_meal_id)
);

CREATE TABLE IF NOT EXISTS user_recipe (
    user_id UUID NOT NULL,
    recipe_id UUID NOT NULL REFERENCES recipe (recipe_id) ON DELETE CASCADE,
    associated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     PRIMARY KEY (user_id, recipe_id)
);

CREATE INDEX IF NOT EXISTS ix_user_recipe_recipe_id ON user_recipe (recipe_id);
