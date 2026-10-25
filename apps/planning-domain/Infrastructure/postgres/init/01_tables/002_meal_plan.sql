CREATE TABLE IF NOT EXISTS meal_plan (
    meal_plan_id UUID PRIMARY KEY,
    meal_plan_name TEXT NOT NULL,
    user_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_meal_plan_user_id ON meal_plan (user_id);

CREATE TABLE IF NOT EXISTS meal_plan_recipe (
    meal_plan_id UUID NOT NULL REFERENCES meal_plan (meal_plan_id) ON DELETE CASCADE,
    recipe_id UUID NOT NULL REFERENCES recipe (recipe_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (meal_plan_id, recipe_id)
);

CREATE INDEX IF NOT EXISTS ix_meal_plan_recipe_recipe_id ON meal_plan_recipe (recipe_id);
