DROP FUNCTION IF EXISTS fn_get_meal_plan(UUID);

CREATE OR REPLACE FUNCTION fn_get_meal_plan(p_meal_plan_id UUID)
RETURNS TABLE (
    meal_plan_id UUID,
    meal_plan_name TEXT,
    user_id UUID,
    recipe_count INTEGER,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        mp.meal_plan_id,
        mp.meal_plan_name,
        mp.user_id,
        COUNT(mpr.recipe_id)::INTEGER AS recipe_count,
        mp.created_at,
        mp.updated_at
    FROM meal_plan AS mp
    LEFT JOIN meal_plan_recipe AS mpr ON mpr.meal_plan_id = mp.meal_plan_id
    WHERE mp.meal_plan_id = p_meal_plan_id
    GROUP BY mp.meal_plan_id, mp.meal_plan_name, mp.user_id, mp.created_at, mp.updated_at;
$$;
