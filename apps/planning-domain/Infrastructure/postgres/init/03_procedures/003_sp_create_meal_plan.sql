CREATE OR REPLACE PROCEDURE sp_create_meal_plan(
    INOUT p_meal_plan_id UUID,
    IN p_meal_plan_name TEXT,
    IN p_user_id UUID
)
LANGUAGE plpgsql
AS $$
BEGIN
    p_meal_plan_id := COALESCE(p_meal_plan_id, gen_random_uuid());

    INSERT INTO meal_plan (meal_plan_id, meal_plan_name, user_id, created_at, updated_at)
    VALUES (p_meal_plan_id, p_meal_plan_name, p_user_id, NOW(), NOW())
    ON CONFLICT (meal_plan_id)
    DO UPDATE SET
        meal_plan_name = EXCLUDED.meal_plan_name,
        updated_at = NOW()
    RETURNING meal_plan_id INTO p_meal_plan_id;
END;
$$;
