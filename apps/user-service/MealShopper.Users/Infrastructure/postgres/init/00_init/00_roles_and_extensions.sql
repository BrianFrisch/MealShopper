CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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