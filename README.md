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

- **Backend**: Django 5.1, Python 3.10–3.11 (la imagen usa 3.10). Tareas periódicas con `manage.py tick`; Celery + Redis opcional
- **Frontend**: HTMX, Tailwind CSS (monocromo)
- **Ingesta**: RSS/sitemaps + Cloudflare Browser Rendering + trafilatura; snapshots en R2
- **IA**: Claude Haiku 5.5 vía OpenRouter (historias), Jev (decisiones tipadas), Workers AI bge-m3 (embeddings)
- **Math**: NumPy, SciPy, scikit-learn (clustering estilo Polis)
- **DB**: SQLite (dev), PostgreSQL (prod)

## Estructura

```
archivo/   # Ingesta, historias, hechos, proposiciones, notas editadas
juego/     # Juego diario y burbujas
core/      # Entidades, motor de clustering, tick, resumen para staff
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

# Tareas periódicas (lo que corre el cron de producción)
poetry run python manage.py tick --listar
poetry run python manage.py tick --forzar ciclo_ingesta

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

# Opcional: con REDIS_URL vuelve el modo Celery (worker + beat)
# REDIS_URL=redis://localhost:6379/0
```

## Deployment (Railway)

Dos servicios del mismo `Dockerfile` más Postgres, sin Redis:

1. **web**: `/entrypoint.sh web` (migra, crea la tabla de cache, gunicorn). Healthcheck `/health/`. Necesita `PORT=8000`.
2. **cron**: `/entrypoint.sh tick`, cron `*/15 * * * *`, restart `NEVER`.

Ver [CLAUDE.md](CLAUDE.md#deployment) y [archivo/README.md](archivo/README.md) para las variables.

## Licencia

Open source. Uso libre, crédito apreciado.
