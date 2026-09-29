CREATE OR REPLACE PROCEDURE sp_import_grocery_stores_batch_v2(
    p_stores JSONB,
    INOUT p_imported_count INTEGER DEFAULT 0
)
LANGUAGE plpgsql
AS $$
DECLARE
    elem JSONB;
BEGIN
    p_imported_count := 0;
    FOR elem IN SELECT * FROM jsonb_array_elements(p_stores)
    LOOP
        CALL sp_upsert_grocery_store(
            (elem->>'store_id')::VARCHAR(32),
            (elem->>'chain_id')::VARCHAR(32),
            (elem->>'store_number')::VARCHAR(16),
            (elem->>'store_name')::VARCHAR(128),
            (elem->>'street_address')::VARCHAR(255),
            (elem->>'city')::VARCHAR(100),
            (elem->>'state_province')::VARCHAR(32),
            (elem->>'postal_code')::VARCHAR(16),
            (elem->>'longitude')::DOUBLE PRECISION,
            (elem->>'latitude')::DOUBLE PRECISION
        );
        p_imported_count := p_imported_count + 1;
    END LOOP;
END;
$$;