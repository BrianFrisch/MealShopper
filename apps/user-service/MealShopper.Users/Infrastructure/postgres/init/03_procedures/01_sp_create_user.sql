CREATE OR REPLACE PROCEDURE sp_create_user(
    p_id UUID,
    p_email VARCHAR(256),
    p_password_hash TEXT,
    p_roles TEXT[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO users (id, email, normalized_email, password_hash, roles)
    VALUES (p_id, p_email, UPPER(p_email), p_password_hash, p_roles)
    ON CONFLICT (normalized_email) DO NOTHING;
END;
$$;