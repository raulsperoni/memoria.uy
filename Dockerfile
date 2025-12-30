FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.6.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    gnupg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g rimraf

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${POETRY_HOME}/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies including dev dependencies for testing
RUN poetry install --no-interaction --no-ansi --no-root --with dev

# Copy project
COPY . .

# Install Tailwind dependencies and build CSS
RUN cd /app/theme/static_src && npm install
RUN cd /app/theme/static_src && npm run build

# Collect static files during build (with minimal env vars)
ENV SECRET_KEY=build-time-secret-key-not-for-runtime
ENV DEBUG=True
RUN python manage.py collectstatic --noinput
ENV SECRET_KEY=
ENV DEBUG=

# Expose port
EXPOSE 8000

# Create entrypoint script
RUN echo '#!/bin/sh\n\
set -e\n\
echo "Starting container with command: $1"\n\
echo "REDIS_URL: ${REDIS_URL:-not set}"\n\
echo "DATABASE_URL: ${DATABASE_URL:-not set}"\n\
\n\
if [ "$1" = "web" ]; then\n\
    echo "Starting web server..."\n\
    PORT=${PORT:-8000}\n\
    gunicorn memoria.wsgi:application --bind 0.0.0.0:$PORT --timeout 120\n\
elif [ "$1" = "worker" ]; then\n\
    echo "Starting Celery worker..."\n\
    echo "Testing Redis connection..."\n\
    python -c "import redis; r=redis.from_url(\"${REDIS_URL}\"); r.ping(); print(\"Redis OK\")" || echo "Redis connection failed!"\n\
    celery -A memoria worker --loglevel=info --concurrency=2\n\
elif [ "$1" = "beat" ]; then\n\
    echo "Starting Celery beat..."\n\
    celery -A memoria beat --loglevel=info\n\
else\n\
    exec "$@"\n\
fi' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]