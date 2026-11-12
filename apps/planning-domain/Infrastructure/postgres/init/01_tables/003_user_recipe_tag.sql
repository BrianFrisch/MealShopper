CREATE TABLE IF NOT EXISTS user_recipe_tag (
    user_id UUID NOT NULL,
    recipe_id UUID NOT NULL,
    tag VARCHAR(16) COLLATE "C" NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, recipe_id, tag),
    FOREIGN KEY (user_id, recipe_id)
        REFERENCES user_recipe (user_id, recipe_id) ON DELETE CASCADE
);
