\connect mealshopper_planner
\i /planner-postgres-init/01_tables/001_recipe.sql
\i /planner-postgres-init/02_functions/001_fn_get_recipe.sql
\i /planner-postgres-init/02_functions/002_fn_get_recipes_for_user.sql
\i /planner-postgres-init/03_procedures/001_sp_create_recipe.sql
\i /planner-postgres-init/03_procedures/002_sp_associate_user_recipe.sql
ALTER TABLE recipe OWNER TO planner_app;
ALTER TABLE user_recipe OWNER TO planner_app;
ALTER FUNCTION fn_get_recipe(UUID) OWNER TO planner_app;
ALTER FUNCTION fn_get_recipes_for_user(UUID) OWNER TO planner_app;
ALTER PROCEDURE sp_create_recipe(UUID, TEXT, TEXT, JSONB) OWNER TO planner_app;
ALTER PROCEDURE sp_associate_user_recipe(UUID, UUID) OWNER TO planner_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO planner_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO planner_app;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA public TO planner_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO planner_app;
