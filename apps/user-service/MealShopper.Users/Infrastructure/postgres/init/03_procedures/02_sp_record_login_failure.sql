CREATE OR REPLACE PROCEDURE sp_record_login_failure(
    p_user_id UUID,
    p_max_attempts INT,
    p_lockout_minutes INT
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE users
    SET failed_attempts = failed_attempts + 1,
        lockout_until = CASE 
            WHEN failed_attempts + 1 >= p_max_attempts 
            THEN NOW() + (p_lockout_minutes || ' minutes')::INTERVAL 
            ELSE lockout_until 
        END
    WHERE id = p_user_id;
END;
$$;