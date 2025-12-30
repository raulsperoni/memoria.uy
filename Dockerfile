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

# Install Tailwind dependencies
RUN cd /app/theme/static_src && npm install

# Expose port
EXPOSE 8000

# Create theme/static directory if it doesn't exist
RUN mkdir -p /app/theme/static

# Create entrypoint script
RUN echo '#!/bin/sh\n\
if [ "$1" = "web" ]; then\n\
    PORT=${PORT:-8000}\n\
    gunicorn memoria.wsgi:application --bind 0.0.0.0:$PORT\n\
elif [ "$1" = "worker" ]; then\n\
    celery -A memoria worker --loglevel=info\n\
elif [ "$1" = "beat" ]; then\n\
    celery -A memoria beat --loglevel=info\n\
else\n\
    exec "$@"\n\
fi' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]