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


BOTS_IA = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User", "Claude-SearchBot",
    "anthropic-ai", "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended",
    "CCBot", "cohere-ai", "Meta-ExternalAgent", "Amazonbot", "DuckAssistBot", "MistralAI-User",
]
# Lo que no debe indexarse: resultados de búsqueda, votos y páginas personales, admin.
NO_INDEXAR = [
    "/admin/",
    "/accounts/",
    "/buscar/",
    "/hoy/resultado/",
    "/hoy/votar/",
    "/p/",
    "/h/*/opinar/",
]


def robots_txt(request):
    """robots.txt: se puede leer todo lo público, también con IA (el objetivo
    es que nos citen). Ver docs/decisiones/0015-politica-de-ia-y-licencia.md."""
    reglas = ["Allow: /"] + [f"Disallow: {p}" for p in NO_INDEXAR]
    lines = [
        "# memoria.uy: archivo abierto de noticias uruguayas, con fuentes.",
        "# Política de IA: los crawlers y agentes de IA pueden leer, indexar y citar todo lo público.",
        "# Hechos, resúmenes y datos: CC BY 4.0 (citar a memoria.uy). Detalle en https://memoria.uy/llms.txt",
        "",
        "User-agent: *",
        "Content-Signal: search=yes, ai-input=yes, ai-train=yes",
        *reglas,
        "",
        "# Crawlers de IA, declarados a propósito (un grupo propio ignora el de *, por eso se repiten las reglas)",
        *[f"User-agent: {b}" for b in BOTS_IA],
        *reglas,
        "",
        "Sitemap: https://memoria.uy/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def llms_txt(request):
    """llms.txt: qué es el sitio, dónde están los datos y bajo qué licencia."""
    from django.shortcuts import render

    return render(request, "llms.txt", content_type="text/plain; charset=utf-8")


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
// memoria.uy — service worker mínimo: red primero; sin red, la copia guardada o una página offline.
const CACHE = 'memoria-v2';
const OFFLINE = '/offline/';
// Páginas que dependen de la sesión o del día: nunca se guardan.
const NO_GUARDAR = ['/accounts/', '/admin/', '/hoy/', '/p/', '/perfil', '/profile'];
self.addEventListener('install', e => e.waitUntil(
  caches.open(CACHE).then(c => c.add(OFFLINE)).then(() => self.skipWaiting())
));
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())
));
self.addEventListener('fetch', e => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  if (NO_GUARDAR.some(p => url.pathname.startsWith(p))) return;
  const navegacion = req.mode === 'navigate';
  e.respondWith(
    fetch(req).then(res => {
      if (res.ok && (navegacion || url.pathname.startsWith('/static/'))) {
        const copia = res.clone();
        caches.open(CACHE).then(c => c.put(req, copia));
      }
      return res;
    }).catch(() => caches.match(req).then(r => r || (navegacion ? caches.match(OFFLINE) : Response.error())))
  );
});
"""


def service_worker(request):
    from django.http import HttpResponse

    resp = HttpResponse(SERVICE_WORKER, content_type="application/javascript")
    resp["Cache-Control"] = "no-cache"
    return resp


def offline(request):
    from django.shortcuts import render

    return render(request, "offline.html")
