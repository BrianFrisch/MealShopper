CREATE OR REPLACE PROCEDURE sp_update_meal_plan(
    IN p_meal_plan_id UUID,
    IN p_meal_plan_name TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE meal_plan
    SET meal_plan_name = p_meal_plan_name,
        updated_at = CLOCK_TIMESTAMP()
    WHERE meal_plan_id = p_meal_plan_id;
END;
$$;
