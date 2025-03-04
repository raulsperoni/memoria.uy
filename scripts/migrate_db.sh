#!/bin/bash
set -e

echo "Running database migrations..."
python manage.py migrate

echo "Database migration completed successfully!"
