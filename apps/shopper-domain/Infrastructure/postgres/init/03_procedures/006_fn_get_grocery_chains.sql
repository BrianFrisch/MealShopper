CREATE OR REPLACE FUNCTION fn_get_grocery_chains(p_chain_id VARCHAR(32) DEFAULT NULL)
RETURNS TABLE (
    chain_id VARCHAR(32),
    display_name VARCHAR(64),
    adapter_name VARCHAR(32),
    spider_name VARCHAR(64),
    flyer_source_type VARCHAR(32),
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)
LANGUAGE sql
STABLE
AS $$
    SELECT 
        chain_id,
        display_name,
        adapter_name,
        spider_name,
        flyer_source_type,
        is_active,
        created_at,
        updated_at
    FROM grocery_chain
    WHERE (p_chain_id IS NULL OR chain_id = p_chain_id)
      AND is_active = TRUE;
$$;
