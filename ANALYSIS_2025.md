# Memoria.uy - Critical Analysis & Revival Strategy (2025)

## Executive Summary

**Verdict: This project is HIGHLY VIABLE in 2025 with strategic pivots**

The core concept—collective sentiment analysis revealing polarization patterns—is more relevant than ever. The technical blockers you faced in the past have elegant modern solutions. This analysis addresses your three issues and proposes a complete rearchitecture.

---

## The Three Issues: Root Causes & Modern Solutions

### Issue #1: Paywall Blocking on Server

**Root Cause:**
- Server IP addresses from VPS/cloud providers are blacklisted by news sites
- Your local IP works because it's residential/ISP-assigned
- Free proxies are unreliable and mostly blacklisted

**Why This Matters:**
Without access to article content, the entire enrichment pipeline fails.

**Modern Solutions (2025):**

#### ✅ **Solution A: Client-Side Capture (RECOMMENDED)**
**How it works:**
1. User installs a **browser extension** (Chrome/Firefox)
2. Extension reads the full DOM when user visits a news page
3. Extension sends rendered HTML + metadata to your server
4. Server processes already-accessible content

**Advantages:**
- ✅ Users bypass paywalls they already have access to
- ✅ No server-side blocking issues
- ✅ Captures exactly what user sees (including personalized content)
- ✅ Perfectly aligns with your privacy-first philosophy: "users share what they can see"
- ✅ Leverages existing browser sessions/cookies

**Implementation:**
- Build a lightweight browser extension with Manifest V3
- Extension captures:
  ```javascript
  {
    url: window.location.href,
    title: document.title,
    html: document.documentElement.outerHTML,
    meta: extractMetaTags(),
    timestamp: Date.now(),
    userVote: null  // User rates before submitting
  }
  ```
- Server receives, archives, and enriches
- Extension can show "Share to Memoria.uy" button on news sites

**Privacy Design:**
- Extension only activates when user clicks "Share"
- No tracking, no data collection unless user explicitly shares
- Open source the extension for transparency

#### ✅ **Solution B: Residential Proxy Service (If you must scrape server-side)**
Services like **Bright Data** or **Oxylabs** provide residential IPs that look like real users.

**Costs (2025 pricing):**
- ~$10-15/GB bandwidth
- Typical article: ~500KB → ~$0.005-0.01 per article
- 1000 articles/month: ~$5-10/month

**Pros:** Works reliably, rotates IPs
**Cons:** Still gets blocked occasionally, costs scale with usage, ethical gray area

#### ❌ **Why Not Free Proxies:**
Your current implementation fetches free proxies from `free-proxy-list.net` and `geonode.com`. These are:
- 95%+ already blacklisted by major news sites
- Slow (100ms+ latency added)
- Unreliable (die mid-request)
- Security risk (MITM potential)

**Recommendation:** **Go with Solution A (Client-Side Capture)**. It's philosophically aligned with your project ("share what you can see"), bypasses all blocking, and creates a better UX (users can vote immediately while reading).

---

### Issue #2: Archive Services Are Slow

**Current Behavior:**
- Sync archive.ph POST: 2-30 seconds (blocks request)
- If "in progress": 3-9 minutes async retry (3 attempts × 3min)
- If not found: 5-15 minutes archive.org fallback (3 attempts × 5min)

**Why This Happens:**
- archive.ph must fetch, render, screenshot, and upload the page (CPU-intensive)
- archive.org has rate limits and queues for new saves
- You're doing this synchronously on user submission (bad UX)

**Modern Solutions (2025):**

#### ✅ **Solution A: Decouple Archive from User Flow (CURRENT BEST PRACTICE)**
**How it works:**
1. User submits URL → Instant success response (200ms)
2. Server queues archival as background job
3. User sees "Archiving in progress..." status
4. Celery worker handles archive + enrichment asynchronously
5. HTMX live updates when complete (WebSocket or polling)

**You already have 90% of this!** Just need to:
- Remove `noticia.find_archived()` from synchronous view code
- Always queue it as Celery task
- Add WebSocket or short-polling for status updates
- Show skeleton UI while enriching

**UX Flow:**
```
User submits → Instant "Saved! Archiving..." → (10-30s later) → Full card appears
```

**Why this works:**
- User isn't blocked waiting for archive
- Archive can retry without user noticing
- Meets expectation: "it'll be ready soon"

#### ✅ **Solution B: Skip Archive Entirely (RADICAL BUT VALID)**
**Question: Do you actually need archives?**

**If YES (for legal/permanence):**
- Use Solution A: async with status updates

**If NO (just want metadata):**
- Parse directly from submitted URL
- Use client-side capture (Issue #1 Solution A)
- Only archive "popular" articles (voted on by 3+ users)

**Hybrid Approach:**
- Always parse immediately from URL/client capture
- Archive opportunistically in background
- If archive fails, who cares? You have the content already

#### 🔍 **Solution C: Self-Hosted Archive (OVERKILL but possible)**
Use **ArchiveBox** (open source):
- Runs locally/on VPS
- Faster than public services (no queue)
- Full control over storage

**Costs:**
- Storage: ~1-5MB per article
- 10,000 articles = 10-50GB (~$1-2/month S3)

**Pros:** Fast, reliable, no API limits
**Cons:** Maintenance burden, doesn't solve paywall issue

**Recommendation:** **Solution A (Async + Status UI)**. Keep current archive strategy but make it fully async with proper user feedback. If you adopt client-side capture (Issue #1), archives become bonus/backup.

---

### Issue #3: LLM Parsing Costs

**Current Costs (2025 Reality Check):**

Your stack:
- **Gemini 2.0 Flash Lite** (HTML→Markdown): ~$0.00001-0.0001 per article
- **Mistral Saba** (Markdown→JSON): ~$0.00001-0.0001 per article

**Total per article: ~$0.0001-0.001** (1/100th of a penny to 1/10th of a penny)

**At scale:**
- 100 articles/day: **$0.03-0.30/month**
- 1000 articles/day: **$0.30-3/month**

**Critical Assessment:**
🎉 **THIS IS NOT AN ISSUE.** You already chose the cheapest viable models. LLM costs have fallen 90%+ since you started this project.

**However, you mentioned cheaper alternatives:**

#### Option A: **GLiNER2** (Local NER - Named Entity Recognition)
- **What it does:** Extracts entities (people, orgs, locations) from text
- **Cost:** $0 (runs locally or on your server)
- **Quality:** Good for Spanish if you use multilingual models
- **Limitation:** Only does NER, not summarization/categorization

**Use case:** Replace entity extraction in your `parse_noticia()` function

**Example:**
```python
from gliner import GLiNER

model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
entities = model.predict_entities(
    text,
    labels=["persona", "organizacion", "lugar"]
)
```

#### Option B: **LangExtract** (Google's Language Extraction)
- **What it does:** Rule-based extraction of structured data from articles
- **Cost:** $0
- **Quality:** Good for well-structured news (title, author, date, source)
- **Limitation:** No summarization, no sentiment, brittle on irregular layouts

**Use case:** Replace metadata extraction (title, author, date, source)

#### Hybrid Recommendation:
1. **LangExtract** for metadata (free, fast, 90% accurate)
2. **GLiNER2** for entity extraction (free, local)
3. **Gemini Flash Lite** for summary only (~$0.00005/article)
4. **Human curation** for sentiment (users vote, crowdsource sentiment)

**New cost:** ~$0.00005 per article = **$1.50/month for 1000 articles/day**

But honestly, your current costs are already negligible. Unless you're processing 100,000+ articles/month, don't optimize this yet.

---

## The Bigger Vision: Clarifying & Expanding

### What You're Building (Refined)

**Core Concept:**
A privacy-first platform to map collective sentiment polarization around news events.

**Key Insights:**
1. **Individual Layer:** News X is good/bad/neutral to me
2. **Consensus Layer:** Which news unite us? Which divide us?
3. **Clustering Layer:** Groups of people with aligned sentiment patterns
4. **Entity Layer:** Sentiment toward named individuals/orgs across clusters

**Novel Output:**
- "80% consensus: this is good news" (rare, interesting!)
- "55/45 split: polarizing story" (reveals fault lines)
- "People who liked News A tend to dislike News B" (cluster similarity)
- "Politician X: negative in Cluster 1, positive in Cluster 2" (reveals bias)

### Privacy-First Design (Your North Star)

**Principles:**
1. **No PII collection:** No names, emails, demographics beyond what user chooses
2. **Self-location:** Users see where they fall in clusters ("You're in the green cluster")
3. **Aggregate only:** Publish cluster insights, never individual votes
4. **User control:** Delete all data at any time
5. **Open source:** Full transparency

**Implementation:**
- Anonymous voting (session-based or pseudonymous accounts)
- Cluster visualization without identifying members
- Public API for aggregate stats only

### Polis Inspiration (What to Borrow)

**Polis** (pol.is) does this for comments/statements. You're doing it for news URLs.

**Borrow:**
- **PCA/t-SNE clustering** for visualizing opinion groups
- **Consensus statements:** "90% of all groups agree on this"
- **Bridging statements:** "This bridges two clusters"
- **Real-time updates:** Watch clusters form as votes come in

**Your unique addition:**
- **Entity sentiment layer:** Not just "do you agree with this news?", but "who is mentioned and how?"
- **Cross-article patterns:** "News about Topic X always divides us"
- **Source analysis:** "Source Y is trusted by Cluster 1, distrusted by Cluster 2"

---

## Proposed Architecture (2025 Edition)

### Phase 1: Minimal Viable Product (MVP)

**Goal:** Prove the core loop works with minimal complexity

**Features:**
1. Users submit URLs (no extension yet, just paste)
2. Server fetches metadata (title, image) from meta tags
3. Users vote: Good / Bad / Neutral
4. Display: Latest news with vote counts
5. Simple visualization: "X% good, Y% bad, Z% neutral"

**Tech Stack:**
- Keep Django + HTMX + Tailwind (works great)
- Skip LLM parsing initially (expensive, not core to MVP)
- Skip archiving (just store URL + metadata)
- SQLite or Supabase (you already support both)

**Timeline:** 2-3 days to clean up existing code and launch

### Phase 2: Browser Extension + Enrichment

**Goal:** Solve paywall issue and add entity/summary layer

**New Features:**
1. Browser extension for client-side capture
2. LLM enrichment (summary, entities, sentiment) via Celery
3. Entity pages: "Show me all news mentioning Politician X"
4. Sentiment filter: "News where X is mentioned positively"

**Tech Stack:**
- Extension: Manifest V3 (Chrome/Firefox)
- LLM: Keep Gemini Flash Lite + Mistral Saba (or add GLiNER2)
- Celery: Keep existing task queue

**Timeline:** 2-3 weeks

### Phase 3: Clustering & Visualization

**Goal:** Reveal polarization patterns

**New Features:**
1. Opinion clustering (PCA/t-SNE on user vote vectors)
2. Interactive cluster map (D3.js or Plotly)
3. "You are here" marker (show user their position)
4. Consensus/divisive metrics per article
5. Bridging news (liked across clusters)

**Tech Stack:**
- Backend: scikit-learn for clustering
- Frontend: D3.js or Plotly for viz
- Caching: Redis for precomputed clusters

**Timeline:** 3-4 weeks

### Phase 4: Public Dashboard & API

**Goal:** Make insights publicly accessible

**New Features:**
1. Public dashboard: No login required to see aggregate patterns
2. API: `/api/news/{id}/sentiment`, `/api/clusters`, etc.
3. Embeddable widgets: "Embed this news sentiment on your blog"
4. RSS/Atom feeds: "Polarizing news this week"

**Tech Stack:**
- Django REST Framework (already installed)
- CORS for embeds
- Rate limiting (django-ratelimit)

**Timeline:** 2-3 weeks

---

## Critical Technical Decisions

### 1. Client-Side vs Server-Side Capture

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Browser Extension** | Bypasses paywalls, no blocking, user sees what they share | Requires extension install, smaller user base initially | ✅ **START HERE** (Phase 2) |
| **Server-Side Scraping** | No install required, easier onboarding | Blocked by paywalls, expensive proxies, legal gray area | Use for MVP only, migrate to extension |

### 2. Archiving Strategy

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Async Public Archives** | Free, permanent record, legal safe harbor | Slow, unreliable | ✅ **Keep current, make fully async** |
| **Self-Hosted ArchiveBox** | Fast, reliable, full control | Maintenance, storage costs | Only if you hit 10k+ articles |
| **No Archiving** | Simple, fast | No permanence, links die | ❌ Don't do this (defeats "memoria" purpose) |

### 3. LLM Parsing vs Open Source

| Approach | Cost/Article | Quality | Maintenance | Recommendation |
|----------|--------------|---------|-------------|----------------|
| **Current (Gemini+Mistral)** | $0.0001-0.001 | High | Low | ✅ **Keep for now** |
| **Hybrid (LangExtract+GLiNER2+Gemini)** | $0.00005 | Medium-High | Medium | Optimize if costs >$10/month |
| **Fully Open (LangExtract+GLiNER2)** | $0 | Medium | High | Only if ideologically opposed to LLM APIs |

### 4. Database: SQLite vs Postgres

| Database | Pros | Cons | When to Use |
|----------|------|------|-------------|
| **SQLite** | Simple, file-based, no setup | Single writer, limited concurrency | ✅ MVP, <100 concurrent users |
| **Postgres (Supabase)** | Scalable, full-text search, JSON support | Requires setup, paid tier eventually | Production, >100 users |

**Recommendation:** Start SQLite, migrate to Supabase when you hit 50+ daily active users.

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Archive services rate-limit you** | High | Medium | Implement exponential backoff, cache aggressively |
| **LLM costs spike** | Low | Medium | Set budget alerts, fallback to open source |
| **Extension adoption is low** | High | High | Make web submission work well, extension is bonus |
| **Clustering doesn't reveal patterns** | Medium | High | Start with simple stats, add clustering only if data warrants |

### Product Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Not enough users to cluster** | High | High | Requires 100+ active users minimum; focus on growth |
| **Polarization reveals are depressing** | Medium | Medium | Frame as "finding common ground" not "exposing division" |
| **Privacy concerns scare users** | Low | High | Open source, clear privacy policy, no tracking |
| **Becomes echo chamber** | Medium | Medium | Surface bridging content, encourage cross-cluster dialogue |

### Legal Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Copyright issues (archiving)** | Low | High | Use public archives (archive.ph/org), fair use doctrine |
| **News sites block you** | High | Low | Extension solves this (user's browser, their access) |
| **Defamation (entity sentiment)** | Low | High | Aggregate only, clear disclaimer: "user opinions, not facts" |

---

## Go/No-Go Recommendation

### ✅ **GO - This Project is Worth Reviving**

**Why:**
1. **Technical issues are solved:** Client-side capture + async archiving + dirt-cheap LLMs
2. **Timing is right:** Polarization discourse is mainstream, people want tools to understand it
3. **Unique value:** No one else combines URL-level sentiment + entity analysis + clustering
4. **Low cost:** $5-20/month to run at 1000 articles/day (mostly Supabase if you outgrow SQLite)
5. **Aligned with your skills:** Django, HTMX, AI parsing—you already built 80% of this

**Critical Path:**
1. **Week 1-2:** Clean up existing code, deploy MVP (no LLM, just voting)
2. **Week 3-4:** Add async archiving with status UI
3. **Week 5-8:** Build browser extension for client-side capture
4. **Month 3:** LLM enrichment + entity pages
5. **Month 4:** Clustering + visualization

### Success Metrics (First 6 Months)

| Metric | Target | Notes |
|--------|--------|-------|
| **Articles Submitted** | 500+ | Proves people find it useful |
| **Active Voters** | 50+ | Minimum for clustering to work |
| **Vote Diversity** | 30%+ split on 20%+ of articles | Proves polarization exists |
| **Extension Installs** | 100+ | Validates client-side capture |
| **Cluster Emergence** | 3+ clear groups | Validates core hypothesis |

---

## Expanded Vision: What This Becomes

### Short Term (6 months)
- **"Sentiment Aggregator":** Like Product Hunt, but for news + opinion diversity
- **Use case:** "Is this news polarizing or consensus?"

### Medium Term (1-2 years)
- **"Polarization Dashboard":** Real-time map of what divides/unites us
- **Use case:** Journalists cite your cluster analysis in articles
- **Features:**
  - Weekly "Most Divisive News" report
  - "Bridging Stories" that got cross-cluster agreement
  - Entity reputation tracks (politician favorability over time)

### Long Term (2-5 years)
- **"Civic Discourse Infrastructure":** Powers deliberation platforms
- **Integrations:**
  - News sites embed your sentiment widget
  - Fact-checkers use entity sentiment to spot narratives
  - Researchers cite your dataset in polarization studies
- **Revenue:**
  - Freemium API (free tier: 1k requests/month, paid: unlimited)
  - Institutional subscriptions (universities, newsrooms)
  - Grants (civic tech, democracy initiatives)

---

## Next Steps (If You Decide to Go)

### Immediate (This Week)
1. ✅ Read this analysis, validate assumptions
2. 🔧 Audit codebase: What works? What's broken?
3. 📝 Write a simple privacy policy (even if just draft)
4. 🎯 Define MVP scope (my suggestion: just voting, no LLM)

### Week 1-2: MVP Launch
1. Strip down to essentials (remove broken features)
2. Fix sync archiving issue (make it fully async)
3. Deploy to production (DigitalOcean or Render)
4. Share with 10 friends: "Vote on news, see if we agree"

### Week 3-4: Validate Core Loop
1. Do people vote? (engagement metric)
2. Is there polarization? (vote split metric)
3. Do they come back? (retention metric)

### Month 2: Extension or Die
- If MVP shows promise → Build extension (solves paywall issue)
- If no one uses it → Pivot or kill project

**Decision point:** By Month 2, you know if this has legs.

---

## Final Thoughts

This project is **not just viable—it's timely**. The 2020s are defined by polarization discourse, and you're building infrastructure to map it quantitatively.

Your original blockers (paywalls, slow archives, LLM costs) are **solved problems in 2025**:
- Paywalls → Client-side capture (browser extension)
- Slow archives → Async + status UI (you already have Celery)
- LLM costs → Already negligible ($1-3/month at scale)

The real risk isn't technical—it's **product-market fit**. You need to find 50-100 people who care about this enough to vote regularly. That's a marketing/community problem, not an engineering one.

**My recommendation:**
1. **Ship the MVP in 2 weeks** (just voting, no LLM)
2. **Validate the loop** (do people vote? is there signal?)
3. **Build the extension** (if validation succeeds)
4. **Add clustering** (once you have 100+ users)

You've already done the hard work. Now it's about focus, iteration, and finding your first 100 believers.

**This project deserves to exist.** Go build it.

---

## Appendix A: Extended Vision Document

### The "Memoria.uy Manifesto" (Draft)

**Problem:**
Same news event can be celebrated by some, mourned by others. This gap—this *fundamental disagreement about reality*—is the defining crisis of modern media.

**Current Solutions (Insufficient):**
- **Fact-checkers:** "This is true/false" (but polarization persists even with facts)
- **Comment sections:** Toxic, unstructured, dominated by extremes
- **Polling:** Expensive, slow, doesn't capture nuance
- **Social media:** Algorithmic amplification of outrage

**What Memoria.uy Does Differently:**
1. **Structured sentiment collection:** Good/Bad/Neutral (simple, fast)
2. **URL-level granularity:** Specific articles, not abstract topics
3. **Entity-aware:** Not just "do you like this news?", but "who is mentioned and how?"
4. **Clustering, not demographics:** Group by *what you think*, not *who you are*
5. **Privacy-first:** No tracking, no PII, full transparency

**Core Insight:**
Most news is consensus ("everyone agrees this is good/bad"). The *outliers*—the 50/50 splits—reveal our actual fault lines. By mapping these, we map ourselves.

**Use Cases:**
- **Individual:** "Am I in the majority or minority on this?"
- **Journalist:** "Is my article bridging divides or widening them?"
- **Researcher:** "What topics polarize Society X in Year Y?"
- **Policymaker:** "Where can we find common ground?"

**Why It Matters:**
Democracy requires *some* shared reality. If we can't even agree on what's good/bad news, how do we deliberate? This tool doesn't solve polarization—it makes it *visible*, which is the first step.

---

## Appendix B: Technical Deep Dive (Browser Extension)

### Extension Architecture

**Manifest V3 (Chrome/Firefox compatible)**

```json
{
  "manifest_version": 3,
  "name": "Memoria.uy - Share & Vote on News",
  "version": "1.0.0",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["https://memoria.uy/*"],
  "action": {
    "default_popup": "popup.html",
    "default_icon": "icon.png"
  },
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content.js"]
  }]
}
```

**Content Script (content.js):**
```javascript
// Detect news sites (heuristic: og:type=article)
function isNewsArticle() {
  const ogType = document.querySelector('meta[property="og:type"]');
  return ogType && ogType.content === 'article';
}

// Extract metadata + full HTML
function captureArticle() {
  return {
    url: window.location.href,
    title: document.title,
    html: document.documentElement.outerHTML,
    meta: {
      title: getMeta('og:title') || getMeta('twitter:title'),
      image: getMeta('og:image') || getMeta('twitter:image'),
      description: getMeta('og:description'),
      author: getMeta('article:author'),
      published: getMeta('article:published_time')
    },
    timestamp: new Date().toISOString()
  };
}

function getMeta(property) {
  const el = document.querySelector(`meta[property="${property}"]`);
  return el ? el.content : null;
}

// Send to background script when user clicks "Share"
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'capture') {
    sendResponse(captureArticle());
  }
});
```

**Popup (popup.html):**
```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body { width: 300px; padding: 10px; font-family: sans-serif; }
    button { width: 100%; padding: 10px; margin: 5px 0; cursor: pointer; }
    .good { background: #4ade80; }
    .bad { background: #f87171; }
    .neutral { background: #94a3b8; }
  </style>
</head>
<body>
  <h3>How is this news?</h3>
  <button class="good" data-vote="buena">😊 Good News</button>
  <button class="bad" data-vote="mala">😞 Bad News</button>
  <button class="neutral" data-vote="neutral">😐 Neutral</button>
  <script src="popup.js"></script>
</body>
</html>
```

**Popup Script (popup.js):**
```javascript
document.querySelectorAll('button').forEach(btn => {
  btn.addEventListener('click', async () => {
    const vote = btn.dataset.vote;

    // Capture article from content script
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    const article = await chrome.tabs.sendMessage(tab.id, {action: 'capture'});

    // Send to Memoria.uy server
    const response = await fetch('https://memoria.uy/api/submit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...article, vote})
    });

    if (response.ok) {
      btn.textContent = '✅ Saved!';
      setTimeout(() => window.close(), 1000);
    }
  });
});
```

**Django API Endpoint:**
```python
# core/views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json

@csrf_exempt  # Use proper CSRF for production
def extension_submit(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        # Create/get Noticia
        noticia, created = Noticia.objects.get_or_create(
            enlace=data['url'],
            defaults={
                'meta_titulo': data['meta']['title'],
                'meta_imagen': data['meta']['image'],
                'agregado_por': request.user or get_anonymous_user()
            }
        )

        # Save vote
        Voto.objects.update_or_create(
            usuario=request.user or get_anonymous_user(),
            noticia=noticia,
            defaults={'opinion': data['vote']}
        )

        # Queue enrichment (async)
        if created:
            enrich_from_html.delay(noticia.id, data['html'])

        return JsonResponse({'status': 'ok', 'id': noticia.id})
```

**Why This Approach Wins:**
- User shares only what they can access (respects paywalls)
- Full HTML content = best quality parsing
- One-click voting (low friction)
- Works on any news site (no allowlist needed)
- Privacy-preserving (data sent only when user clicks)

---

## Appendix C: Cost Projections

### Scenario A: Hobbyist (100 articles/month)

| Item | Cost |
|------|------|
| **Hosting** (Render/Railway free tier) | $0 |
| **Database** (SQLite, local) | $0 |
| **Redis** (Upstash free tier, 10k requests) | $0 |
| **LLM** (100 articles × $0.001) | $0.10 |
| **Archive** (free services) | $0 |
| **Total** | **$0.10/month** |

### Scenario B: Growing (1000 articles/month, 50 users)

| Item | Cost |
|------|------|
| **Hosting** (Render Starter, 512MB) | $7 |
| **Database** (Supabase free tier, 500MB) | $0 |
| **Redis** (Upstash paid, 100k requests) | $3 |
| **LLM** (1000 articles × $0.001) | $1 |
| **Archive** (free services) | $0 |
| **Total** | **$11/month** |

### Scenario C: Sustainable (10k articles/month, 500 users)

| Item | Cost |
|------|------|
| **Hosting** (DigitalOcean 2GB droplet) | $12 |
| **Database** (Supabase Pro, 8GB) | $25 |
| **Redis** (Upstash paid, 1M requests) | $10 |
| **LLM** (10k articles × $0.001) | $10 |
| **Archive** (ArchiveBox S3 storage, 50GB) | $5 |
| **CDN** (Cloudflare free tier) | $0 |
| **Total** | **$62/month** |

### Scenario D: Scaled (100k articles/month, 5k users)

| Item | Cost |
|------|------|
| **Hosting** (DigitalOcean 4GB + workers) | $48 |
| **Database** (Supabase Pro, 100GB) | $100 |
| **Redis** (Upstash paid, 10M requests) | $40 |
| **LLM** (100k articles × $0.0005 w/ caching) | $50 |
| **Archive** (S3, 500GB) | $15 |
| **CDN** (Cloudflare Pro) | $20 |
| **Total** | **$273/month** |

**Revenue to Break Even (Scenario D):**
- 300 users paying $1/month (Patreon/donations)
- OR 10 institutional subscribers at $30/month
- OR API usage fees ($0.01 per request, 30k requests/month)

---

## Appendix D: Open Questions (For You to Answer)

1. **Who is your target user?**
   - General public? (hard to acquire)
   - Journalists/researchers? (easier to target, lower volume)
   - Students/academics? (mission-aligned, budget-constrained)

2. **What's your growth strategy?**
   - Organic (share on HN/Reddit, hope for viral)
   - Partnerships (integrate with news sites?)
   - Paid (ads? never)

3. **How do you handle spam/abuse?**
   - Require account for voting? (friction)
   - Rate limiting only? (bots will game it)
   - Invite-only initially? (slow growth, high quality)

4. **What's your end goal?**
   - Side project for personal learning?
   - Non-profit civic tech?
   - Startup (eventually monetize)?

5. **Do you have time/resources?**
   - 10 hours/week? (MVP in 2 months)
   - 40 hours/week? (MVP in 2 weeks, full product in 3 months)
   - Money to outsource? (hire help for frontend/extension)

**These answers determine your roadmap.** Think on them, then decide.

---

End of Analysis. Let's discuss your thoughts.
