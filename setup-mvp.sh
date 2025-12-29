#!/bin/bash
# Memoria.uy MVP Setup Script
# Run this to get a clean local environment

set -e  # Exit on error

echo "🚀 Memoria.uy MVP Setup"
echo "======================="
echo ""

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Please install it first:"
    echo "   curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

echo "✅ Poetry found: $(poetry --version)"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env from template..."
    cp .env.example.mvp .env
    echo "✅ Created .env (customize if needed)"
else
    echo "✅ .env already exists"
fi
echo ""

# Install dependencies
echo "📦 Installing Python dependencies..."
poetry install --no-interaction
echo "✅ Dependencies installed"
echo ""

# Run migrations
echo "🗄️  Setting up database..."
poetry run python manage.py migrate --no-input
echo "✅ Database ready"
echo ""

# Check if superuser exists
USER_COUNT=$(poetry run python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(is_superuser=True).count())" 2>&1 | tail -1)

if [ "$USER_COUNT" = "0" ]; then
    echo "👤 Creating superuser..."
    echo ""
    echo "Enter admin credentials:"
    poetry run python manage.py createsuperuser
    echo ""
else
    echo "✅ Superuser already exists"
fi
echo ""

# Install Tailwind (optional, for CSS changes)
echo "🎨 Installing Tailwind CSS..."
poetry run python manage.py tailwind install --no-input || echo "⚠️  Tailwind install failed (optional, can skip)"
echo ""

# Build Tailwind CSS
echo "🎨 Building Tailwind CSS..."
poetry run python manage.py tailwind build --no-input || echo "⚠️  Tailwind build failed (optional, can skip)"
poetry run python manage.py collectstatic --no-input --clear
echo ""

echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "   1. Review .env file and customize if needed"
echo "   2. Start the server:"
echo "      poetry run python manage.py runserver"
echo ""
echo "   3. Visit: http://localhost:8000"
echo "   4. Admin: http://localhost:8000/admin"
echo ""
echo "📚 For development with live CSS updates:"
echo "   Terminal 1: poetry run python manage.py runserver"
echo "   Terminal 2: poetry run python manage.py tailwind start"
echo ""
