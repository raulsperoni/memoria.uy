#!/bin/bash

# Exit on error
set -e

# Variables
REPO_URL="https://github.com/yourusername/memoria.uy.git"
PROJECT_DIR="/path/to/your/project"
DOMAIN="yourdomain.com"

# Update these with your actual values before running the script
# or pass them as environment variables

echo "Starting deployment process..."

# Check if the project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Project directory does not exist. Cloning repository..."
    git clone $REPO_URL $PROJECT_DIR
    cd $PROJECT_DIR
else
    echo "Project directory exists. Pulling latest changes..."
    cd $PROJECT_DIR
    git pull
fi

# Check if .env file exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please update the .env file with your production settings!"
    exit 1
fi

# Update Nginx configuration with the correct domain
echo "Updating Nginx configuration..."
sed -i "s/yourdomain.com/$DOMAIN/g" $PROJECT_DIR/nginx/conf.d

# Build and start the Docker containers
echo "Building and starting Docker containers..."
docker-compose down
docker-compose up -d --build

# Run migrations
echo "Running database migrations..."
docker-compose exec -T web python manage.py migrate

# Build Tailwind CSS for production
echo "Building Tailwind CSS for production..."
docker-compose exec -T web make tailwind-build

# Collect static files
echo "Collecting static files..."
docker-compose exec -T web python manage.py collectstatic --noinput

echo "Deployment completed successfully!"
echo "Your application should now be running at https://$DOMAIN"
