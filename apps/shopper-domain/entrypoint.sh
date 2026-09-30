#!/bin/bash
set -e
/app/Infrastructure/postgres/deploy.sh
exec uvicorn src.main:app --host 0.0.0.0 --port 8001
