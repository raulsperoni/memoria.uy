<p align="center">
  <img src="memoria-uy-brand/logo-256.png" alt="memoria.uy" width="128">
</p>

# Memoria.uy

**Votá noticias. Descubrí patrones. Salí de tu burbuja.**

Anonymous news sentiment aggregator for Uruguayan media. Vote on articles (buena/mala/neutral), discover voting patterns, and explore opinion clusters without login or tracking.

## Quick Start

```bash
# Install dependencies
poetry install

# Run migrations
poetry run python manage.py migrate

# Start development server
poetry run python manage.py runserver

# Visit: http://localhost:8000
```

Start voting immediately - no login required!

## What It Does

1. **Vote anonymously** - Buena 😊 / Mala 😞 / Neutral 😐 (no account needed)
2. **Submit via extension** - Browser extension captures paywalled articles
3. **See patterns** - Which news divides Uruguay? Which unites us?
4. **Find your burbuja** - Discover opinion clusters and your position

**Privacy-first:** Session-based voting, no tracking, open source.

## Features

### Core Features
- ✅ **Anonymous voting** via session cookies
- ✅ **Browser extension** bypasses paywalls with client-side capture
- ✅ **LLM enrichment** (Gemini/O3-mini) extracts entities and sentiment
- ✅ **Vote filtering** (my votes, majority opinion, burbuja consensus)
- ✅ **Polis-inspired clustering** groups voters by opinion patterns
- ✅ **HTMX UI** for fast, partial page updates

### Clustering & Visualization
- ✅ **Sparsity-aware PCA** handles incomplete voting matrices
- ✅ **Hierarchical grouping** (base → group → subgroup clusters)
- ✅ **Interactive visualization** with Plotly.js scatter plots
- ✅ **Consensus metrics** show within-cluster agreement
- ✅ **Burbuja mode selector** control your information diet

## Tech Stack

- **Backend:** Django 5.1.7, Python 3.11
- **Tasks:** Celery 5.4.0 + Redis
- **Math:** NumPy, SciPy, scikit-learn (clustering)
- **LLM:** LiteLLM (Gemini Flash Lite, O3-mini fallback)
- **Frontend:** HTMX, Tailwind CSS, Plotly.js
- **Database:** SQLite (dev), PostgreSQL (prod)
- **Extension:** Chrome/Firefox Manifest V3

## Development Commands

```bash
# Run server
poetry run python manage.py runserver

# Run migrations
poetry run python manage.py makemigrations
poetry run python manage.py migrate

# Run tests
poetry run pytest
poetry run pytest --cov=. --cov-report=html

# Start Celery worker (for LLM enrichment)
poetry run celery -A memoria worker --loglevel=info

# Manual clustering
poetry run python manage.py cluster_voters --days 30 --min-voters 50

# Tailwind CSS (watch mode)
poetry run python manage.py tailwind start
```

## Browser Extension

Install locally for development:

**Chrome:**
1. Go to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" → Select `browser-extension/` folder

**Firefox:**
1. Go to `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on" → Select `browser-extension/manifest.json`

Extension captures full HTML from user's browser session, bypassing paywalls and IP blocks.

## Project Structure

```
core/              # Main Django app
├── models.py      # Noticia, Voto, Entidad, Clustering models
├── views.py       # Timeline, voting, filtering
├── api_views.py   # Extension API endpoints
├── tasks.py       # Celery tasks (LLM enrichment, clustering)
├── parse.py       # LLM parsing (HTML→Markdown, entities)
├── clustering/    # Polis-inspired math engine
│   ├── matrix_builder.py  # Vote matrix construction
│   ├── pca.py             # Sparsity-aware PCA
│   ├── kmeans.py          # Weighted k-means
│   ├── hierarchical.py    # Silhouette-based grouping
│   └── metrics.py         # Consensus & similarity
└── templates/
    ├── noticias/         # Timeline, detail pages
    └── clustering/       # Visualization, stats

browser-extension/  # Chrome/Firefox extension
memoria/           # Django settings
theme/             # Tailwind CSS
```

## Deployment

### Docker (Production)

```bash
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

Services: Django + PostgreSQL + Nginx + Celery + Redis

### Environment Variables

```bash
# Required
SECRET_KEY=your-secret-key
DEBUG=False
DATABASE_URL=postgresql://user:pass@host:5432/db

# LLM (required for enrichment)
GOOGLE_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key  # optional fallback

# Redis (required for Celery)
REDIS_URL=redis://localhost:6379/0
```

## How It Works

### Data Flow

```
1. User votes via extension on paywalled article
   └─→ Extension captures full HTML (client-side)

2. POST /api/submit-from-extension/
   └─→ Creates Noticia + Voto
   └─→ Triggers Celery pipeline

3. Celery Phase 1: HTML → Markdown (Gemini Flash Lite)
   └─→ Removes ads, scripts, navigation
   └─→ Preserves article structure

4. Celery Phase 2: Markdown → Entities (Gemini/O3-mini)
   └─→ Extracts personas, organizaciones, lugares
   └─→ Analyzes sentiment per entity (positivo/negativo/neutral)

5. Periodic clustering (30-day window)
   └─→ Build sparse vote matrix (voters × noticias)
   └─→ Sparsity-aware PCA → 2D projection
   └─→ K-means (k≈100) → Hierarchical grouping
   └─→ Save clusters, projections, consensus metrics

6. UI displays:
   └─→ Timeline with burbuja badges
   └─→ Entity tags with sentiment
   └─→ Interactive cluster visualization
   └─→ Burbuja mode selector (mi burbuja / todo / otras burbujas)
```

### Session Management

Three types of user identification:
1. **Authenticated users** (optional, via django-allauth)
2. **Extension sessions** (cross-platform, synced via cookie + localStorage)
3. **Django sessions** (web-only fallback)

Priority: Authenticated → Extension → Django session

## Cost & Performance

**LLM Enrichment:**
- Per article: ~$0.0002 (2 LLM calls)
- 100 articles/day: ~$0.60/month
- Gemini free tier: 15 RPM (600 articles/hour)

**Clustering:**
- 5-1,000 voters: 0.3-5 seconds
- 10,000-100,000 voters: <10 seconds (optimized)
- Cache: 1 hour for clustering API

## Contributing

This is a personal project exploring collective sentiment analysis for Uruguayan news. Feedback welcome!

**Key principle:** Privacy-first. No tracking, no PII collection, full transparency.

## Documentation

- [CLAUDE.md](CLAUDE.md) - Complete technical reference for development
- [browser-extension/README.md](browser-extension/README.md) - Extension-specific docs
- [POLIS_CLUSTERING_PLAN.md](POLIS_CLUSTERING_PLAN.md) - Clustering implementation plan

## License

Open source. Use freely, credit appreciated.
