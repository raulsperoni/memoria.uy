# Memoria.uy - 2025 Roadmap

## Decisions Made (December 2025)

✅ **Client-side capture** - Browser extension + embeddable widget
✅ **Skip archiving** - Keep it simple, just store URL + metadata
✅ **Keep LLMs** - Upgrade to latest affordable models (Dec 2025)
✅ **Database** - SQLite (dev) + Dockerized Postgres (prod)

---

## Phase 1: MVP - Web-Based Voting (Weeks 1-2)

**Goal:** Prove the core loop works without extensions or complexity

### Features
- [x] User authentication (django-allauth already setup)
- [ ] URL submission form (already exists, clean it up)
- [ ] Simple vote buttons: Good / Bad / Neutral
- [ ] Timeline view with vote counts
- [ ] Basic filtering: My votes, All votes
- [ ] Remove archiving workflow (comment out for now)
- [ ] Remove LLM enrichment (comment out for now)

### Tech Stack
- Django 5.1 + HTMX + Tailwind (keep existing)
- SQLite for development
- No Celery (everything sync for now)
- Deploy to Render or Railway (free tier)

### Success Criteria
- 5-10 friends actively vote on 20+ articles
- Vote diversity: some articles are split 50/50
- Users return next day to vote again

### Code Changes Needed
```python
# core/models.py - Simplify Noticia model
class Noticia(models.Model):
    enlace = models.URLField(unique=True)
    meta_titulo = models.CharField(max_length=255, blank=True)
    meta_imagen = models.URLField(blank=True)
    meta_description = models.TextField(blank=True)
    fecha_agregado = models.DateTimeField(auto_now_add=True)
    agregado_por = models.ForeignKey(User, on_delete=models.CASCADE)

    # REMOVED: archivo_url, markdown, LLM fields (for now)

    def update_meta_from_url(self):
        """Fetch og:title and og:image from URL"""
        from core.parse import parse_from_meta_tags
        title, image = parse_from_meta_tags(self.enlace)
        if title:
            self.meta_titulo = title
        if image:
            self.meta_imagen = image
        self.save()

# core/views.py - Simplify create view
class NoticiaCreateView(LoginRequiredMixin, FormView):
    def form_valid(self, form):
        enlace = form.cleaned_data.get('enlace')
        vote = form.cleaned_data.get('opinion')

        # Get or create noticia
        noticia, created = Noticia.objects.get_or_create(
            enlace=enlace,
            defaults={'agregado_por': self.request.user}
        )

        # Fetch metadata synchronously (fast, just HTTP HEAD)
        if created:
            noticia.update_meta_from_url()

        # Save vote
        Voto.objects.update_or_create(
            usuario=self.request.user,
            noticia=noticia,
            defaults={'opinion': vote}
        )

        # Redirect or HTMX response
        # ... existing code ...
```

### Timeline
- **Day 1-2:** Remove archive/LLM code, test locally
- **Day 3-4:** Polish UI, add vote stats
- **Day 5-6:** Deploy to free hosting, invite 10 friends
- **Day 7-14:** Observe usage, gather feedback

---

## Phase 2: Browser Extension (Weeks 3-6)

**Goal:** Solve paywall issue, enable client-side capture

### Features
- [ ] Chrome extension (Manifest V3)
- [ ] Firefox extension (same codebase)
- [ ] One-click "Share & Vote" button
- [ ] Captures full HTML + metadata
- [ ] Sends to Memoria.uy API
- [ ] Shows success confirmation

### Architecture

**Extension Structure:**
```
memoria-extension/
├── manifest.json          # Chrome/Firefox config
├── popup.html            # Vote UI (opens when clicked)
├── popup.js              # Vote logic
├── content.js            # Page scraping
├── background.js         # API communication
└── icons/                # Extension icons
```

**manifest.json:**
```json
{
  "manifest_version": 3,
  "name": "Memoria.uy",
  "version": "1.0.0",
  "description": "Share news and vote: Good, Bad, or Neutral",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["https://memoria.uy/*"],
  "action": {
    "default_popup": "popup.html",
    "default_icon": "icons/icon48.png"
  },
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content.js"]
  }],
  "background": {
    "service_worker": "background.js"
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

**popup.html (simplified):**
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {
      width: 320px;
      padding: 16px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    h2 { margin: 0 0 16px 0; font-size: 16px; }
    .vote-btn {
      width: 100%;
      padding: 12px;
      margin: 8px 0;
      border: none;
      border-radius: 8px;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .vote-btn:hover { transform: scale(1.02); }
    .good { background: #4ade80; color: white; }
    .bad { background: #f87171; color: white; }
    .neutral { background: #94a3b8; color: white; }
    #status {
      margin-top: 16px;
      padding: 12px;
      border-radius: 8px;
      text-align: center;
      display: none;
    }
    .success { background: #d1fae5; color: #065f46; }
    .error { background: #fee2e2; color: #991b1b; }
  </style>
</head>
<body>
  <h2>¿Cómo es esta noticia?</h2>

  <button class="vote-btn good" data-vote="buena">
    😊 Buena Noticia
  </button>

  <button class="vote-btn bad" data-vote="mala">
    😞 Mala Noticia
  </button>

  <button class="vote-btn neutral" data-vote="neutral">
    😐 Neutral
  </button>

  <div id="status"></div>

  <script src="popup.js"></script>
</body>
</html>
```

**popup.js:**
```javascript
// Get current tab info and set up vote buttons
document.addEventListener('DOMContentLoaded', async () => {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  const statusDiv = document.getElementById('status');

  // Check if user is logged in (stored from previous auth)
  const authToken = await chrome.storage.local.get('authToken');

  document.querySelectorAll('.vote-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const vote = btn.dataset.vote;

      try {
        // Get article data from content script
        const response = await chrome.tabs.sendMessage(tab.id, {
          action: 'captureArticle'
        });

        if (!response || !response.url) {
          throw new Error('No se pudo capturar la página');
        }

        // Send to Memoria.uy
        const result = await fetch('https://memoria.uy/api/extension/submit', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken.authToken || ''}`
          },
          body: JSON.stringify({
            ...response,
            vote: vote
          })
        });

        if (!result.ok) {
          throw new Error('Error al guardar');
        }

        // Show success
        statusDiv.className = 'success';
        statusDiv.textContent = '✅ ¡Guardado!';
        statusDiv.style.display = 'block';

        // Auto-close after 1 second
        setTimeout(() => window.close(), 1000);

      } catch (error) {
        console.error('Error:', error);
        statusDiv.className = 'error';
        statusDiv.textContent = '❌ ' + error.message;
        statusDiv.style.display = 'block';
      }
    });
  });
});
```

**content.js:**
```javascript
// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'captureArticle') {
    // Extract article metadata
    const article = {
      url: window.location.href,
      title: document.title,
      meta: {
        title: getMetaContent('og:title') ||
               getMetaContent('twitter:title') ||
               document.title,
        image: getMetaContent('og:image') ||
               getMetaContent('twitter:image'),
        description: getMetaContent('og:description') ||
                    getMetaContent('description'),
        author: getMetaContent('author') ||
               getMetaContent('article:author'),
        published: getMetaContent('article:published_time')
      },
      // Capture full HTML for future LLM processing
      html: document.documentElement.outerHTML,
      timestamp: new Date().toISOString()
    };

    sendResponse(article);
  }
  return true; // Keep message channel open for async response
});

function getMetaContent(name) {
  // Try property attribute first (og:, twitter:)
  let meta = document.querySelector(`meta[property="${name}"]`);
  if (meta) return meta.getAttribute('content');

  // Try name attribute
  meta = document.querySelector(`meta[name="${name}"]`);
  if (meta) return meta.getAttribute('content');

  return null;
}
```

**Django API endpoint:**
```python
# core/views.py
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
import json

@csrf_exempt  # Extension can't easily get CSRF token
@require_http_methods(["POST"])
def extension_submit(request):
    """
    Endpoint for browser extension submissions.
    Accepts article metadata + user vote.
    """
    try:
        data = json.loads(request.body)

        # For now, allow anonymous votes (tracked by session)
        # Later: require auth via OAuth or API key

        # Create or get noticia
        noticia, created = Noticia.objects.get_or_create(
            enlace=data['url'],
            defaults={
                'meta_titulo': data['meta'].get('title', '')[:255],
                'meta_imagen': data['meta'].get('image', ''),
                'meta_description': data['meta'].get('description', ''),
                'agregado_por': request.user if request.user.is_authenticated else None
            }
        )

        # Save vote (use session ID if not authenticated)
        user = request.user if request.user.is_authenticated else None
        if user:
            Voto.objects.update_or_create(
                usuario=user,
                noticia=noticia,
                defaults={'opinion': data['vote']}
            )

        # TODO: Queue LLM enrichment if HTML provided
        # if 'html' in data and created:
        #     enrich_from_html.delay(noticia.id, data['html'])

        return JsonResponse({
            'status': 'success',
            'noticia_id': noticia.id,
            'created': created
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

# urls.py
urlpatterns = [
    # ... existing patterns ...
    path('api/extension/submit', extension_submit, name='extension-submit'),
]
```

### Distribution Strategy

**Chrome Web Store:**
1. Create developer account ($5 one-time fee)
2. Package extension as `.zip`
3. Submit with screenshots + description
4. Review takes 1-3 days

**Firefox Add-ons:**
1. Free Mozilla account
2. Submit same extension (manifest compatible)
3. Review takes 1-2 weeks

**Self-hosted (early testing):**
- Upload `.zip` to GitHub Releases
- Users manually install via "Load unpacked" (dev mode)
- No review process, instant updates

### Timeline
- **Week 3:** Build extension core (popup + content script)
- **Week 4:** Build API endpoint + test end-to-end
- **Week 5:** Polish UI, add error handling
- **Week 6:** Submit to Chrome/Firefox stores

---

## Phase 3: LLM Enrichment (Weeks 7-10)

**Goal:** Auto-extract summary, entities, sentiment using latest affordable LLMs

### Latest Affordable Models (December 2025)

**Updated model priorities:**

```python
# core/parse.py

# As of December 2025, check latest pricing at:
# - https://openrouter.ai/models
# - https://ai.google.dev/pricing
# - https://platform.openai.com/docs/models

MODELS_PRIORITY_MD = {
    # Google Gemini 2.0 Flash (free tier: 15 RPM, 1.5M tokens/day)
    "gemini/gemini-2.0-flash-exp": 1,

    # Fallback: Claude 3.5 Haiku (cheap, quality)
    "anthropic/claude-3-5-haiku-20241022": 2,

    # Last resort: GPT-4o-mini
    "openai/gpt-4o-mini": 3,
}

MODELS_PRIORITY_JSON = {
    # Gemini 2.0 Flash with JSON mode (free tier)
    "gemini/gemini-2.0-flash-exp": 1,

    # Fallback: Mistral Small (cheap structured output)
    "mistralai/mistral-small-2409": 2,

    # Last resort: GPT-4o-mini
    "openai/gpt-4o-mini": 3,
}
```

**Cost comparison (December 2025):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Typical article cost |
|-------|---------------------|----------------------|---------------------|
| Gemini 2.0 Flash | **FREE** (15 RPM limit) | **FREE** | $0 |
| Claude 3.5 Haiku | $0.80 | $4.00 | ~$0.0005 |
| GPT-4o-mini | $0.15 | $0.60 | ~$0.0002 |
| Mistral Small | $0.20 | $0.60 | ~$0.0003 |

**Recommendation:** Use Gemini 2.0 Flash (free tier) as primary. With 15 requests/min limit, you can process ~21,000 articles/day for $0.

### Re-enable LLM Tasks

```python
# core/tasks.py - Update with new models

@shared_task
@task_lock()
def enrich_from_html(noticia_id, html):
    """
    Extract metadata from captured HTML using LLM.
    Called when extension submits article.
    """
    noticia = Noticia.objects.get(id=noticia_id)

    # Parse HTML to markdown (if needed)
    markdown = parse_noticia_markdown(html, noticia.meta_titulo)

    if markdown:
        # Extract structured data
        articulo = parse_noticia(markdown)

        if articulo:
            # Update noticia with LLM-extracted data
            noticia.titulo = articulo.titulo or noticia.meta_titulo
            noticia.fuente = articulo.fuente
            noticia.categoria = articulo.categoria or 'otros'
            noticia.resumen = articulo.resumen

            # Parse date if available
            if articulo.fecha:
                try:
                    from datetime import datetime
                    noticia.fecha_noticia = datetime.fromisoformat(articulo.fecha)
                except (ValueError, TypeError):
                    pass

            noticia.save()

            # Save entities
            if articulo.entidades:
                for ent in articulo.entidades:
                    entidad, _ = Entidad.objects.get_or_create(
                        nombre=ent.nombre,
                        tipo=ent.tipo
                    )
                    NoticiaEntidad.objects.get_or_create(
                        noticia=noticia,
                        entidad=entidad,
                        defaults={'sentimiento': ent.sentimiento}
                    )

    return noticia_id
```

### Timeline
- **Week 7:** Update model configs, test locally
- **Week 8:** Re-enable Celery tasks, test enrichment
- **Week 9:** Add entity pages, sentiment filters
- **Week 10:** Deploy to production, monitor costs

---

## Phase 4: Embeddable Widget (Weeks 11-14)

**Goal:** Partner with news outlets to embed voting widget

### Widget Features
- Lightweight iframe embed (`<script>` tag)
- Shows vote counts for current article
- Users can vote without leaving page
- Links to Memoria.uy for full analysis
- Respects GDPR/privacy (no tracking)

### Implementation

**Embed script (memoria-embed.js):**
```javascript
(function() {
  'use strict';

  // Find all widget containers
  const widgets = document.querySelectorAll('.memoria-widget');

  widgets.forEach(widget => {
    // Get URL to analyze (defaults to current page)
    const url = widget.dataset.url || window.location.href;
    const theme = widget.dataset.theme || 'light'; // light/dark

    // Create iframe
    const iframe = document.createElement('iframe');
    iframe.src = `https://memoria.uy/widget?url=${encodeURIComponent(url)}&theme=${theme}`;
    iframe.style.cssText = 'width: 100%; height: 180px; border: 1px solid #e5e7eb; border-radius: 8px;';
    iframe.setAttribute('scrolling', 'no');
    iframe.setAttribute('frameborder', '0');

    // Insert iframe
    widget.appendChild(iframe);

    // Listen for resize messages from iframe
    window.addEventListener('message', (event) => {
      if (event.origin !== 'https://memoria.uy') return;
      if (event.data.type === 'resize') {
        iframe.style.height = event.data.height + 'px';
      }
    });
  });
})();
```

**Widget view (Django):**
```python
# core/views.py

def widget_view(request):
    """
    Embeddable widget showing vote stats + vote buttons.
    Rendered in iframe for security.
    """
    url = request.GET.get('url')
    theme = request.GET.get('theme', 'light')

    # Get or create noticia
    noticia = Noticia.objects.filter(enlace=url).first()

    # Calculate vote stats
    votes = {'good': 0, 'bad': 0, 'neutral': 0, 'total': 0}
    if noticia:
        votes = noticia.votos.aggregate(
            good=Count('id', filter=Q(opinion='buena')),
            bad=Count('id', filter=Q(opinion='mala')),
            neutral=Count('id', filter=Q(opinion='neutral'))
        )
        votes['total'] = votes['good'] + votes['bad'] + votes['neutral']

    context = {
        'url': url,
        'noticia': noticia,
        'votes': votes,
        'theme': theme,
    }

    return render(request, 'widgets/vote_widget.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def widget_vote(request):
    """
    Handle vote submission from widget.
    Returns updated vote counts.
    """
    data = json.loads(request.body)
    url = data['url']
    vote = data['vote']

    # Create/get noticia
    noticia, _ = Noticia.objects.get_or_create(
        enlace=url,
        defaults={'agregado_por': None}  # Anonymous via widget
    )

    # Save vote (use session or IP-based deduplication)
    session_id = request.session.session_key or request.META.get('REMOTE_ADDR')

    # For widgets, we track by session to allow voting without login
    # Store in a separate WidgetVote model or use Voto with null user

    # Return updated counts
    votes = noticia.votos.aggregate(
        good=Count('id', filter=Q(opinion='buena')),
        bad=Count('id', filter=Q(opinion='mala')),
        neutral=Count('id', filter=Q(opinion='neutral'))
    )

    return JsonResponse({'status': 'success', 'votes': votes})
```

**Widget template (widgets/vote_widget.html):**
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      padding: 16px;
      {% if theme == 'dark' %}
        background: #1f2937;
        color: #f9fafb;
      {% else %}
        background: white;
        color: #111827;
      {% endif %}
    }
    .header {
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 12px;
    }
    .stats {
      display: flex;
      gap: 12px;
      margin-bottom: 12px;
      font-size: 13px;
    }
    .stat { display: flex; align-items: center; gap: 4px; }
    .vote-buttons {
      display: flex;
      gap: 8px;
    }
    .vote-btn {
      flex: 1;
      padding: 8px;
      border: none;
      border-radius: 6px;
      font-size: 13px;
      cursor: pointer;
      transition: transform 0.1s;
    }
    .vote-btn:hover { transform: scale(1.05); }
    .vote-btn.good { background: #4ade80; color: white; }
    .vote-btn.bad { background: #f87171; color: white; }
    .vote-btn.neutral { background: #94a3b8; color: white; }
    .footer {
      margin-top: 12px;
      font-size: 11px;
      text-align: center;
      opacity: 0.6;
    }
    .footer a {
      color: inherit;
      text-decoration: none;
      font-weight: 500;
    }
  </style>
</head>
<body>
  <div class="header">¿Cómo es esta noticia?</div>

  {% if votes.total > 0 %}
  <div class="stats">
    <div class="stat">😊 {{ votes.good }}</div>
    <div class="stat">😞 {{ votes.bad }}</div>
    <div class="stat">😐 {{ votes.neutral }}</div>
  </div>
  {% endif %}

  <div class="vote-buttons">
    <button class="vote-btn good" data-vote="buena">😊 Buena</button>
    <button class="vote-btn bad" data-vote="mala">😞 Mala</button>
    <button class="vote-btn neutral" data-vote="neutral">😐 Neutral</button>
  </div>

  <div class="footer">
    Powered by <a href="https://memoria.uy" target="_blank">Memoria.uy</a>
  </div>

  <script>
    // Handle vote button clicks
    document.querySelectorAll('.vote-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const vote = btn.dataset.vote;

        try {
          const response = await fetch('https://memoria.uy/api/widget/vote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              url: '{{ url }}',
              vote: vote
            })
          });

          const data = await response.json();

          if (data.status === 'success') {
            // Update UI with new counts
            location.reload(); // Simple approach
          }
        } catch (error) {
          console.error('Vote failed:', error);
        }
      });
    });

    // Send height to parent for responsive iframe
    function sendHeight() {
      const height = document.body.scrollHeight;
      window.parent.postMessage({ type: 'resize', height: height }, '*');
    }

    sendHeight();
    window.addEventListener('resize', sendHeight);
  </script>
</body>
</html>
```

**Usage by news outlets:**
```html
<!-- In their article template -->
<div class="memoria-widget" data-url="current-page" data-theme="light"></div>
<script async src="https://memoria.uy/embed.js"></script>
```

### Partnership Strategy
1. **Target:** Small independent news outlets (friendly, need engagement tools)
2. **Pitch:** "Add audience sentiment to your articles - free widget"
3. **Value prop for them:**
   - Engagement metric (readers vote)
   - Social proof (show popular opinions)
   - Backlink to your site (SEO)
4. **Value prop for you:**
   - Distribution (piggyback on their traffic)
   - Data (more votes = better clustering)
   - Credibility (partnered with real news)

### Timeline
- **Week 11:** Build widget iframe + embed script
- **Week 12:** Test with 1-2 friendly outlets
- **Week 13:** Polish based on feedback
- **Week 14:** Launch widget SDK publicly

---

## Phase 5: Clustering & Visualization (Months 4-5)

**Goal:** Reveal polarization patterns (only viable with 100+ active users)

### Prerequisites
- 100+ users with 10+ votes each
- 500+ articles with 5+ votes each
- Diverse vote patterns (not everyone agrees)

### Features
- User opinion clustering (PCA/t-SNE)
- Interactive cluster map (Plotly or D3.js)
- "You are here" marker
- Consensus metrics per article
- Entity reputation tracking

### Tech Stack
- scikit-learn for clustering
- Plotly for interactive viz
- Redis for caching computed clusters
- Celery periodic task to recompute daily

### Timeline
- **Month 4:** Build clustering algorithm, test with synthetic data
- **Month 5:** Build visualization UI, deploy

**NOTE:** Don't build this until you have the data. Clustering on 10 users is meaningless.

---

## Database Strategy

### Development: SQLite
```python
# memoria/settings.py
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
```

**Pros:**
- Zero setup
- Fast for development
- File-based (easy to backup/reset)

**Cons:**
- Single writer (Celery + web server = conflicts)
- No full-text search
- Locks on high concurrency

**When to use:** Local dev only

### Production: Dockerized Postgres

**docker-compose.yml (update):**
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: memoria
      POSTGRES_USER: memoria
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U memoria"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  web:
    build: .
    command: web
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    env_file:
      - ./.env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    restart: always

  celery_worker:
    build: .
    command: worker
    volumes:
      - .:/app
    env_file:
      - ./.env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: always

  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    depends_on:
      - web
    restart: always

volumes:
  postgres_data:
  static_volume:
  media_volume:
```

**Django settings:**
```python
# memoria/settings.py
import dj_database_url

if not DEBUG:
    DATABASES = {
        'default': dj_database_url.config(
            default=f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@db:5432/{os.getenv('DB_NAME')}",
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
```

**.env:**
```bash
DEBUG=False
DB_NAME=memoria
DB_USER=memoria
DB_PASSWORD=your-secure-password-here
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
```

### Migration from SQLite to Postgres

```bash
# 1. Dump SQLite data
python manage.py dumpdata --natural-foreign --natural-primary \
  -e contenttypes -e auth.Permission > datadump.json

# 2. Switch to Postgres in settings
# 3. Run migrations
python manage.py migrate

# 4. Load data
python manage.py loaddata datadump.json
```

---

## Success Metrics & KPIs

### Phase 1 (MVP) - Week 2
- ✅ 5+ active users
- ✅ 20+ articles submitted
- ✅ 50+ votes cast
- ✅ At least 3 articles with split votes (not 100% consensus)

### Phase 2 (Extension) - Week 6
- ✅ 100+ extension installs
- ✅ 50+ articles submitted via extension
- ✅ 5+ daily active extension users

### Phase 3 (LLM) - Week 10
- ✅ 80%+ articles successfully enriched
- ✅ Entity extraction accuracy >70% (manual check on 20 articles)
- ✅ LLM costs <$5/month

### Phase 4 (Widget) - Week 14
- ✅ 2+ news outlet partners
- ✅ 100+ votes via widget
- ✅ 10+ new users discovered via widget

### Phase 5 (Clustering) - Month 5
- ✅ 100+ users with 10+ votes each
- ✅ 3+ distinct clusters emerge
- ✅ Users engage with cluster visualization (>50% click on map)

---

## Risk Mitigation

### Technical Risks
| Risk | Mitigation |
|------|------------|
| Extension not approved by stores | Self-host initially, fix issues, resubmit |
| LLM rate limits hit | Implement queue with exponential backoff |
| Postgres migration issues | Test on staging first, keep SQLite backup |
| Widget iframe blocked by CSP | Provide fallback instructions, use postMessage correctly |

### Product Risks
| Risk | Mitigation |
|------|------------|
| Low user adoption | Focus on personal network first, iterate on UX |
| No vote diversity (everyone agrees) | Target polarizing topics, diverse user base |
| Spam/abuse | Rate limiting, require account for extension, manual review initially |
| News outlets don't embed widget | Make it valuable for them (analytics dashboard?) |

### Resource Risks
| Risk | Mitigation |
|------|------------|
| Burn out building too much | Ship MVP first, validate before building more |
| Costs spiral | Set budget alerts, use free tiers, monitor daily |
| Time constraints | 10 hours/week = 6 weeks for MVP (realistic) |

---

## Next Immediate Steps (This Week)

### Day 1 (Today)
- [x] Document decisions in ROADMAP_2025.md
- [ ] Audit current codebase: what works, what's broken?
- [ ] Create new git branch: `mvp-2025`
- [ ] Remove/comment out archiving code
- [ ] Remove/comment out LLM enrichment

### Day 2-3
- [ ] Test core voting flow locally
- [ ] Fix any HTMX issues
- [ ] Polish timeline UI (remove debug sections)
- [ ] Add simple vote count display

### Day 4-5
- [ ] Deploy to free hosting (Render/Railway)
- [ ] Test production deploy
- [ ] Invite 5 friends to test

### Day 6-7
- [ ] Gather feedback
- [ ] Fix critical bugs
- [ ] Plan extension build for next week

---

## Long-Term Vision (Revisited)

### 6 Months
- 500+ active users
- 5,000+ articles with votes
- 3+ distinct opinion clusters
- Widget on 5+ news sites
- $10/month operating costs

### 1 Year
- 2,000+ active users
- Public API launched
- Research partnerships (universities)
- Media coverage (writeup in tech/civic media)
- Break-even on costs (donations/grants)

### 2-3 Years
- 10,000+ active users
- Referenced in academic papers on polarization
- Integrated with major news aggregators
- Non-profit status (if mission-driven)
- OR sustainable revenue (API subscriptions, institutional)

---

## Open Questions (Decide This Week)

1. **Anonymous voting or require accounts?**
   - Pro anonymous: Lower friction, more votes
   - Pro accounts: Better clustering, less spam
   - **Hybrid:** Allow anonymous via widget, encourage account creation for timeline

2. **Soft launch or public launch?**
   - Soft: Invite-only first 100 users, iterate
   - Public: Post on HN/Reddit immediately
   - **Recommendation:** Soft launch, polish, then public

3. **Monetization strategy?**
   - Free forever (donations/grants)
   - Freemium API (free tier + paid)
   - Institutional subscriptions (universities, newsrooms)
   - **Recommendation:** Free for individuals, paid API for institutions (decide in Month 3)

4. **Legal structure?**
   - Personal project (simplest)
   - Non-profit (mission alignment, can accept grants)
   - For-profit (can raise capital)
   - **Recommendation:** Start as personal project, decide in Month 6

---

## Resources & References

### Technical
- **Django + HTMX:** https://django-htmx.readthedocs.io/
- **Browser Extensions:** https://developer.chrome.com/docs/extensions/mv3/
- **LiteLLM:** https://docs.litellm.ai/
- **Gemini API:** https://ai.google.dev/
- **scikit-learn clustering:** https://scikit-learn.org/stable/modules/clustering.html

### Inspiration
- **Polis:** https://pol.is (opinion clustering)
- **Ground News:** https://ground.news (bias ratings)
- **AllSides:** https://www.allsides.com (media bias chart)
- **Wikipedia:** https://wikipedia.org (NPOV, consensus-driven)

### Community
- **Reddit:** r/django, r/webdev, r/civictech
- **Discord:** Django Discord, HTMX Discord
- **HN:** Post your MVP when ready

---

**Last Updated:** December 29, 2025
**Status:** Ready to start Phase 1 (MVP)
