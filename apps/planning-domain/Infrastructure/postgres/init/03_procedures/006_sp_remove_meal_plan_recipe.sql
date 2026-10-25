CREATE OR REPLACE PROCEDURE sp_remove_meal_plan_recipe(
    p_meal_plan_id UUID,
    p_recipe_id UUID
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM meal_plan_ingredient
    WHERE meal_plan_id = p_meal_plan_id
      AND recipe_id = p_recipe_id;

    DELETE FROM meal_plan_recipe
    WHERE meal_plan_id = p_meal_plan_id
      AND recipe_id = p_recipe_id;
END;
$$;
