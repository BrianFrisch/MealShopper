CREATE OR REPLACE PROCEDURE sp_create_recipe(
    INOUT p_recipe_id UUID,
    IN p_meal_plan_id TEXT,
    IN p_source_meal_id TEXT,
    IN p_recipe_data JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO recipe (recipe_id, meal_plan_id, source_meal_id, recipe_data)
    VALUES (
        p_recipe_id,
        p_meal_plan_id,
        p_source_meal_id,
        jsonb_set(p_recipe_data, '{meal_id}', to_jsonb(p_recipe_id::TEXT), TRUE)
    )
    ON CONFLICT (meal_plan_id, source_meal_id)
    DO UPDATE SET recipe_data = jsonb_set(
        EXCLUDED.recipe_data,
        '{meal_id}',
        to_jsonb(recipe.recipe_id::TEXT),
        TRUE
    )
    RETURNING recipe_id INTO p_recipe_id;
END;
$$;
