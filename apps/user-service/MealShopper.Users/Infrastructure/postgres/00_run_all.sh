#!/bin/bash
set -e

# Run all .sql files found in subdirectories in order
find /docker-entrypoint-initdb.d/init -type f -name "*.sql" | sort | while read -r f; do
    echo "Running $f..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$f"
done