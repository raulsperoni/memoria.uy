# Phase 2: LLM Enrichment - Enabled

LLM enrichment has been re-enabled for articles submitted via the browser extension!

## What Was Added

### 1. Database Changes
- **New field:** `Noticia.markdown` - Stores LLM-generated markdown from captured HTML
- **Migration:** `0010_noticia_markdown.py` (applied)

### 2. Celery Tasks

**Task 1: HTML → Markdown**
- **New task:** `enrich_from_captured_html(noticia_id)`
  - Converts captured HTML → Markdown using LLM
  - Uses `parse.parse_noticia_markdown()` function
  - Runs asynchronously after article submission
  - Protected by task lock to prevent concurrent execution
  - Chains to entity extraction when done

**Task 2: Markdown → Entities**
- **New task:** `extract_entities_from_markdown(noticia_id)`
  - Extracts entities and sentiment from markdown
  - Uses `parse.parse_noticia()` function
  - Creates Entidad and NoticiaEntidad records
  - Runs automatically after markdown generation
  - Protected by task lock to prevent duplicate processing

### 3. API Integration
- **Trigger:** Automatically called when extension submits article with HTML
- **Condition:** Only runs if `captured_html` exists and `markdown` is null
- **Location:** [core/api_views.py:107-114](core/api_views.py#L107-L114)

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│ 1. User votes via extension                            │
│    → HTML captured from browser                         │
│    → Metadata extracted (og:image, title, etc.)        │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 2. POST /api/submit-from-extension/                    │
│    → Noticia created with captured_html + metadata     │
│    → Vote created                                       │
│    → LLM enrichment triggered                           │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Celery: enrich_from_captured_html.delay()           │
│    → Background task queued                             │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 4. LLM Processing #1 (Gemini Flash Lite)               │
│    → HTML → Clean markdown                              │
│    → Removes ads, scripts, navigation                   │
│    → Preserves article structure                        │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Save markdown to Noticia                            │
│    → noticia.markdown = result                          │
│    → Triggers next phase                                │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 6. Celery: extract_entities_from_markdown.delay()      │
│    → Background task queued                             │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 7. LLM Processing #2 (Gemini/O3-mini)                  │
│    → Markdown → Structured data                         │
│    → Extract entities (personas, lugares, etc.)        │
│    → Analyze sentiment per entity                       │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 8. Save Entities to Database                           │
│    → Create Entidad records                             │
│    → Create NoticiaEntidad links with sentiment        │
│    → Ready for display in UI                            │
└─────────────────────────────────────────────────────────┘
```

## LLM Model Priority

From [core/parse.py](core/parse.py):

**Markdown Generation:**
1. **Primary:** `openrouter/google/gemini-2.0-flash-lite-001` (fast, cheap)
2. **Fallback:** `openrouter/openai/o3-mini` (more expensive, better quality)

**Cost:** ~$0.0001-0.001 per article (depending on length)

## Requirements

### 1. Celery Worker Running

The enrichment happens in background tasks, so you need Celery:

```bash
# Option 1: Local with Redis
# Start Redis
redis-server

# Start Celery worker
poetry run celery -A memoria worker --loglevel=info

# Option 2: Docker (includes Redis)
docker-compose up -d
```

### 2. LLM API Keys

Set in `.env`:

```bash
# Required for Gemini models
GOOGLE_API_KEY=your_google_api_key_here

# Optional: Fallback models via OpenRouter
OPENROUTER_API_KEY=your_openrouter_key_here
```

**Get API keys:**
- Google Gemini: https://aistudio.google.com/app/apikey
- OpenRouter: https://openrouter.ai/keys

## Testing

### Manual Test

1. **Start services:**
   ```bash
   # Terminal 1: Django
   poetry run python manage.py runserver

   # Terminal 2: Celery
   poetry run celery -A memoria worker --loglevel=info
   ```

2. **Submit article via extension:**
   - Go to any news article
   - Click extension → Vote → Submit
   - Watch Celery logs for enrichment task

3. **Check results:**
   ```bash
   poetry run python manage.py shell
   >>> from core.models import Noticia
   >>> n = Noticia.objects.last()
   >>> print(n.captured_html[:100])  # Raw HTML
   >>> print(n.markdown[:500])       # Should have markdown after ~5-30 seconds
   ```

### Expected Celery Output

```
[INFO] Triggered LLM enrichment for noticia 123
[INFO] Task enrich_from_captured_html[abc-123] received
[INFO] Converting captured HTML to markdown for noticia 123
[INFO] Successfully converted HTML to markdown for noticia 123
[INFO] Triggered entity extraction for noticia 123
[INFO] Task extract_entities_from_markdown[def-456] received
[INFO] Extracting entities from markdown for noticia 123
[INFO] Found entity: Luis Lacalle Pou (persona, positivo)
[INFO] Found entity: Banco Central (organizacion, neutral)
[INFO] Saved 2 entities for noticia 123
```

## Troubleshooting

### "No Celery worker running"

**Problem:** Task is queued but never executes

**Solution:**
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Start Celery worker
poetry run celery -A memoria worker --loglevel=info
```

### "API key not configured"

**Problem:** `AuthenticationError` or `InvalidRequestError`

**Solution:**
```bash
# Check .env file has keys
cat .env | grep API_KEY

# Add if missing
echo "GOOGLE_API_KEY=your_key_here" >> .env

# Restart server
poetry run python manage.py runserver
```

### Markdown is always null

**Problem:** Task runs but markdown not saved

**Check:**
1. Celery logs for errors
2. API key is valid
3. Captured HTML is valid (not empty)

```bash
# Test API key directly
poetry run python manage.py shell
>>> from litellm import completion
>>> response = completion(
...     model="openrouter/google/gemini-2.0-flash-lite-001",
...     messages=[{"role": "user", "content": "Say hello"}]
... )
>>> print(response.choices[0].message.content)
```

### Rate limits

**Problem:** "Rate limit exceeded" errors

**Solution:**
- Gemini free tier: 15 requests/minute
- Wait 1 minute between tests
- Or use paid tier for higher limits

## Disabling Enrichment

If you want to disable LLM enrichment (to save costs during testing):

Comment out in [core/api_views.py:107-114](core/api_views.py#L107-L114):

```python
# Trigger background task for LLM enrichment
# if noticia.captured_html and not noticia.markdown:
#     from core.tasks import enrich_from_captured_html
#     enrich_from_captured_html.delay(noticia.id)
#     logger.info(f"Triggered LLM enrichment for noticia {noticia.id}")
```

## Future: Entity Extraction

Currently markdown is generated but not used. Next steps:

1. **Extract structured data** from markdown
   - Call `parse.parse_noticia(markdown)`
   - Get: title, source, category, summary, entities, sentiment
   - Save to Noticia and NoticiaEntidad models

2. **Create second task:**
   ```python
   @shared_task
   def enrich_content_from_markdown(noticia_id):
       noticia = Noticia.objects.get(id=noticia_id)
       articulo = parse.parse_noticia(noticia.markdown)
       # Save title, resumen, entidades, etc.
   ```

3. **Chain tasks:**
   ```python
   # In enrich_from_captured_html after saving markdown:
   if markdown:
       noticia.markdown = markdown
       noticia.save()

       # Trigger next phase
       enrich_content_from_markdown.delay(noticia.id)
   ```

## Monitoring

### View Task Status

```bash
# Celery logs
poetry run celery -A memoria worker --loglevel=info

# Or in production
docker-compose logs -f celery_worker
```

### View Enrichment Stats

```bash
poetry run python manage.py shell
>>> from core.models import Noticia
>>> total = Noticia.objects.count()
>>> with_html = Noticia.objects.exclude(captured_html=None).count()
>>> with_markdown = Noticia.objects.exclude(markdown=None).count()
>>> print(f"Total: {total}, HTML: {with_html}, Markdown: {with_markdown}")
```

## Cost Estimation

**Per article (2 LLM calls):**
- **Markdown generation:** ~3000 tokens → ~$0.0001 (Gemini Flash Lite)
- **Entity extraction:** ~1000 tokens → ~$0.0001 (Gemini/O3-mini)
- **Total per article:** ~$0.0002

**Monthly (100 articles/day):**
- 3000 articles/month × 2 calls = 6000 LLM calls
- Gemini: ~$0.60/month
- O3-mini: ~$6/month (if all fallback)

**Practically free** with Gemini free tier (15 RPM = ~600 articles/hour)

## Files Modified

```
core/
├── models.py                    # + markdown field
├── tasks.py                     # + enrich_from_captured_html task
├── api_views.py                 # Enabled enrichment trigger
└── migrations/
    └── 0010_noticia_markdown.py # New migration

PHASE_2_LLM_ENRICHMENT.md        # This file
```

## Summary

✅ **Enabled:** LLM enrichment for extension submissions
✅ **Field:** `markdown` field stores processed content
✅ **Task:** `enrich_from_captured_html` runs asynchronously
✅ **Migration:** Applied to database
✅ **Cost:** ~$0.0001 per article (practically free)

**Next:** Test with real articles and monitor Celery logs!

---

**Status:** LLM enrichment enabled and ready to test

**Requires:** Celery worker + Google API key

**See also:**
- [PHASE_2_SETUP.md](PHASE_2_SETUP.md) - Extension setup
- [core/parse.py](core/parse.py) - LLM parsing functions
- [core/tasks.py](core/tasks.py) - Background tasks
