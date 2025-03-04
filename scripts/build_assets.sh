#!/bin/bash
set -e

echo "Installing Tailwind dependencies..."
poetry run python manage.py tailwind install

echo "Building Tailwind CSS..."
poetry run python manage.py tailwind build

echo "Collecting static files..."
poetry run python manage.py collectstatic --noinput

echo "Asset building completed successfully!"
