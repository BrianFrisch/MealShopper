CREATE OR REPLACE PROCEDURE sp_upsert_grocery_chain(
    p_chain_id VARCHAR(32),
    p_display_name VARCHAR(64),
    p_adapter_name VARCHAR(32),
    p_flyer_source_type VARCHAR(32) DEFAULT 'flipp'
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO grocery_chain (
        chain_id, display_name, adapter_name, flyer_source_type, is_active, updated_at
    )
    VALUES (
        p_chain_id, p_display_name, p_adapter_name, p_flyer_source_type, TRUE, NOW()
    )
    ON CONFLICT (chain_id) DO UPDATE SET
        display_name = EXCLUDED.display_name,
        adapter_name = EXCLUDED.adapter_name,
        flyer_source_type = EXCLUDED.flyer_source_type,
        updated_at = NOW();
END;
$$;