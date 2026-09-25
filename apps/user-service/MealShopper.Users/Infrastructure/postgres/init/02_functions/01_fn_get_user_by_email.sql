CREATE OR REPLACE FUNCTION fn_get_user_by_email(p_email VARCHAR(256))
RETURNS TABLE (
    id UUID,
    email VARCHAR(256),
    password_hash TEXT,
    roles TEXT[],
    failed_attempts INT,
    lockout_until TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT u.id, u.email, u.password_hash, u.roles, u.failed_attempts, u.lockout_until
    FROM users u
    WHERE u.normalized_email = UPPER(p_email);
END;
$$;