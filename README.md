# Memoria.uy

**Anonymous-first news sentiment aggregator.** Vote on news articles (good/bad/neutral) without login, explore polarization patterns through collective opinions.

## 🚀 Quick Start (2 Minutes)

```bash
# One-command setup
./setup-mvp.sh

# OR manual:
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver

# Visit: http://localhost:8000
```

No login required - start voting immediately!

---

## What It Does

1. **Submit news URLs** - Paste any article link
2. **Vote anonymously** - Good 😊 / Bad 😞 / Neutral 😐 (no account needed)
3. **See patterns** - Which news divides us? Which unites us?
4. **Optional signup** - Sync votes across devices later

**Privacy-first:** Session-based voting, no tracking, open source.

---

## Features (MVP)

- ✅ **Anonymous voting** via session cookies
- ✅ **Instant submissions** (< 1 second, no archiving delays)
- ✅ **Vote filtering** (my votes, majority opinion)
- ✅ **Meta tag extraction** (title, image from og: tags)
- ✅ **HTMX UI** (partial page updates)
- ❌ ~~Archiving~~ (removed - too slow)
- ❌ ~~LLM enrichment~~ (removed - for Phase 2)

---

## Development

### Prerequisites
- Python 3.10+
- Poetry ([install](https://python-poetry.org/docs/#installation))
- Node.js (for Tailwind CSS)

### Commands

```bash
# Server
poetry run python manage.py runserver
make -f Makefile.local runserver

# Migrations
poetry run python manage.py makemigrations
poetry run python manage.py migrate

# Tests
poetry run pytest
poetry run pytest --cov=.

# Tailwind CSS
poetry run python manage.py tailwind start  # Watch mode
poetry run python manage.py tailwind build

# Django shell
poetry run python manage.py shell
```

### Project Structure

```
core/              # Main app (models, views, templates)
memoria/           # Django settings
theme/             # Tailwind CSS
db.sqlite3         # Database (dev)
docker-compose.yml # Docker setup (prod)
```

---

## Deployment

### Docker (Production)

```bash
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

Services: Django + Postgres + Nginx (Redis/Celery disabled for MVP)

### Free Hosting (Render/Railway)

1. Push this repo
2. Set `SECRET_KEY` env var
3. Run migrations
4. Done!

---

## Roadmap

**Phase 1 (DONE):** Anonymous voting MVP
**Phase 2:** Browser extension (bypass paywalls)
**Phase 3:** Embeddable widgets (news site partnerships)
**Phase 4:** Clustering visualization (polarization patterns)

See [DEVELOPMENT.md](DEVELOPMENT.md) for details.

---

## Tech Stack

- Django 5.1 + HTMX + Tailwind CSS
- SQLite (dev) / Postgres (prod)
- Session-based auth (no forced login)
- Poetry for dependencies

---

## Contributing

This is a personal project exploring collective sentiment analysis. Feedback welcome!

**Key principle:** Privacy-first. No tracking, no PII collection, full transparency.

---

## License

Open source. Use freely, credit appreciated.
