CREATE OR REPLACE FUNCTION fn_get_recipe(p_recipe_id UUID)
RETURNS TABLE (
    recipe_id UUID,
    meal_plan_id TEXT,
    source_meal_id TEXT,
    recipe_data JSONB,
    created_at TIMESTAMPTZ
)
LANGUAGE SQL
STABLE
AS $$
    SELECT r.recipe_id, r.meal_plan_id, r.source_meal_id, r.recipe_data, r.created_at
    FROM recipe AS r
    WHERE r.recipe_id = p_recipe_id;
$$;
