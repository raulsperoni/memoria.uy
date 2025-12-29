# Phase 2: Browser Extension - Setup Guide

Phase 2 implementation is complete! This guide will help you test and deploy the browser extension.

## What Was Built

### Browser Extension
- **Chrome/Firefox compatible** extension (Manifest V3)
- **Client-side HTML capture** - Bypasses server IP blocks and paywalls
- **One-click voting** interface
- **Anonymous session** support
- **Badge indicators** for voted articles

### Django Backend
- New model field: `Noticia.captured_html` (stores full article HTML)
- API endpoint: `POST /api/submit-from-extension/` (receives HTML + vote)
- API endpoint: `GET /api/check-vote/?url=...` (checks existing votes)
- Utility function: `parse_from_html_string()` (extracts meta from HTML)
- CORS configuration for extension communication

## Quick Start

### 1. Update Dependencies

```bash
poetry install  # Installs django-cors-headers
```

### 2. Apply Migration

```bash
poetry run python manage.py migrate
# ✓ Applied: core.0009_noticia_captured_html
```

### 3. Start Django Server

```bash
poetry run python manage.py runserver
# Server at http://localhost:8000
```

### 4. Install Extension

#### Chrome:
1. Open `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select `browser-extension` folder

#### Firefox:
1. Open `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Select `browser-extension/manifest.json`

### 5. Configure Extension

1. Click extension icon in toolbar
2. Click "Configuración" at bottom
3. Verify URL: `http://localhost:8000`
4. Click "Guardar cambios"

## Testing

### Manual Test Flow

1. **Navigate to a news article** (e.g., BBC, Wikipedia, local news)
2. **Click extension icon** - Should show article title and URL
3. **Select vote** (Buena/Neutral/Mala)
4. **Click "Enviar voto"** - Should submit and close popup
5. **Check database:**
   ```bash
   poetry run python manage.py shell
   >>> from core.models import Noticia
   >>> n = Noticia.objects.last()
   >>> print(n.meta_titulo)
   >>> print(len(n.captured_html))  # Should have HTML
   >>> print(n.votos.count())  # Should be 1
   ```

### Badge Test

- After voting, extension icon should show green "✓" badge
- Re-opening popup should pre-select your existing vote

### API Test

```bash
# Check health
curl http://localhost:8000/health/

# Test check-vote endpoint (should return {"voted": false})
curl "http://localhost:8000/api/check-vote/?url=https://example.com"
```

## File Structure

```
browser-extension/
├── manifest.json              # Extension configuration
├── popup.html                 # Voting UI
├── options.html               # Settings page
├── scripts/
│   ├── popup.js              # Popup logic
│   ├── content.js            # HTML extraction
│   ├── background.js         # Badge updates
│   └── options.js            # Settings
├── icons/
│   ├── README.txt            # Icon instructions
│   └── generate_icons.html   # Icon generator
└── README.md                 # Full documentation

core/
├── models.py                 # + captured_html field
├── api_views.py              # NEW: Extension API
├── parse.py                  # + parse_from_html_string()
└── migrations/
    └── 0009_noticia_captured_html.py

memoria/
├── urls.py                   # + API routes
└── settings.py               # + CORS config
```

## Known Issues & TODOs

### Icons
- Currently extension has no visible icons (will show default)
- **Fix:** Open `browser-extension/icons/generate_icons.html` in browser
- Right-click each canvas, save as PNG
- Or create proper icons in Figma/Inkscape

### Extension Warnings
- Chrome may warn "This extension is not listed in Chrome Web Store"
- This is normal for local development
- Will disappear after publishing to store

### Session Persistence
- Extension session IDs are stored locally
- Clearing extension storage will reset votes
- Future: Add vote migration on user signup

## Next Steps

### Phase 2 Completion Tasks

1. **Create proper icons** (see icons/generate_icons.html)

2. **Test with paywalled articles:**
   - La Diaria (if you have access)
   - El País Uruguay
   - Local news sites

3. **Test edge cases:**
   - Very long articles
   - Articles with heavy JavaScript
   - Single-page applications
   - Articles without `<article>` tags

4. **Performance testing:**
   - Time from click to vote stored
   - HTML size limits (current: no limit)
   - Extension memory usage

### Phase 3: Re-enable LLM Enrichment

Currently disabled, will re-enable after extension testing:

```python
# In core/api_views.py (currently commented out)
if noticia.captured_html and not noticia.markdown:
    from core.tasks import enrich_from_captured_html
    enrich_from_captured_html.delay(noticia.id)
```

Tasks to create:
- `enrich_from_captured_html(noticia_id)` - Convert HTML → Markdown
- `enrich_content_from_markdown(noticia_id)` - Extract entities, sentiment
- Use `parse_noticia_markdown()` on captured HTML
- Use `parse_noticia()` on generated markdown

### Phase 4: Publishing

Once tested:

1. **Chrome Web Store:**
   - Create developer account ($5)
   - Package extension as ZIP
   - Fill out store listing
   - Submit for review (1-3 days)

2. **Firefox Add-ons:**
   - Create account (free)
   - Package extension as ZIP
   - Submit for review (1-7 days)

3. **Update manifest for production:**
   ```json
   {
     "host_permissions": [
       "https://memoria.uy/*"
     ]
   }
   ```

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│            User's Browser                       │
│                                                 │
│  ┌───────────────┐         ┌─────────────────┐ │
│  │  News Site    │         │  Extension UI   │ │
│  │  (Paywalled)  │◄────────│  (popup.html)   │ │
│  └───────┬───────┘         └────────┬────────┘ │
│          │                          │          │
│          │ Read article             │ User     │
│          │ with user's              │ votes    │
│          │ session/cookies          │          │
│          ▼                          ▼          │
│  ┌───────────────┐         ┌─────────────────┐ │
│  │ Content Script│─────────▶│  Popup Script   │ │
│  │ (content.js)  │  HTML   │  (popup.js)     │ │
│  └───────────────┘         └────────┬────────┘ │
└───────────────────────────────────────┼─────────┘
                                       │
                                       │ POST
                                       │ {html, vote}
                                       ▼
                           ┌──────────────────────┐
                           │   Django Backend     │
                           │   (localhost:8000)   │
                           │                      │
                           │  ┌────────────────┐  │
                           │  │ API Views      │  │
                           │  │ (api_views.py) │  │
                           │  └────────┬───────┘  │
                           │           │          │
                           │           ▼          │
                           │  ┌────────────────┐  │
                           │  │ Models         │  │
                           │  │ (models.py)    │  │
                           │  │                │  │
                           │  │ Noticia        │  │
                           │  │ + captured_html│  │
                           │  │                │  │
                           │  │ Voto           │  │
                           │  │ + session_key  │  │
                           │  └────────────────┘  │
                           └──────────────────────┘
```

## Benefits Over Server-Side Fetching

### Why Client-Side Capture?

1. **Bypasses paywalls** - Uses user's authenticated session
2. **Avoids IP blocks** - News sites don't block individual users
3. **JavaScript rendering** - Captures content loaded by JS
4. **Better metadata** - Gets content after client-side processing
5. **Legal compliance** - User explicitly shares content they can access

## Privacy & Security

### What We Collect
- Article URLs user votes on
- Full HTML of pages (stored server-side)
- Anonymous session ID (generated locally)
- Vote opinions (buena/mala/neutral)

### What We DON'T Collect
- Browsing history
- Personal information
- Cookies from other sites
- Passwords or credentials

### Permissions Used
- `activeTab` - Access current tab when user clicks extension
- `storage` - Store session ID and settings locally
- `host_permissions` - Only memoria.uy server

## Troubleshooting

### Extension doesn't load
```bash
# Check for syntax errors
cd browser-extension
# Look at manifest.json, should be valid JSON
```

### "Connection failed" in popup
```bash
# Verify server is running
curl http://localhost:8000/health/
# Should return: {"status": "healthy"}

# Check extension settings
# Extension popup → Configuración
# API URL should be: http://localhost:8000
```

### HTML not captured
```bash
# Check database
poetry run python manage.py shell
>>> from core.models import Noticia
>>> n = Noticia.objects.last()
>>> print(n.captured_html)  # Should not be None

# Check browser console
# F12 → Console → Look for content script errors
```

### CORS errors
```bash
# Check settings.py has:
INSTALLED_APPS = [
    ...
    "corsheaders",
]

MIDDLEWARE = [
    ...
    "corsheaders.middleware.CorsMiddleware",
]

CORS_ALLOW_ALL_ORIGINS = DEBUG
```

## Support

See full documentation in:
- [browser-extension/README.md](browser-extension/README.md) - Extension docs
- [DEVELOPMENT.md](DEVELOPMENT.md) - Phase roadmap
- [CLAUDE.md](CLAUDE.md) - Project architecture

---

**Status:** Phase 2 implementation complete, ready for testing!

**Next:** Test with real articles, create icons, then move to Phase 3 (LLM enrichment)
