CREATE OR REPLACE PROCEDURE sp_reset_login_failure(p_user_id UUID)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE users
    SET failed_attempts = 0,
        lockout_until = NULL
    WHERE id = p_user_id;
END;
$$;