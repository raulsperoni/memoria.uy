# Development Guide

Everything you need to work on Memoria.uy.

---

## Quick Test (5 Minutes)

```bash
poetry run python manage.py runserver
# Visit http://localhost:8000
# Submit a URL (try https://www.bbc.com/news)
# Vote without login
# Check "My Votes" filter
```

**Should work:** Anonymous voting, instant submission, persistent sessions
**Won't work:** Archive links, AI summaries (removed in MVP)

---

## Architecture

### Anonymous-First Authentication

**Why:** Login requirements kill growth. People won't sign up to "test" an app.

**How it works:**
1. User visits → Session cookie created automatically
2. User votes → Vote tied to `session_key` (not user account)
3. User signs up (optional) → Anonymous votes migrate to account

**Models:**
```python
class Voto(models.Model):
    usuario = ForeignKey(User, null=True)      # Authenticated
    session_key = CharField(null=True)          # Anonymous
    noticia = ForeignKey(Noticia)
    opinion = CharField()  # buena/mala/neutral

    # One vote per user OR session per article
    constraints = [
        UniqueConstraint(fields=['usuario', 'noticia']),
        UniqueConstraint(fields=['session_key', 'noticia'])
    ]
```

**Views:**
```python
def get_voter_identifier(request):
    if request.user.is_authenticated:
        return {'usuario': request.user}
    else:
        if not request.session.session_key:
            request.session.create()
        return {'session_key': request.session.session_key}
```

**Templates:** Check both `voter_user` and `voter_session` to display votes.

### What We Removed (MVP Cleanup)

**Removed fields (10 total):**
- Archive: `archivo_url`, `archivo_fecha`, `archivo_titulo`, `archivo_imagen`
- LLM: `markdown`, `titulo`, `fuente`, `categoria`, `resumen`, `fecha_noticia`

**Why:** Archiving took 30+ seconds (blocking), LLM costs money, both unnecessary for MVP.

**Kept fields:**
- `enlace` (URL)
- `meta_titulo`, `meta_imagen`, `meta_descripcion` (fast og: tag extraction)
- `fecha_agregado` (submission date)
- `agregado_por` (optional - who submitted)

**Performance gain:** Submissions now < 1 second (was 30+ seconds).

---

## Roadmap

### Phase 1: MVP (DONE) ✅
- Anonymous voting via sessions
- Meta tag extraction (title, image)
- Vote filtering (my votes, majority)
- No login required

**Status:** Deployed on `mvp-2025` branch

### Phase 2: Browser Extension (2-3 weeks)
**Goal:** Bypass paywalls by capturing client-side

**How:**
- Chrome/Firefox extension (Manifest V3)
- User reads article → Clicks extension → Votes + sends HTML
- Server receives full HTML (bypasses paywall)
- Future: LLM enrichment from client-captured HTML

**Why:** News sites block VPS IPs. Extension uses user's own browser session.

### Phase 3: Embeddable Widgets (3-4 weeks)
**Goal:** Partner with news outlets for distribution

**How:**
```html
<!-- News outlet embeds this -->
<div class="memoria-widget" data-url="current-page"></div>
<script src="https://memoria.uy/embed.js"></script>
```

**Benefits:** News sites get engagement widget, we get traffic.

### Phase 4: Clustering (2-3 months)
**Goal:** Visualize polarization patterns

**Requires:** 100+ active users (50+ votes each)

**Features:**
- PCA/t-SNE clustering of voting patterns
- "You are here" on cluster map
- Consensus vs divisive metrics
- Entity sentiment tracking

---

## Database Schema

### Core Models

**Noticia** (News Article)
```
enlace (URL, unique)
meta_titulo (og:title)
meta_imagen (og:image)
meta_descripcion (og:description)
fecha_agregado (timestamp)
agregado_por (User, nullable)
```

**Voto** (Vote)
```
usuario (User, nullable)         # Authenticated vote
session_key (char, nullable)     # Anonymous vote
noticia (Noticia)
opinion (buena/mala/neutral)
fecha_voto (timestamp)
```

**Entidad** (Named Entity - unused in MVP)
```
nombre (str)
tipo (persona/organizacion/lugar/otro)
```

**NoticiaEntidad** (Entity Link - unused in MVP)
```
noticia (Noticia)
entidad (Entidad)
sentimiento (positivo/negativo/neutral)
```

### Migrations

Latest: `0008_mvp_cleanup_anonymous_auth.py`

**Changes:**
- Removed 10 archive/LLM fields
- Added `session_key` to Voto
- Made `usuario` nullable in Voto
- Added UniqueConstraints for session/user votes

**To rollback:**
```bash
poetry run python manage.py migrate core 0007
```

---

## Testing Strategy

### Unit Tests
```bash
poetry run pytest core/tests/
```

**Key test files:**
- `test_models.py` - Noticia, Voto, constraints
- `test_views.py` - Anonymous voting, filtering
- `test_basic.py` - Smoke tests

### Manual Testing Checklist
1. [ ] Anonymous vote on news
2. [ ] Session persists across tabs
3. [ ] "My Votes" filter works for anonymous
4. [ ] Authenticated user can vote
5. [ ] Vote counts update in real-time (HTMX)
6. [ ] Submission < 1 second
7. [ ] No errors in console

### Performance Targets
- Page load: < 1s
- Submit URL: < 1s
- Vote: < 200ms
- Filter: < 500ms

---

## Deployment

### Local (SQLite)
```bash
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver
```

### Docker (Postgres)
```bash
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

**Services:**
- `web` - Django + Gunicorn
- `db` - Postgres 16
- `nginx` - Reverse proxy
- `celery_worker` - Disabled for MVP (no background tasks)

### Free Hosting

**Render.com:**
1. New Web Service → Connect repo
2. Build: `poetry install`
3. Start: `gunicorn memoria.wsgi`
4. Add Postgres database
5. Set env: `SECRET_KEY`, `DATABASE_URL`

**Railway.app:**
1. New Project → Deploy from GitHub
2. Auto-detects Django
3. Add Postgres plugin
4. Set env vars
5. Run migrations via CLI

---

## Environment Variables

**Required:**
```bash
SECRET_KEY=your-secret-key
DEBUG=False  # True for local dev
```

**Optional (MVP):**
```bash
# Database (defaults to SQLite)
DATABASE_URL=postgresql://user:pass@host:5432/db

# For future phases
GOOGLE_API_KEY=...        # Gemini (Phase 3: LLM)
OPENROUTER_API_KEY=...    # Fallback models
REDIS_URL=...             # If re-enabling Celery
```

---

## Code Organization

### Models (`core/models.py`)
- **Noticia:** News article (URL + metadata)
- **Voto:** User/session vote
- **Entidad:** Named entities (unused)
- **NoticiaEntidad:** Entity links (unused)

### Views (`core/views.py`)
- **NewsTimelineView:** Main list + filtering
- **VoteView:** Handle votes (HTMX partial)
- **NoticiaCreateView:** Submit URL + vote
- **RefreshNoticiaView:** Admin only (re-fetch metadata)
- **DeleteNoticiaView:** Admin only

### Forms (`core/forms.py`)
- **NoticiaForm:** URL + opinion input

### Templates
```
templates/base.html                  # Layout
core/templates/noticias/
  timeline.html                      # Main page
  timeline_fragment.html             # Form + items (HTMX)
  timeline_items.html                # Item list (HTMX)
  timeline_item.html                 # Single card
  vote_area.html                     # Vote buttons (HTMX)
```

---

## Future Enhancements

### Vote Migration on Signup
**Not implemented yet.** When user signs up, migrate anonymous votes:

```python
from allauth.account.signals import user_signed_up

@receiver(user_signed_up)
def claim_anonymous_votes(sender, request, user, **kwargs):
    if request.session.session_key:
        Voto.objects.filter(
            session_key=request.session.session_key,
            usuario__isnull=True
        ).update(usuario=user, session_key=None)
```

### LLM Enrichment (Phase 3)
**Bring back with latest models (Dec 2025):**

```python
# Use Gemini 2.0 Flash (free tier: 15 RPM)
MODELS = {
    "markdown": "gemini/gemini-2.0-flash-exp",
    "json": "gemini/gemini-2.0-flash-exp",
}

# Cost: ~$0 (free tier) or $0.0001/article (paid)
```

**Only enable after:**
1. Extension built (client-side HTML capture)
2. 50+ daily users (worth the cost)

### Entity Extraction
**Use GLiNER2 (free, local) instead of LLM:**

```python
from gliner import GLiNER

model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
entities = model.predict_entities(
    text,
    labels=["persona", "organizacion", "lugar"]
)
```

**Cost:** $0 (runs on server)
**Quality:** Good for Spanish

---

## Troubleshooting

### "Login Required" Error
**Problem:** Old templates still check `user.is_authenticated`
**Fix:** Check for both `user.is_authenticated` OR `voter_session` in templates

### Slow Submissions
**Problem:** Still calling archive/LLM somewhere
**Fix:** Search codebase for `find_archived()`, `enrich_` - should be removed

### Session Not Persisting
**Problem:** Cookie settings
**Fix:** Check `SESSION_COOKIE_AGE` in settings (default: 1209600 = 2 weeks)

### Vote Counts Wrong
**Problem:** Query not filtering correctly
**Fix:** Check `get_queryset()` filters - should handle both user + session

---

## Contributing Guidelines

1. **Branch naming:** `feature/description` or `fix/description`
2. **Commits:** Descriptive (no "fix", "update", "changes")
3. **Tests:** Add for new features
4. **No tracking:** Never add analytics, tracking pixels, etc.
5. **Privacy first:** Any data collection needs explicit consent

---

## Resources

**Django + HTMX:**
- https://django-htmx.readthedocs.io/

**Tailwind CSS:**
- https://django-tailwind.readthedocs.io/

**Session Auth:**
- https://docs.djangoproject.com/en/stable/topics/http/sessions/

**Polis (inspiration):**
- https://pol.is

---

**Last Updated:** December 29, 2025
**Branch:** mvp-2025
**Status:** MVP complete, ready to ship
