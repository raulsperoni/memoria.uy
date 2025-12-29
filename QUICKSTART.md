# Memoria.uy - Quick Start Guide

## 🚀 Get Running in 5 Minutes

### Prerequisites
- Python 3.10+ installed
- Poetry installed ([install guide](https://python-poetry.org/docs/#installation))

### One-Command Setup
```bash
./setup-mvp.sh
```

This will:
1. Install all dependencies
2. Setup SQLite database
3. Run migrations
4. Create superuser (if needed)
5. Build Tailwind CSS
6. Collect static files

### Manual Setup (if script fails)

```bash
# 1. Install dependencies
poetry install

# 2. Create .env file
cp .env.example.mvp .env
# Edit .env if needed (defaults are fine for local dev)

# 3. Run migrations
poetry run python manage.py migrate

# 4. Create admin user
poetry run python manage.py createsuperuser

# 5. Build CSS
poetry run python manage.py tailwind install
poetry run python manage.py tailwind build
poetry run python manage.py collectstatic --no-input

# 6. Run server
poetry run python manage.py runserver
```

### Access the App

- **Main site:** http://localhost:8000
- **Admin panel:** http://localhost:8000/admin
- **Login:** Use the superuser credentials you created

---

## 📝 What Works Right Now (MVP)

### Current Features ✅
1. **Submit news URLs** - Paste any news article URL
2. **Vote:** Good / Bad / Neutral - Share your opinion
3. **See vote counts** - How many people agree/disagree
4. **Filter timeline:**
   - My votes
   - Majority good/bad news
   - By entity mentions
5. **Meta tag extraction** - Auto-fetch title & image from URL

### What's NOT Included (Yet)
- ❌ Archiving (removed for MVP - was too slow)
- ❌ LLM enrichment (removed for MVP - costs money)
- ❌ Entity extraction (requires LLM)
- ❌ Clustering/visualization (needs more users)

These will be added back in phases (see [ROADMAP_2025.md](ROADMAP_2025.md))

---

## 🛠️ Development Workflow

### Running the Server

**Basic (no live CSS updates):**
```bash
poetry run python manage.py runserver
```

**With live Tailwind CSS updates (2 terminals):**
```bash
# Terminal 1: Django server
poetry run python manage.py runserver

# Terminal 2: Tailwind watcher
poetry run python manage.py tailwind start
```

**With Make (shortcut):**
```bash
make -f Makefile.local runserver  # Django only
make -f Makefile.local tailwind-start  # Tailwind watcher
```

### Running Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=. --cov-report=html
open htmlcov/index.html

# Single test file
poetry run pytest core/tests/test_models.py

# Specific test
poetry run pytest -k "test_vote"
```

### Database Commands

```bash
# Make migrations after model changes
poetry run python manage.py makemigrations

# Apply migrations
poetry run python manage.py migrate

# Django shell
poetry run python manage.py shell

# Create another admin user
poetry run python manage.py createsuperuser
```

### CSS/Static Files

```bash
# Rebuild Tailwind CSS
poetry run python manage.py tailwind build

# Collect static files (for production)
poetry run python manage.py collectstatic
```

---

## 📂 Project Structure

```
memoria.uy/
├── core/                      # Main Django app
│   ├── models.py             # Noticia, Voto, Entidad models
│   ├── views.py              # Timeline, voting views
│   ├── forms.py              # NoticiaForm
│   ├── templates/            # HTML templates
│   │   └── noticias/
│   │       ├── timeline.html       # Main page
│   │       ├── timeline_item.html  # Single news card
│   │       └── vote_area.html      # Vote buttons (HTMX partial)
│   ├── tests/                # pytest tests
│   └── tasks.py              # Celery tasks (disabled for MVP)
│
├── memoria/                   # Django project settings
│   ├── settings.py           # Main config
│   ├── urls.py               # URL routing
│   └── celery.py             # Celery config (optional)
│
├── theme/                     # Tailwind CSS app
│   ├── static_src/
│   │   ├── src/styles.css    # Custom Tailwind styles
│   │   └── tailwind.config.js
│   └── static/               # Compiled CSS output
│
├── templates/                 # Global templates
│   └── base.html             # Base layout
│
├── db.sqlite3                # SQLite database (gitignored)
├── .env                      # Environment variables (gitignored)
├── .env.example.mvp          # Template for .env
├── setup-mvp.sh              # Setup script
│
├── pyproject.toml            # Poetry dependencies
├── Dockerfile                # Docker build (for production)
├── docker-compose.yml        # Docker services (for production)
│
└── Documentation/
    ├── README.md             # Full project docs
    ├── QUICKSTART.md         # This file
    ├── ROADMAP_2025.md       # Future plans
    ├── ANALYSIS_2025.md      # Technical analysis
    ├── AUDIT_MVP.md          # What to clean up
    └── CLAUDE.md             # AI assistant guide
```

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'django'"
**Solution:** Activate Poetry environment
```bash
poetry install
poetry shell  # OR prefix commands with: poetry run
```

### "Error: database is locked"
**Solution:** SQLite doesn't handle concurrent writes well
- Make sure only one server is running
- For production, use Postgres (see docker-compose.yml)

### Tailwind CSS not loading
**Solution:**
```bash
# Reinstall and rebuild
poetry run python manage.py tailwind install
poetry run python manage.py tailwind build
poetry run python manage.py collectstatic --no-input
```

### "SECRET_KEY is not set"
**Solution:** Create .env file
```bash
cp .env.example.mvp .env
# Edit SECRET_KEY in .env (any random string works for dev)
```

### Port 8000 already in use
**Solution:** Kill existing server or use different port
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9

# OR run on different port
poetry run python manage.py runserver 8001
```

---

## 🎯 Next Steps After Setup

### 1. Test the Core Flow
1. Go to http://localhost:8000
2. Submit a news URL (try: https://www.bbc.com/news)
3. Vote: Good / Bad / Neutral
4. Check if it appears in timeline
5. Filter by "My votes"

### 2. Invite Friends to Test
- Share your local URL (if on same network)
- OR deploy to free hosting (Railway, Render)
- Get 5-10 people voting on real news

### 3. Read the Roadmap
- [ROADMAP_2025.md](ROADMAP_2025.md) - What's next
- Decide: Extension (paywall bypass) or Widget (distribution)?

### 4. Clean Up Code (Optional)
- [AUDIT_MVP.md](AUDIT_MVP.md) - List of code to remove
- Currently archiving/LLM code is just commented out
- Can delete it fully once MVP is validated

---

## 📚 Useful Commands Cheat Sheet

```bash
# Server
poetry run python manage.py runserver
make -f Makefile.local runserver

# Migrations
poetry run python manage.py makemigrations
poetry run python manage.py migrate

# Admin
poetry run python manage.py createsuperuser

# Tests
poetry run pytest
poetry run pytest --cov=.

# CSS
poetry run python manage.py tailwind start  # Watch mode
poetry run python manage.py tailwind build  # One-time build

# Django shell
poetry run python manage.py shell

# Check for issues
poetry run python manage.py check

# List all management commands
poetry run python manage.py help
```

---

## 🐳 Docker (Optional - For Production)

```bash
# Build and start all services
docker-compose up -d --build

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# View logs
docker-compose logs -f web

# Stop all services
docker-compose down
```

---

## 🆘 Need Help?

1. **Check logs:** Look at Django server output in terminal
2. **Read audit:** [AUDIT_MVP.md](AUDIT_MVP.md) explains what's broken
3. **Read analysis:** [ANALYSIS_2025.md](ANALYSIS_2025.md) has deep technical dive
4. **Check roadmap:** [ROADMAP_2025.md](ROADMAP_2025.md) for future plans

---

**Last Updated:** December 29, 2025
**Branch:** mvp-2025
**Status:** ✅ Working locally with SQLite
