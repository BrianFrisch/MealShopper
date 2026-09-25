CREATE OR REPLACE PROCEDURE sp_upsert_user_preferences(
    p_user_id UUID,
    p_address_label VARCHAR(100),
    p_latitude NUMERIC,
    p_longitude NUMERIC,
    p_search_radius_miles INT,
    p_max_stores INT,
    p_household_size INT,
    p_target_meal_count INT,
    p_preferred_cuisines TEXT[],
    p_dietary_restrictions TEXT[],
    p_avoid_ingredients TEXT[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO user_preferences (
        user_id,
        default_address_label,
        latitude,
        longitude,
        search_radius_miles,
        max_stores,
        household_size,
        target_meal_count,
        preferred_cuisines,
        dietary_restrictions,
        avoid_ingredients,
        updated_at
    )
    VALUES (
        p_user_id,
        p_address_label,
        p_latitude,
        p_longitude,
        p_search_radius_miles,
        p_max_stores,
        p_household_size,
        p_target_meal_count,
        p_preferred_cuisines,
        p_dietary_restrictions,
        p_avoid_ingredients,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (user_id) DO UPDATE SET
        default_address_label = EXCLUDED.default_address_label,
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        search_radius_miles = EXCLUDED.search_radius_miles,
        max_stores = EXCLUDED.max_stores,
        household_size = EXCLUDED.household_size,
        target_meal_count = EXCLUDED.target_meal_count,
        preferred_cuisines = EXCLUDED.preferred_cuisines,
        dietary_restrictions = EXCLUDED.dietary_restrictions,
        avoid_ingredients = EXCLUDED.avoid_ingredients,
        updated_at = CURRENT_TIMESTAMP;
END;
$$;