\getenv planner_password PLANNER_DB_PASSWORD

SELECT format('CREATE ROLE planner_app WITH LOGIN PASSWORD %L', :'planner_password')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'planner_app')
\gexec
ALTER ROLE planner_app WITH PASSWORD :'planner_password';

SELECT format('CREATE DATABASE mealshopper_planner OWNER planner_app')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_database WHERE datname = 'mealshopper_planner')
\gexec

\connect mealshopper_planner
GRANT ALL PRIVILEGES ON DATABASE mealshopper_planner TO planner_app;
GRANT ALL ON SCHEMA public TO planner_app;
