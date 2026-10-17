\getenv shopper_password SHOPPER_DB_PASSWORD
\getenv users_password USERS_DB_PASSWORD

SELECT format('CREATE ROLE shopper_app WITH LOGIN PASSWORD %L', :'shopper_password')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'shopper_app')
\gexec
ALTER ROLE shopper_app WITH PASSWORD :'shopper_password';

SELECT format('CREATE DATABASE mealshopper_shopper OWNER shopper_app')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_database WHERE datname = 'mealshopper_shopper')
\gexec

\connect mealshopper_shopper
CREATE EXTENSION IF NOT EXISTS postgis;
GRANT ALL PRIVILEGES ON DATABASE mealshopper_shopper TO shopper_app;
GRANT ALL ON SCHEMA public TO shopper_app;

SELECT format('CREATE ROLE users_app WITH LOGIN PASSWORD %L', :'users_password')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'users_app')
\gexec
ALTER ROLE users_app WITH PASSWORD :'users_password';

SELECT format('CREATE DATABASE mealshopper_users OWNER users_app')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_database WHERE datname = 'mealshopper_users')
\gexec

\connect mealshopper_users
GRANT ALL PRIVILEGES ON DATABASE mealshopper_users TO users_app;
GRANT ALL ON SCHEMA public TO users_app;