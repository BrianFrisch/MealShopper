CREATE OR REPLACE FUNCTION fn_get_meal_plan(p_meal_plan_id UUID)
RETURNS TABLE (
    meal_plan_id UUID,
    meal_plan_name TEXT,
    user_id UUID,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)
LANGUAGE SQL
STABLE
AS $$
    SELECT mp.meal_plan_id, mp.meal_plan_name, mp.user_id, mp.created_at, mp.updated_at
    FROM meal_plan AS mp
    WHERE mp.meal_plan_id = p_meal_plan_id;
$$;
