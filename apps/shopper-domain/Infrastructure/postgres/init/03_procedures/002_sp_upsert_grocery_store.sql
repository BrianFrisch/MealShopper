CREATE OR REPLACE PROCEDURE sp_upsert_grocery_store(
    p_store_id VARCHAR(32),
    p_chain_id VARCHAR(32),
    p_store_number VARCHAR(16),
    p_name VARCHAR(128),
    p_street_address VARCHAR(255),
    p_city VARCHAR(100),
    p_state_province VARCHAR(32),
    p_postal_code VARCHAR(16),
    p_longitude DOUBLE PRECISION,
    p_latitude DOUBLE PRECISION
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO grocery_store (
        store_id, chain_id, store_number, store_name, street_address,
        city, state_province, postal_code, store_location, is_active, updated_at
    )
    VALUES (
        p_store_id, p_chain_id, p_store_number, p_name, p_street_address,
        p_city, p_state_province, p_postal_code,
        ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography,
        TRUE, NOW()
    )
    ON CONFLICT (store_id) DO UPDATE SET
        store_name = EXCLUDED.store_name,
        street_address = EXCLUDED.street_address,
        city = EXCLUDED.city,
        state_province = EXCLUDED.state_province,
        postal_code = EXCLUDED.postal_code,
        store_location = EXCLUDED.store_location,
        is_active = TRUE,
        updated_at = NOW();
END;
$$;