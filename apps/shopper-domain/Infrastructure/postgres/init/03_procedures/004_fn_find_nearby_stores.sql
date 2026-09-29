CREATE OR REPLACE FUNCTION fn_find_nearby_stores(
    p_longitude DOUBLE PRECISION,
    p_latitude DOUBLE PRECISION,
    p_radius_miles DOUBLE PRECISION DEFAULT 10.0,
    p_max_stores INTEGER DEFAULT 20
)
RETURNS TABLE (
    store_id VARCHAR(32),
    chain_id VARCHAR(32),
    chain_name VARCHAR(64),
    adapter_name VARCHAR(32),
    name VARCHAR(128),
    street_address VARCHAR(255),
    city VARCHAR(100),
    state_province VARCHAR(32),
    postal_code VARCHAR(16),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    distance_miles NUMERIC
)
LANGUAGE sql
STABLE
AS $$
    SELECT 
        s.store_id,
        s.chain_id,
        c.display_name AS chain_name,
        c.adapter_name,
        s.store_name,
        s.street_address,
        s.city,
        s.state_province,
        s.postal_code,
        ST_Y(s.store_location::geometry) AS latitude,
        ST_X(s.store_location::geometry) AS longitude,
        ROUND((ST_Distance(s.store_location, ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography) / 1609.34)::numeric, 2) AS distance_miles
    FROM grocery_store s
    JOIN grocery_chain c ON s.chain_id = c.chain_id
    WHERE s.is_active = TRUE 
      AND c.is_active = TRUE
      AND ST_DWithin(
          s.store_location,
          ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography,
          p_radius_miles * 1609.34
      )
    ORDER BY distance_miles ASC
    LIMIT p_max_stores;
$$;