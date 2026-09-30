-- apps/shopper-domain/Infrastructure/postgres/init/05_data/001_grocery_chain_data.sql

INSERT INTO grocery_chain (chain_id, display_name, adapter_name, spider_name, flyer_source_type, is_active)
VALUES
    ('ralphs', 'Ralphs', 'ralphs', 'kroger_us', 'flipp', TRUE),
    ('aldi', 'ALDI', 'aldi', 'aldi_sud_us', 'flipp', TRUE),
    ('vons', 'Vons', 'vons', 'vons', 'flipp', TRUE),
    ('trader-joes', 'Trader Joe''s', 'trader-joes', 'trader_joes', 'flipp', TRUE)
ON CONFLICT (chain_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    adapter_name = EXCLUDED.adapter_name,
    spider_name = EXCLUDED.spider_name,
    flyer_source_type = EXCLUDED.flyer_source_type,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

