CREATE OR REPLACE FUNCTION fn_get_recipes_for_user(p_user_id UUID)
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
    INNER JOIN user_recipe AS ur ON ur.recipe_id = r.recipe_id
    WHERE ur.user_id = p_user_id
    ORDER BY ur.associated_at DESC, r.created_at DESC;
$$;
