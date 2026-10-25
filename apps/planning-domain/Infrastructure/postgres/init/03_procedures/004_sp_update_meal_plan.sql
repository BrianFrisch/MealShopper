DROP PROCEDURE IF EXISTS sp_update_meal_plan(UUID, TEXT);
DROP PROCEDURE IF EXISTS sp_update_meal_plan(UUID, TEXT, BOOLEAN);

CREATE PROCEDURE sp_update_meal_plan(
    IN p_meal_plan_id UUID,
    IN p_meal_plan_name TEXT,
    IN p_is_archived BOOLEAN
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE meal_plan
    SET meal_plan_name = p_meal_plan_name,
        is_archived = COALESCE(p_is_archived, is_archived),
        updated_at = CLOCK_TIMESTAMP()
    WHERE meal_plan_id = p_meal_plan_id;
END;
$$;
