#!/bin/bash
set -e

echo "Running database migrations..."
poetry run python manage.py migrate

echo "Database migration completed successfully!"
