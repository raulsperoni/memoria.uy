from django.http import JsonResponse, HttpResponse
from django.views.static import serve
from django.conf import settings
import os

def health_check(request):
    """
    Simple health check endpoint for Docker healthcheck.
    Returns a 200 OK response to indicate the service is healthy.
    """
    return JsonResponse({"status": "healthy"})


def favicon(request):
    """Serve favicon from static files"""
    return serve(
        request,
        'core/favicon.ico',
        document_root=os.path.join(settings.BASE_DIR, 'core/static')
    )


def robots_txt(request):
    """Generate robots.txt file for search engine crawlers."""
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "# Sitemaps",
        "Sitemap: https://memoria.uy/sitemap.xml",
        "",
        "# Disallow admin and API endpoints",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /accounts/",
        "",
        "# Allow crawling of public pages",
        "Allow: /noticias/",
        "Allow: /acerca-de/",
        "Allow: /privacidad/",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def manifest(request):
    """Web App Manifest (PWA instalable)."""
    from django.http import JsonResponse
    from django.templatetags.static import static

    return JsonResponse(
        {
            "name": "memoria.uy",
            "short_name": "memoria.uy",
            "description": "Lo que pasó en Uruguay, con fuentes. Y lo que pensamos.",
            "start_url": "/?pwa=1",
            "scope": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#000000",
            "lang": "es-UY",
            "icons": [
                {"src": static("core/icons/icon-256.png"), "sizes": "256x256", "type": "image/png"},
                {"src": static("core/icons/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            ],
        },
        content_type="application/manifest+json",
        json_dumps_params={"ensure_ascii": False},
    )


SERVICE_WORKER = """
// memoria.uy — service worker mínimo: red primero, caché como respaldo offline.
const CACHE = 'memoria-v1';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())
));
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  e.respondWith(
    fetch(req).then(res => {
      if (res.ok && (req.mode === 'navigate' || req.url.includes('/static/'))) {
        const copia = res.clone();
        caches.open(CACHE).then(c => c.put(req, copia));
      }
      return res;
    }).catch(() => caches.match(req).then(r => r || caches.match('/')))
  );
});
"""


def service_worker(request):
    from django.http import HttpResponse

    resp = HttpResponse(SERVICE_WORKER, content_type="application/javascript")
    resp["Cache-Control"] = "no-cache"
    return resp
