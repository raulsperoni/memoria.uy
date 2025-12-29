# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Memoria.uy is a Django news aggregation and archival application. Users submit news URLs, which are archived via archive.ph, parsed using AI (LiteLLM), and enriched with metadata (title, summary, entities, sentiment). Users can vote on news and filter by entities or sentiment.

## Development Commands

### Local Development (Poetry)

```bash
# Run development server
make -f Makefile.local runserver

# Run migrations
make -f Makefile.local migrate
poetry run python manage.py migrate

# Create migrations
make -f Makefile.local makemigrations
poetry run python manage.py makemigrations

# Run tests
make -f Makefile.local test
poetry run pytest

# Run tests with coverage
make -f Makefile.local test-cov
poetry run pytest --cov=. --cov-report=html

# Run a single test file
poetry run pytest core/tests/test_models.py

# Run tests matching a pattern
poetry run pytest -k "test_archive"

# Run Celery worker (requires Redis running)
poetry run celery -A memoria worker --loglevel=info

# Tailwind CSS setup
make -f Makefile.local tailwind-install
make -f Makefile.local tailwind-start  # Watch mode for development

# Full development setup
make -f Makefile.local dev  # Runs migrations and builds Tailwind
```

### Docker Development

```bash
# Build and start all containers
docker-compose up -d --build

# Run Django commands in Docker
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py shell

# Run tests in Docker
make test
docker-compose exec web pytest

# View logs
make logs
docker-compose logs -f web

# Restart services
make restart-web
make restart-worker
```

## Architecture

### Core Data Flow

1. **URL Submission** ([core/views.py:173-226](core/views.py#L173-L226))
   - User submits URL via `NoticiaCreateView`
   - Creates `Noticia` model with original URL
   - Calls `noticia.find_archived()` to fetch archived version

2. **Archive Retrieval** ([core/models.py:83-118](core/models.py#L83-L118))
   - `find_archived()` attempts sync archive.ph snapshot retrieval
   - On `ArchiveInProgress`, schedules async retry via `find_archived` Celery task
   - On `ArchiveNotFound`, triggers `save_to_archive_org` Celery task

3. **Content Enrichment Pipeline** (Celery tasks in [core/tasks.py](core/tasks.py))
   - `enrich_markdown`: Parses HTML to Markdown using LiteLLM (Gemini/OpenAI)
   - `enrich_content`: Extracts structured data (title, summary, entities, sentiment)
   - All tasks use `@task_lock` decorator to prevent concurrent execution on same noticia

4. **AI Parsing** ([core/parse.py](core/parse.py))
   - `parse_noticia_markdown`: HTML → Markdown (model priority: Gemini Flash Lite → O3-mini)
   - `parse_noticia`: Markdown → Structured JSON (Pydantic `Articulo` model)
   - Model fallback system with priority order

5. **Archive Services**
   - `archive_ph.py`: Primary archive service (archive.ph)
   - `archive_org.py`: Fallback (Internet Archive)
   - Custom exceptions: `ArchiveInProgress`, `ArchiveNotFound`

### Key Models

- **Noticia** ([core/models.py:13-119](core/models.py#L13-L119))
  - Stores original URL (`enlace`), archive URL (`archivo_url`), metadata, and parsed content
  - Properties: `mostrar_titulo`, `mostrar_imagen`, `mostrar_fecha` (fallback chains)

- **Voto**: User opinion on news (buena/mala/neutral)
- **Entidad**: Named entities (persona/organizacion/lugar/otro)
- **NoticiaEntidad**: Links news to entities with sentiment (positivo/negativo/neutral)

### Request Handling

- Uses `url_requests.py` with proxy rotation and retry logic
- Proxy list can be refreshed via `refresh_proxy_list` Celery task

### Frontend

- HTMX-based UI for dynamic updates without full page reloads
- Tailwind CSS in `theme/` app
- News filtering by user votes, majority opinion, or entities ([core/views.py:71-126](core/views.py#L71-L126))

## Important Patterns

### Task Locking
All Celery tasks use `@task_lock(timeout=...)` decorator to prevent duplicate execution. Lock keys include task name and arguments.

### Model Fallback in AI Parsing
Both markdown and JSON parsing have fallback models defined in `MODELS_PRIORITY_MD` and `MODELS_PRIORITY_JSON`. If primary model fails, automatically tries next priority.

### Archive Workflow
- First attempt: Synchronous archive.ph lookup in view
- If in progress: Async Celery retry (3 attempts, 3min intervals)
- If not found: Attempt to save to archive.org, then retry retrieval

### Testing
- Uses pytest with pytest-django
- Fixtures defined in `conftest.py` (root and per-app)
- Tests in `core/tests/`: `test_models.py`, `test_views.py`, `test_basic.py`
- Coverage configured in `.coveragerc` and `pytest.ini`

## Environment Configuration

- Database: SQLite (dev) or Supabase/Postgres (production via `SUPABASE_DATABASE_URL`)
- Celery: Redis broker (default: `redis://redis:6379/0`)
- LiteLLM: Requires OpenRouter API keys for AI models
- Language: Spanish (es-uy), Timezone: America/Montevideo

## Deployment

- Docker-based deployment via docker-compose.yml
- Nginx reverse proxy (config in `nginx/conf.d`)
- Gunicorn WSGI server
- Services: web, celery_worker, redis, nginx
- Health check endpoint: `/health/`
