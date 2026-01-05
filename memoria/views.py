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
