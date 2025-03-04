#!/bin/bash
set -e

echo "Installing Tailwind dependencies..."
python manage.py tailwind install

echo "Building Tailwind CSS..."
python manage.py tailwind build

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Asset building completed successfully!"
