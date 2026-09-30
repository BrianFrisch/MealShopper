#!/bin/bash
set -e
chmod +x ./Infrastructure/postgres/deploy.sh
# Run service's own migrations independently
./Infrastructure/postgres/deploy.sh

# Start FastAPI application
exec uvicorn src.main:app --host 0.0.0.0 --port 8001