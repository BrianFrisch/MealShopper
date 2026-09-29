CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS grocery_store (
    store_id VARCHAR(32) PRIMARY KEY,              -- 'ralphs-101', 'aldi-421'
    chain_id VARCHAR(32) NOT NULL REFERENCES grocery_chain(chain_id) ON DELETE RESTRICT,
    store_number VARCHAR(16) NOT NULL,             -- '101', '421'
    store_name VARCHAR(128) NOT NULL,
    street_address VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state_province VARCHAR(32) NOT NULL,
    postal_code VARCHAR(16) NOT NULL,
    store_location GEOGRAPHY(Point, 4326) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_grocery_store_chain_number UNIQUE (chain_id, store_number)
);

-- Spatial index for radius calculations
CREATE INDEX IF NOT EXISTS idx_grocery_store_location ON grocery_store USING GIST (store_location);
CREATE INDEX IF NOT EXISTS idx_grocery_store_postal ON grocery_store (postal_code);