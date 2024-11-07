#!/bin/bash
set -e

# Create migrations directory if it doesn't exist
mkdir -p alembic/versions

# Run migrations
echo "Running database migrations..."
alembic upgrade head

echo "Migrations completed successfully!" 