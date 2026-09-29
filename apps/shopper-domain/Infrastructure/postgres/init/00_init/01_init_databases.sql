-- -- 1. Create Shopper Domain Database and Role
-- CREATE USER shopper_app WITH PASSWORD 'ShopperApp_Dev_Pwd99!';
-- CREATE DATABASE mealshopper_shopper OWNER shopper_app;

-- -- Connect to shopper db and enable spatial extensions
-- \connect mealshopper_shopper;
-- CREATE EXTENSION IF NOT EXISTS postgis;
-- GRANT ALL PRIVILEGES ON DATABASE mealshopper_shopper TO shopper_app;
-- GRANT ALL ON SCHEMA public TO shopper_app;

-- -- 2. User Service Database and Role
-- \connect mealshopper;
-- -- existing user-service migrations run here