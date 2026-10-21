#!/bin/sh
set -eu

DB_HOST="${PLANNER_DB_HOST:-postgres}"
DB_PORT="${PLANNER_DB_PORT:-5432}"
DB_NAME="${PLANNER_DB_NAME:-mealshopper_planner}"
DB_USER="${PLANNER_DB_USER:-planner_app}"
: "${PLANNER_DB_PASSWORD:?PLANNER_DB_PASSWORD must be set}"
export PGPASSWORD="$PLANNER_DB_PASSWORD"


echo "=== [Planning-Domain] Running Database Migrations on ${DB_NAME} at ${DB_HOST}:${DB_PORT} ==="

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/init"

if [ -d "$SCRIPT_DIR" ]; then
    find "$SCRIPT_DIR" -type f -name "*.sql" | sort | while read -r f; do
        echo "[Planning-Domain] Applying $f..."
        psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$f"
    done
fi

echo "=== [Planning-Domain] Migrations successfully completed ==="
