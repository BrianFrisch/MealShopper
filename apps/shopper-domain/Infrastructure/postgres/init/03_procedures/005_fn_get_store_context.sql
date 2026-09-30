CREATE OR REPLACE FUNCTION fn_get_store_context(p_store_id VARCHAR(32))
RETURNS TABLE (
    store_id VARCHAR(32),
    chain_id VARCHAR(32),
    store_number VARCHAR(16),
    street_address VARCHAR(255),
    city VARCHAR(100),
    postal_code VARCHAR(16),
    store_location GEOGRAPHY(Point, 4326),
    store_is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    display_name VARCHAR(64),
    adapter_name VARCHAR(32),
    flyer_source_type VARCHAR(32),
    chain_is_active BOOLEAN
)
LANGUAGE sql
STABLE
AS $$
    SELECT 
        s.store_id,
        s.chain_id,
        s.store_number,
        s.street_address,
        s.city,
        s.postal_code,
        s.store_location,
        s.is_active,
        s.created_at,
        s.updated_at,
        c.display_name,
        c.adapter_name,
        c.flyer_source_type,
        c.is_active
    FROM grocery_store s
    JOIN grocery_chain c ON s.chain_id = c.chain_id
    WHERE s.store_id = p_store_id
    LIMIT 1;
$$;