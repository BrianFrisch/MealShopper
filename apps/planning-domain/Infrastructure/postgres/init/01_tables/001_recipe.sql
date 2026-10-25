CREATE TABLE IF NOT EXISTS recipe (
    recipe_id UUID PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    protein_subtype VARCHAR(50),
    cuisine VARCHAR(50),
    image_url TEXT,
    ingredients JSONB NOT NULL DEFAULT '[]'::JSONB,
    directions JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE recipe
    DROP CONSTRAINT IF EXISTS uq_recipe_meal_plan_meal,
    DROP COLUMN IF EXISTS meal_plan_id,
    DROP COLUMN IF EXISTS source_meal_id,
    DROP COLUMN IF EXISTS recipe_data,
    ADD COLUMN IF NOT EXISTS title VARCHAR(200) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS protein_subtype VARCHAR(50),
    ADD COLUMN IF NOT EXISTS cuisine VARCHAR(50),
    ADD COLUMN IF NOT EXISTS image_url TEXT,
    ADD COLUMN IF NOT EXISTS ingredients JSONB NOT NULL DEFAULT '[]'::JSONB,
    ADD COLUMN IF NOT EXISTS directions JSONB NOT NULL DEFAULT '[]'::JSONB;

CREATE TABLE IF NOT EXISTS user_recipe (
    user_id UUID NOT NULL,
    recipe_id UUID NOT NULL REFERENCES recipe (recipe_id) ON DELETE CASCADE,
    associated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, recipe_id)
);

CREATE INDEX IF NOT EXISTS ix_user_recipe_recipe_id ON user_recipe (recipe_id);
