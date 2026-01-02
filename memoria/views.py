from django.http import JsonResponse, HttpResponse

def health_check(request):
    """
    Simple health check endpoint for Docker healthcheck.
    Returns a 200 OK response to indicate the service is healthy.
    """
    return JsonResponse({"status": "healthy"})


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
