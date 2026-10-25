\connect mealshopper_planner
\i /planner-postgres-init/01_tables/001_recipe.sql
\i /planner-postgres-init/01_tables/002_meal_plan.sql
\i /planner-postgres-init/02_functions/001_fn_get_recipe.sql
\i /planner-postgres-init/02_functions/002_fn_get_recipes_for_user.sql
\i /planner-postgres-init/02_functions/003_fn_get_meal_plan.sql
\i /planner-postgres-init/02_functions/004_fn_get_meal_plans_for_user.sql
\i /planner-postgres-init/02_functions/005_fn_get_recipes_for_meal_plan.sql
\i /planner-postgres-init/03_procedures/001_sp_create_recipe.sql
\i /planner-postgres-init/03_procedures/002_sp_associate_user_recipe.sql
\i /planner-postgres-init/03_procedures/003_sp_create_meal_plan.sql
\i /planner-postgres-init/03_procedures/004_sp_update_meal_plan.sql
\i /planner-postgres-init/03_procedures/005_sp_associate_meal_plan_recipe.sql
\i /planner-postgres-init/03_procedures/006_sp_remove_meal_plan_recipe.sql
ALTER TABLE recipe OWNER TO planner_app;
ALTER TABLE user_recipe OWNER TO planner_app;
ALTER TABLE meal_plan OWNER TO planner_app;
ALTER TABLE meal_plan_recipe OWNER TO planner_app;
ALTER TABLE meal_plan_ingredient OWNER TO planner_app;
ALTER FUNCTION fn_get_recipe(UUID) OWNER TO planner_app;
ALTER FUNCTION fn_get_recipes_for_user(UUID) OWNER TO planner_app;
ALTER FUNCTION fn_get_meal_plan(UUID) OWNER TO planner_app;
ALTER FUNCTION fn_get_meal_plans_for_user(UUID) OWNER TO planner_app;
ALTER FUNCTION fn_get_recipes_for_meal_plan(UUID) OWNER TO planner_app;
ALTER PROCEDURE sp_create_recipe(UUID, VARCHAR, TEXT, VARCHAR, VARCHAR, TEXT, JSONB, JSONB) OWNER TO planner_app;
ALTER PROCEDURE sp_associate_user_recipe(UUID, UUID) OWNER TO planner_app;
ALTER PROCEDURE sp_create_meal_plan(UUID, TEXT, UUID) OWNER TO planner_app;
ALTER PROCEDURE sp_update_meal_plan(UUID, TEXT, BOOLEAN) OWNER TO planner_app;
ALTER PROCEDURE sp_associate_meal_plan_recipe(UUID, UUID) OWNER TO planner_app;
ALTER PROCEDURE sp_remove_meal_plan_recipe(UUID, UUID) OWNER TO planner_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO planner_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO planner_app;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA public TO planner_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO planner_app;
