DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = (
            SELECT n.nspname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.oid = 'grocery_chain'::regclass
        )
          AND table_name = 'grocery_chain'
          AND column_name = 'spider_name'
          AND character_maximum_length < 1024
    ) THEN
        ALTER TABLE grocery_chain
            ALTER COLUMN spider_name TYPE VARCHAR(1024);
    END IF;
END;
$$;
