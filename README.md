<p align="center">
  <img src="memoria-uy-brand/logo-256.png" alt="memoria.uy" width="128">
</p>

# Memoria.uy

Agregador de noticias uruguayo con votación anónima y clustering de opinión.

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

- **Backend**: Django 5.1, Python 3.11, Celery + Redis
- **Frontend**: HTMX, Tailwind CSS, Plotly.js
- **AI**: LiteLLM (Gemini Flash, O3-mini fallback)
- **Math**: NumPy, SciPy, scikit-learn
- **DB**: SQLite (dev), PostgreSQL (prod)

## Estructura

```
core/                 # App principal Django
├── models.py         # Noticia, Voto, Entidad, Clustering
├── views.py          # Timeline, votación, filtros
├── api_views.py      # API para extensión
├── tasks.py          # Celery (enriquecimiento, clustering)
├── parse.py          # LLM parsing
├── clustering/       # Motor matemático Polis-style
│   ├── matrix_builder.py
│   ├── pca.py
│   ├── kmeans.py
│   ├── hierarchical.py
│   └── metrics.py
└── templates/

browser-extension/    # Chrome/Firefox Manifest V3
memoria/              # Django settings
theme/                # Tailwind CSS
memoria-uy-brand/     # Assets de marca
docs/                 # Documentación científica
```

## Features

### Signup Prompt (Anónimo → Registrado)

El sistema invita a crear cuenta después del 3er voto o al agotar noticias disponibles.

**Beneficios ofrecidos:**
- Guardar votos entre dispositivos (claim de votos anónimos)
- Alias opcional en mapa de clustering
- Email semanal con noticias relevantes

**Modelo:** `UserProfile` (alias, show_alias_on_map, weekly_email_enabled)  
**Form:** `CustomSignupForm` extiende allauth con campo alias  
**Triggers:** 3er voto + estado vacío ("votaste todas las noticias")

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

# Clustering manual
poetry run python manage.py cluster_voters --days 30 --min-voters 50

# Tailwind
poetry run python manage.py tailwind start
```

## Docker

```bash
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

## Extensión de navegador

**Chrome:**
1. `chrome://extensions/` → Developer mode
2. Load unpacked → `browser-extension/`

**Firefox:**
1. `about:debugging#/runtime/this-firefox`
2. Load Temporary Add-on → `browser-extension/manifest.json`

## Variables de entorno

```bash
SECRET_KEY=...
DEBUG=False
DATABASE_URL=postgresql://...

# LLM
GOOGLE_API_KEY=...
OPENROUTER_API_KEY=...  # fallback

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
