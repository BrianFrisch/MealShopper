CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    default_address_label VARCHAR(100) NOT NULL DEFAULT '',
    latitude NUMERIC(9, 6) NOT NULL DEFAULT 0.0,
    longitude NUMERIC(9, 6) NOT NULL DEFAULT 0.0,
    search_radius_miles INT NOT NULL DEFAULT 10,
    max_stores INT NOT NULL DEFAULT 3,
    household_size INT NOT NULL DEFAULT 2,
    target_meal_count INT NOT NULL DEFAULT 3,
    preferred_cuisines TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    dietary_restrictions TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    avoid_ingredients TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);