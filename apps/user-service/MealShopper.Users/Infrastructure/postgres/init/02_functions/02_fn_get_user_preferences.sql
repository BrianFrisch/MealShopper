CREATE OR REPLACE FUNCTION fn_get_user_preferences(p_user_id UUID)
RETURNS TABLE (
    user_id UUID,
    default_address_label VARCHAR(100),
    latitude NUMERIC,
    longitude NUMERIC,
    search_radius_miles INT,
    max_stores INT,
    household_size INT,
    target_meal_count INT,
    preferred_cuisines TEXT[],
    dietary_restrictions TEXT[],
    avoid_ingredients TEXT[],
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        up.user_id,
        up.default_address_label,
        up.latitude,
        up.longitude,
        up.search_radius_miles,
        up.max_stores,
        up.household_size,
        up.target_meal_count,
        up.preferred_cuisines,
        up.dietary_restrictions,
        up.avoid_ingredients,
        up.created_at,
        up.updated_at
    FROM user_preferences up
    WHERE up.user_id = p_user_id;
END;
$$;