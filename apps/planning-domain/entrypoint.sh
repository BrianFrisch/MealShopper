#!/bin/bash
set -e
sh /app/Infrastructure/postgres/deploy.sh
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8002}"
