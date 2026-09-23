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
    street VARCHAR(255) NOT NULL DEFAULT '',
    city VARCHAR(100) NOT NULL DEFAULT '',
    state VARCHAR(50) NOT NULL DEFAULT '',
    zip_code VARCHAR(20) NOT NULL DEFAULT '',
    search_radius_miles INT NOT NULL DEFAULT 5,
    max_stores INT NOT NULL DEFAULT 2,
    preferred_cuisines JSONB NOT NULL DEFAULT '[]'::jsonb,
    avoid_ingredients JSONB NOT NULL DEFAULT '[]'::jsonb
);

-- 2. Stored Procedure: Upsert User Account
CREATE OR REPLACE PROCEDURE sp_create_user(
    p_id UUID,
    p_email VARCHAR(256),
    p_password_hash TEXT,
    p_roles TEXT[],
    p_street VARCHAR(255),
    p_city VARCHAR(100),
    p_state VARCHAR(50),
    p_zip VARCHAR(20),
    p_cuisines JSONB,
    p_avoid JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO users (id, email, normalized_email, password_hash, roles)
    VALUES (p_id, p_email, UPPER(p_email), p_password_hash, p_roles)
    ON CONFLICT (normalized_email) DO NOTHING;

    INSERT INTO user_preferences (
        user_id, street, city, state, zip_code, preferred_cuisines, avoid_ingredients
    )
    VALUES (
        p_id, p_street, p_city, p_state, p_zip, p_cuisines, p_avoid
    )
    ON CONFLICT (user_id) DO UPDATE SET
        street = EXCLUDED.street,
        city = EXCLUDED.city,
        state = EXCLUDED.state,
        zip_code = EXCLUDED.zip_code,
        preferred_cuisines = EXCLUDED.preferred_cuisines,
        avoid_ingredients = EXCLUDED.avoid_ingredients;
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
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    search_radius_miles INT,
    max_stores INT,
    preferred_cuisines TEXT,
    avoid_ingredients TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.user_id, 
        p.street, 
        p.city, 
        p.state, 
        p.zip_code, 
        p.search_radius_miles, 
        p.max_stores, 
        p.preferred_cuisines::text, 
        p.avoid_ingredients::text
    FROM user_preferences p
    WHERE p.user_id = p_user_id;
END;
$$;

-- 7. Application Role & Least-Privilege Grants
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mealshopper_app') THEN
        CREATE ROLE mealshopper_app WITH LOGIN PASSWORD 'MealShopperApp_Dev_Pwd99!';
    ELSE
        ALTER ROLE mealshopper_app WITH PASSWORD 'MealShopperApp_Dev_Pwd99!';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE mealshopper TO mealshopper_app;
GRANT USAGE ON SCHEMA public TO mealshopper_app;

-- Grant DML execution on tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mealshopper_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mealshopper_app;

-- Grant Execution on functions and procedures
GRANT EXECUTE ON ALL ROUTINES IN SCHEMA public TO mealshopper_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON ROUTINES TO mealshopper_app;

-- -- 8. Seed Default Test User (Password: Password123!)
-- -- Hash generated using standard ASP.NET Core Identity PasswordHasher (PBKDF2 with HMAC-SHA256)
-- CALL sp_create_user(
--     'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d'::UUID,
--     'testuser@mealshopper.local',
--     'AQAAAAIAAYagAAAAEI46P3jC5v1P84d0bH2+M5rV8N9m9K9E3S4f8t8r2J5W8Z7+L3e1Q==',
--     ARRAY['User'],
--     '15625 Hawthorne Blvd',
--     'Lawndale',
--     'CA',
--     '90260',
--     '["Italian", "Mexican"]'::jsonb,
--     '["Peanuts"]'::jsonb
-- );