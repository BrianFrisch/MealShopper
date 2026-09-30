#!/bin/bash
set -e

# Default to Docker service names if environment variables are not set
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-mealshopper_shopper}"
DB_USER="${POSTGRES_USER:-shopper_app}"
export PGPASSWORD="${POSTGRES_PASSWORD:-ShopperApp_Dev_Pwd99!}"

echo "=== [Shopper-Domain] Running Database Migrations on ${DB_NAME} at ${DB_HOST}:${DB_PORT} ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/init"

if [ -d "$SCRIPT_DIR" ]; then
    find "$SCRIPT_DIR" -type f -name "*.sql" | sort | while read -r f; do
        echo "[Shopper-Domain] Applying $f..."
        psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$f"
    done
fi

echo "=== [Shopper-Domain] Migrations successfully completed ==="