CREATE TABLE IF NOT EXISTS grocery_chain (
    chain_id VARCHAR(32) PRIMARY KEY,              -- 'ralphs', 'aldi', 'vons'
    display_name VARCHAR(64) NOT NULL,             -- 'Ralphs', 'ALDI'
    adapter_name VARCHAR(32) NOT NULL,             -- matches DealAdapterFactory key
    spider_name VARCHAR(64),                       -- AllThePlaces spider e.g. 'kroger_us', 'aldi_sud_us'
    flyer_source_type VARCHAR(32) NOT NULL DEFAULT 'flipp',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);