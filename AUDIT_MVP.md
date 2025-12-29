# Codebase Audit - MVP Cleanup (December 2025)

## Current State ✅

**Environment:** Working locally with SQLite
**Users:** 1 existing user in database
**Django:** 5.1.7 - Working
**Dependencies:** All installed via Poetry
**Branch:** `mvp-2025` (created)

---

## What's Working 🟢

### Core Django App
- ✅ **Django settings** - Configured for both SQLite (dev) and Postgres (prod)
- ✅ **Models** - Noticia, Voto, Entidad, NoticiaEntidad all defined
- ✅ **Views** - NewsTimelineView, VoteView, NoticiaCreateView working
- ✅ **HTMX integration** - Partial updates for voting, timeline filtering
- ✅ **Tailwind CSS** - Setup via django-tailwind (theme app)
- ✅ **Authentication** - django-allauth configured, 1 user exists
- ✅ **Templates** - Complete template structure (base, timeline, partials)

### What Users Can Do (Currently)
1. ✅ Submit news URL
2. ✅ Vote: Good / Bad / Neutral
3. ✅ View timeline of all news
4. ✅ Filter by: My votes, Majority opinion
5. ✅ Filter by entity mentions
6. ✅ See vote counts per article

---

## What's Broken/Slow 🔴

### 1. Archiving Workflow (BLOCKING)
**Files:** `core/models.py:83-118`, `core/archive_ph.py`, `core/archive_org.py`

**Problem:**
- `noticia.find_archived()` called synchronously in view (`core/views.py:206`)
- Can timeout for 30+ seconds
- Blocks user submission
- Supabase DB no longer accessible (lost access)

**Impact:** Bad UX - user waits 30 seconds for submission

**MVP Fix:** Remove archiving entirely for now
```python
# In NoticiaCreateView.form_valid()
# OLD:
noticia.find_archived()  # ❌ Blocks for 30s

# NEW (MVP):
# Just save URL and meta, no archiving yet  # ✅
noticia.update_title_image_from_original_url()
```

### 2. LLM Enrichment (SLOW, COSTS MONEY)
**Files:** `core/tasks.py:58-112`, `core/parse.py`

**Problem:**
- Celery tasks `enrich_markdown` and `enrich_content` use LiteLLM
- Costs ~$0.001 per article
- Requires Redis + Celery worker running
- Not essential for MVP

**Impact:** Adds complexity, costs, and infrastructure requirements

**MVP Fix:** Comment out LLM enrichment tasks
```python
# In core/models.py find_archived()
# OLD:
if not self.markdown:
    enrich_markdown.delay(self.id, html)  # ❌

# NEW (MVP):
# Skip LLM for now, just use meta tags  # ✅
```

### 3. Celery Dependency (INFRASTRUCTURE OVERHEAD)
**Files:** `memoria/celery.py`, `docker-compose.yml`

**Problem:**
- Requires Redis running
- Requires celery_worker container
- Not needed if we remove async tasks

**Impact:** Harder to run locally

**MVP Fix:** Make Celery optional
- Keep code, but don't require it for basic voting
- Only needed if we re-enable archiving/LLM later

### 4. Proxy System (UNRELIABLE)
**Files:** `core/url_requests.py:266-395`

**Problem:**
- Fetches free proxies from public lists
- 95%+ are blacklisted/broken
- Adds latency and failure rate

**Impact:** Makes archiving even slower/more broken

**MVP Fix:** Remove proxy usage for now
```python
# In parse_from_meta_tags()
response = get(url, headers=headers,
               rotate_user_agent=True,
               retry_on_failure=True)
# Don't use proxies: use_proxy=False (default)
```

---

## MVP Cleanup Plan 🧹

### Phase 1: Remove Blocking Code (Today)

#### 1.1 Simplify Noticia Model
**File:** `core/models.py`

**Remove/Comment:**
- `archivo_url`, `archivo_fecha`, `archivo_titulo`, `archivo_imagen` (archive fields)
- `markdown` field (LLM-generated)
- `titulo`, `fuente`, `categoria`, `resumen`, `fecha_noticia` (LLM-extracted)
- Keep only: `enlace`, `meta_titulo`, `meta_imagen`, `meta_description`, `fecha_agregado`, `agregado_por`

**Keep:**
- `update_title_image_from_original_url()` - Fast, just reads meta tags
- Remove: `find_archived()`, `update_title_image_from_archive()`

#### 1.2 Simplify NoticiaCreateView
**File:** `core/views.py:173-226`

**Changes:**
```python
def form_valid(self, form):
    enlace = form.cleaned_data.get('enlace')
    vote = form.cleaned_data.get('opinion')

    # Get or create noticia
    noticia, created = Noticia.objects.get_or_create(
        enlace=enlace,
        defaults={
            'agregado_por': self.request.user,
        }
    )

    # Fetch meta tags (fast, sync)
    if created or not noticia.meta_titulo:
        noticia.update_title_image_from_original_url()

    # Save vote
    Voto.objects.update_or_create(
        usuario=self.request.user,
        noticia=noticia,
        defaults={'opinion': vote}
    )

    # HTMX response
    # ... rest stays the same ...
```

#### 1.3 Comment Out Celery Tasks
**File:** `core/tasks.py`

**Action:** Add `# MVP: Disabled for now` comments to:
- `enrich_markdown()`
- `enrich_content()`
- `find_archived()`
- `save_to_archive_org()`
- `refresh_proxy_list()`

**Keep:** `task_lock()` decorator (useful for future)

#### 1.4 Update Templates
**File:** `core/templates/noticias/timeline_item.html`

**Remove:**
- Archive URL display
- LLM-generated summary display
- "Refresh" button (admin only, triggers archiving)

**Keep:**
- Meta title/image display
- Vote buttons
- Vote count display
- Entity filtering (if entities exist)

### Phase 2: Database Migration

#### 2.1 Create New Migrations
```bash
# Generate migration to remove fields
poetry run python manage.py makemigrations core

# This will create a migration that drops:
# - archivo_url, archivo_fecha, archivo_titulo, archivo_imagen
# - markdown
# - titulo, fuente, categoria, resumen, fecha_noticia
```

#### 2.2 Apply Migrations
```bash
poetry run python manage.py migrate
```

**Note:** Existing data in those fields will be lost. Backup `db.sqlite3` first if needed.

### Phase 3: Clean .env

**Create:** `.env.mvp` (clean starting point)
```bash
# Django
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True

# Database (SQLite by default, no config needed)

# Optional: Redis for future Celery tasks
# REDIS_URL=redis://localhost:6379/0

# Optional: LLM APIs (for Phase 3 re-enable)
# OPENAI_API_KEY=
# OPENROUTER_API_KEY=
```

### Phase 4: Update Documentation

#### 4.1 Update CLAUDE.md
Remove references to:
- Archiving workflow
- LLM enrichment
- Celery tasks

Add:
- "MVP: Simple voting only"
- "No archiving or LLM (for now)"

#### 4.2 Update README.md
Simplify development setup:
1. Install Poetry
2. `poetry install`
3. `poetry run python manage.py migrate`
4. `poetry run python manage.py createsuperuser`
5. `poetry run python manage.py runserver`

No need for:
- Redis setup
- Celery worker
- Archive API keys

---

## Files to Modify

### Critical (Must Change for MVP)
1. ✏️ `core/models.py` - Remove archive/LLM fields
2. ✏️ `core/views.py` - Simplify NoticiaCreateView
3. ✏️ `core/tasks.py` - Comment out all tasks
4. ✏️ `core/templates/noticias/timeline_item.html` - Remove archive/LLM UI
5. ✏️ `.env` - Simplify to essentials

### Nice to Have (Can Do Later)
6. 📝 `CLAUDE.md` - Update architecture notes
7. 📝 `README.md` - Simplify setup instructions
8. 🗑️ `core/archive_ph.py` - Can delete eventually
9. 🗑️ `core/archive_org.py` - Can delete eventually
10. 🗑️ `core/url_requests.py` - Can simplify (remove proxy code)

### Keep As-Is (Working Fine)
- ✅ `memoria/settings.py` - Already supports SQLite fallback
- ✅ `core/forms.py` - NoticiaForm is simple
- ✅ `templates/base.html` - Base layout works
- ✅ `theme/` - Tailwind CSS setup fine
- ✅ `docker-compose.yml` - For future production use
- ✅ All test files

---

## Testing Checklist (After Cleanup)

### Must Work
- [ ] Submit URL → Shows instantly in timeline
- [ ] Vote on news → Updates immediately (HTMX)
- [ ] Filter timeline → My votes, All votes
- [ ] Meta tags load → Title + image from URL
- [ ] No errors in console
- [ ] Page loads in <1 second

### Should NOT Happen
- [ ] No 30-second waits
- [ ] No Celery errors in logs
- [ ] No "archiving in progress" messages
- [ ] No LLM API calls

---

## Estimated Time

- **Phase 1 (Remove code):** 2-3 hours
- **Phase 2 (Migrations):** 30 minutes
- **Phase 3 (Clean .env):** 15 minutes
- **Phase 4 (Docs):** 30 minutes
- **Total:** ~4 hours

---

## Next Steps After MVP Cleanup

1. ✅ Test locally - Invite 5 friends
2. 📊 Gather feedback - Is voting useful?
3. 🚀 Deploy to Render/Railway - Free tier
4. 📈 Monitor usage - Do people come back?
5. 🔧 Decide: Extension (Phase 2) or Widget (Phase 4)?

---

## Rollback Plan

If cleanup breaks something:
```bash
git checkout v2  # Back to original
git branch -D mvp-2025
```

We have a full backup in `v2` branch.

---

**Status:** Ready to start cleanup
**Next Action:** Modify `core/models.py` to remove archive/LLM fields
