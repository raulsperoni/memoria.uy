# Memoria.uy Browser Extension

Browser extension for Chrome/Firefox that captures article HTML client-side and submits to Memoria.uy, bypassing paywalls.

## Features

- **Client-side HTML capture** - Bypasses VPS IP blocks and paywalls
- **One-click voting** - Vote directly from any news article
- **Anonymous sessions** - No account required
- **Smart article extraction** - Automatically finds article content
- **Badge indicators** - Shows if you've already voted on current page
- **Configurable server** - Works with localhost or production

## Architecture

```
┌─────────────────┐
│  News Website   │ ◄── User reads article with paywall bypass
└────────┬────────┘
         │
         │ User clicks extension icon
         ▼
┌─────────────────┐
│ Content Script  │ ◄── Extracts full HTML from page
└────────┬────────┘
         │
         │ Sends to popup
         ▼
┌─────────────────┐
│  Popup UI       │ ◄── User votes (buena/mala/neutral)
└────────┬────────┘
         │
         │ POST with HTML + vote
         ▼
┌─────────────────┐
│ Django Backend  │ ◄── Stores HTML, creates vote
│  (Memoria.uy)   │     Triggers LLM enrichment
└─────────────────┘
```

## Installation (Development)

### 1. Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `browser-extension` folder

### 2. Firefox

1. Open Firefox and navigate to `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Navigate to `browser-extension` folder
4. Select `manifest.json`

**Note:** Firefox extensions loaded this way are temporary and will be removed when Firefox restarts.

## Setup

### 1. Start Django Server

```bash
# From project root
poetry run python manage.py migrate
poetry run python manage.py runserver
```

Server should be running at `http://localhost:8000`

### 2. Configure Extension

1. Click extension icon in browser toolbar
2. Click "Configuración" link at bottom
3. Verify API URL is set to `http://localhost:8000`
4. Click "Guardar cambios"

The extension will test the connection and confirm if successful.

## Usage

### Vote on an Article

1. Navigate to any news article (e.g., BBC, El País, La Diaria)
2. Click the Memoria.uy extension icon in toolbar
3. Select your opinion: Buena / Neutral / Mala
4. Click "Enviar voto"
5. Extension captures full HTML and submits to server

### Check Existing Votes

- Badge with "✓" appears on extension icon if you've already voted
- Popup pre-selects your existing vote when opened

## File Structure

```
browser-extension/
├── manifest.json           # Extension config (Manifest V3)
├── popup.html             # Popup UI (shown when clicking icon)
├── options.html           # Settings page
├── scripts/
│   ├── popup.js          # Popup logic and API calls
│   ├── content.js        # HTML extraction from page
│   ├── background.js     # Service worker (badge updates)
│   └── options.js        # Settings page logic
└── icons/
    ├── icon16.png        # Toolbar icon (16x16)
    ├── icon48.png        # Extension list (48x48)
    └── icon128.png       # Chrome Web Store (128x128)
```

## How It Works

### 1. Content Extraction

When user clicks extension, `content.js` runs in the page context and:

1. Searches for article content using heuristics:
   - `<article>` tag
   - `[role="article"]`
   - Common selectors (`.article-content`, `.post-content`, etc.)
   - Falls back to `<body>` if nothing found

2. Cleans extracted HTML:
   - Removes `<script>`, `<style>`, ads, paywalls
   - Strips inline event handlers
   - Preserves article structure and text

3. Extracts metadata:
   - Open Graph tags (`og:title`, `og:image`, etc.)
   - Twitter Card tags
   - JSON-LD structured data

### 2. API Communication

Extension sends POST to `/api/submit-from-extension/`:

```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "html": "<html>...</html>",
  "vote": "buena"
}
```

Headers:
- `X-Extension-Session`: Unique session ID (stored in extension storage)
- `Content-Type: application/json`

### 3. Django Backend

Backend (`core/api_views.py`):

1. **Creates/updates Noticia:**
   - Stores `captured_html` field
   - Extracts metadata from HTML
   - Falls back to fetching from URL if needed

2. **Creates/updates Voto:**
   - Links to extension session (anonymous)
   - Or links to authenticated user if logged in

3. **Triggers enrichment** (Phase 3):
   - Convert HTML → Markdown (LLM)
   - Extract entities, sentiment
   - Generate summary

## Configuration

### Extension Settings

Accessible via extension popup → "Configuración"

- **API URL**: Server endpoint (default: `http://localhost:8000`)

### Django Settings

Add to `settings.py` for production:

```python
# CORS for extension (if needed)
CORS_ALLOWED_ORIGINS = [
    "chrome-extension://*",
    "moz-extension://*",
]

# Or allow all origins (not recommended for production)
CORS_ALLOW_ALL_ORIGINS = True
```

## API Endpoints

### POST /api/submit-from-extension/

Submit article HTML and vote from extension.

**Request:**
```json
{
  "url": "https://...",
  "title": "Article Title",
  "html": "<html>...</html>",
  "vote": "buena|mala|neutral"
}
```

**Response:**
```json
{
  "success": true,
  "noticia_id": 123,
  "vote_created": true,
  "message": "Voto registrado"
}
```

### GET /api/check-vote/?url=https://...

Check if user has voted on a URL.

**Response:**
```json
{
  "voted": true,
  "opinion": "buena",
  "noticia_id": 123
}
```

## Testing

### Manual Testing Checklist

1. [ ] Extension installs without errors
2. [ ] Popup opens and shows article info
3. [ ] Vote buttons work and highlight when selected
4. [ ] Submit creates noticia in database
5. [ ] HTML is captured and stored
6. [ ] Badge shows ✓ after voting
7. [ ] Re-opening popup pre-selects existing vote
8. [ ] Settings page saves API URL
9. [ ] Works on paywalled articles

### Test URLs

Try these to test extension:

- **Free articles:**
  - BBC: https://www.bbc.com/news
  - Wikipedia: https://en.wikipedia.org/wiki/Uruguay

- **Paywalled (if you have access):**
  - La Diaria: https://ladiaria.com.uy
  - El País: https://www.elpais.com.uy

## Troubleshooting

### Extension doesn't appear

- Check that Developer mode is enabled
- Reload extension in `chrome://extensions`
- Check browser console for errors

### "Connection failed" error

- Verify Django server is running: `curl http://localhost:8000/health/`
- Check API URL in extension settings
- Look for CORS errors in browser console

### HTML not captured

- Check content script runs: Open DevTools → Console
- Try different article (some sites block extensions)
- Check `captured_html` field in database

### Badge doesn't update

- Background service worker may need restart
- Reload extension in `chrome://extensions`
- Check browser console for service worker errors

## Deployment (Production)

### Chrome Web Store

1. Create developer account ($5 one-time fee)
2. Package extension: `zip -r extension.zip browser-extension/`
3. Upload to Chrome Web Store Developer Dashboard
4. Fill out store listing (screenshots, description)
5. Submit for review (typically 1-3 days)

### Firefox Add-ons

1. Create account on addons.mozilla.org
2. Package extension: `zip -r extension.zip browser-extension/`
3. Upload to Developer Hub
4. Submit for review (typically 1-7 days)

### Update manifest.json for production

```json
{
  "host_permissions": [
    "https://memoria.uy/*"
  ]
}
```

## Privacy & Security

### What Data We Collect

- Article URLs you vote on
- Full HTML of pages (stored server-side)
- Anonymous session ID (generated locally)
- Vote opinion (buena/mala/neutral)

### What We DON'T Collect

- Browsing history
- Personal information
- Cookies from other sites
- Passwords or credentials

### Permissions Explanation

- `activeTab` - Access current tab's content when you click extension
- `storage` - Store session ID and settings locally
- `host_permissions` - Send data to Memoria.uy server only

## Roadmap

### Phase 2 (Current)
- [x] Basic extension with voting
- [x] HTML capture from client browser
- [x] Django API endpoints
- [ ] Testing with real articles
- [ ] Published to Chrome/Firefox stores

### Phase 3 (Future)
- [ ] Re-enable LLM enrichment from captured HTML
- [ ] Entity extraction from client HTML
- [ ] Sentiment analysis
- [ ] Article summaries

### Phase 4 (Future)
- [ ] Keyboard shortcuts
- [ ] Context menu integration (right-click → vote)
- [ ] Multiple vote changes before final submit
- [ ] Article highlights/annotations

## Contributing

Found a bug? Have suggestions? Open an issue in the main repo.

## License

Same as main Memoria.uy project (see root LICENSE file).
