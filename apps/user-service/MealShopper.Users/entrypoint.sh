#!/bin/bash
set -e

# Run service's own migrations independently
./Infrastructure/postgres/deploy.sh

exec dotnet MealShopper.Users.dll