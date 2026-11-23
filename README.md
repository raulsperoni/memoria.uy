<p align="center">
  <img src="memoria-uy-brand/logo-256.png" alt="memoria.uy" width="128">
</p>

# Memoria.uy

Archivo de noticias uruguayas con fuentes, juego diario «¿Qué piensa Uruguay?» y burbujas de opinión.

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [VISION.md](VISION.md) | Visión de producto, motivación, estado actual |
| [docs/SCIENTIFIC.md](docs/SCIENTIFIC.md) | Algoritmos, referencias científicas |
| [CLAUDE.md](CLAUDE.md) | Guía técnica para desarrollo |

## Quick Start

```bash
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver
# http://localhost:8000
```

## Stack

- **Backend**: Django 5.1, Python 3.11+, Celery + Redis
- **Frontend**: HTMX, Tailwind CSS (monocromo)
- **Ingesta**: RSS/sitemaps + Cloudflare Browser Rendering + trafilatura; snapshots en R2
- **IA**: Claude Haiku 5.5 vía OpenRouter (historias), Jev (decisiones tipadas), Workers AI bge-m3 (embeddings)
- **Math**: NumPy, SciPy, scikit-learn (clustering estilo Polis)
- **DB**: SQLite (dev), PostgreSQL (prod)

## Estructura

```
archivo/   # Ingesta, historias, hechos, proposiciones, notas editadas
juego/     # Juego diario y burbujas
core/      # Usuarios, entidades, motor de clustering, emails (y sistema viejo)
memoria/   # Settings, urls, celery
theme/     # Tailwind
docs/      # Propuesta, plan, ciencia
```

## Comandos

```bash
# Desarrollo
poetry run python manage.py runserver
poetry run python manage.py makemigrations
poetry run python manage.py migrate

# Tests
poetry run pytest
poetry run pytest --cov=. --cov-report=html

# Tests de seguridad
poetry run pytest core/tests/test_security.py -v

# Celery (requiere Redis)
poetry run celery -A memoria worker --loglevel=info

# Archivo y juego
poetry run python manage.py cargar_medios
poetry run python manage.py detectar_feeds
poetry run python manage.py armar_jornada

# Tailwind
poetry run python manage.py tailwind start
```

## Docker

```bash
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

## Variables de entorno

```bash
SECRET_KEY=...
DEBUG=False
DATABASE_URL=postgresql://...

# IA y crawl (ver archivo/README.md para la lista completa)
OPENROUTER_API_KEY=...
TYPESAFE_API_KEY=...            # o la key de OpenRouter con TYPESAFE_BASE_URL
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_API_TOKEN=...
EXTRACTOR=cloudflare
SNAPSHOT_STORAGE=r2
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...

# Celery
REDIS_URL=redis://localhost:6379/0

# Re-engagement emails (optional)
ENABLE_REENGAGEMENT_EMAILS=True          # Enable re-engagement emails
REENGAGEMENT_EMAIL_HOUR=10               # Hour to send (default: 10 AM)
REENGAGEMENT_EMAIL_MINUTE=0              # Minute to send (default: 0)
REENGAGEMENT_DAYS_INACTIVE=7             # Days of inactivity to trigger email
REENGAGEMENT_MAX_EMAILS=500              # Max emails per run
REENGAGEMENT_MIN_DAYS_BETWEEN=7          # Minimum days between emails to same user
```

## Deployment (Railway)

Tres servicios requeridos:

1. **Web**: `/entrypoint.sh web`
2. **Worker**: `/entrypoint.sh worker`
3. **Beat**: `/entrypoint.sh beat`

Todos comparten `REDIS_URL`.

## Licencia

Open source. Uso libre, crédito apreciado.
