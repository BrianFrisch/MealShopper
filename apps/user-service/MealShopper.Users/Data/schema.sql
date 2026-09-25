-- 1. Tables
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(256) NOT NULL UNIQUE,
    normalized_email VARCHAR(256) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    roles TEXT[] NOT NULL DEFAULT '{"User"}',
    failed_attempts INT NOT NULL DEFAULT 0,
    lockout_until TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


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

-- Grant least-privileged access
--GRANT SELECT, INSERT, UPDATE ON user_preferences TO mealshopper_app;

-- 2. Stored Procedure: Upsert User Account
CREATE OR REPLACE PROCEDURE sp_create_user(
    p_id UUID,
    p_email VARCHAR(256),
    p_password_hash TEXT,
    p_roles TEXT[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO users (id, email, normalized_email, password_hash, roles)
    VALUES (p_id, p_email, UPPER(p_email), p_password_hash, p_roles)
    ON CONFLICT (normalized_email) DO NOTHING;
END;
$$;

-- 3. Stored Function: Get User by Normalized Email
CREATE OR REPLACE FUNCTION fn_get_user_by_email(p_email VARCHAR(256))
RETURNS TABLE (
    id UUID,
    email VARCHAR(256),
    password_hash TEXT,
    roles TEXT[],
    failed_attempts INT,
    lockout_until TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT u.id, u.email, u.password_hash, u.roles, u.failed_attempts, u.lockout_until
    FROM users u
    WHERE u.normalized_email = UPPER(p_email);
END;
$$;

-- 4. Stored Procedure: Record Login Failure & Lockout
CREATE OR REPLACE PROCEDURE sp_record_login_failure(
    p_user_id UUID,
    p_max_attempts INT,
    p_lockout_minutes INT
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE users
    SET failed_attempts = failed_attempts + 1,
        lockout_until = CASE 
            WHEN failed_attempts + 1 >= p_max_attempts 
            THEN NOW() + (p_lockout_minutes || ' minutes')::INTERVAL 
            ELSE lockout_until 
        END
    WHERE id = p_user_id;
END;
$$;

-- 5. Stored Procedure: Reset Failed Attempts
CREATE OR REPLACE PROCEDURE sp_reset_login_failure(p_user_id UUID)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE users
    SET failed_attempts = 0,
        lockout_until = NULL
    WHERE id = p_user_id;
END;
$$;

-- 6. Stored Function: Get User Preferences
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
) AS $$
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
$$ LANGUAGE plpgsql;

-- Stored Procedure: Upsert Preferences
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