-- infra/postgres/init/00_create_service_databases.sql

-- 1. Shopper Domain Role & DB
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'shopper_app') THEN
        CREATE ROLE shopper_app WITH LOGIN PASSWORD 'ShopperApp_Dev_Pwd99!';
    END IF;
END
$$;

SELECT 'CREATE DATABASE mealshopper_shopper OWNER shopper_app'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mealshopper_shopper')\gexec

-- Connect to shopper db and grant PostGIS capabilities to the service user
\connect mealshopper_shopper;
CREATE EXTENSION IF NOT EXISTS postgis;
GRANT ALL PRIVILEGES ON DATABASE mealshopper_shopper TO shopper_app;
GRANT ALL ON SCHEMA public TO shopper_app;

-- 2. User Service Role & DB
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'users_app') THEN
        CREATE ROLE users_app WITH LOGIN PASSWORD 'MealShopperApp_Dev_Pwd99!';
    END IF;
END
$$;

SELECT 'CREATE DATABASE mealshopper_users OWNER users_app'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mealshopper_users')\gexec

\connect mealshopper_users;
GRANT ALL PRIVILEGES ON DATABASE mealshopper_users TO users_app;
GRANT ALL ON SCHEMA public TO users_app;