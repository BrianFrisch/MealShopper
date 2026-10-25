CREATE OR REPLACE PROCEDURE sp_associate_meal_plan_recipe(
    p_meal_plan_id UUID,
    p_recipe_id UUID
)
LANGUAGE SQL
AS $$
    INSERT INTO meal_plan_recipe (meal_plan_id, recipe_id)
    VALUES (p_meal_plan_id, p_recipe_id)
    ON CONFLICT (meal_plan_id, recipe_id) DO NOTHING;
$$;
