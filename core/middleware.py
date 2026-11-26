"""Cache-Control para el HTML público y anónimo."""

# Páginas que no dependen de quién mira. Si un día una muestra algo del
# votante, sale de esta lista.
VISTAS_PUBLICAS = {
    "archivo:home",
    "archivo:hoy",
    "archivo:dia",
    "archivo:historia",
    "archivo:historia-md",
    "archivo:historia-json",
    "archivo:entidad-slug",
    "archivo:tema",
    "archivo:cambios",
    "archivo:cambio",
    "archivo:medio",
    "archivo:datos",
    "archivo:feed",
    "archivo:feed-cambios",
    "acerca_de",
    "privacidad",
    "llms_txt",
    "robots_txt",
    "django.contrib.sitemaps.views.sitemap",
}

CACHE_PUBLICO = "public, max-age=60, s-maxage=300, stale-while-revalidate=600"


class CachePublicoMiddleware:
    """Un GET anónimo (sin cookie de sesión) a una página pública, que no
    puso cookies en la respuesta, se puede guardar un rato en un CDN. Con
    sesión, o si la respuesta setea cookies, no se toca el header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.method in ("GET", "HEAD")
            and response.status_code == 200
            and not response.has_header("Cache-Control")
            and not response.cookies
            and "sessionid" not in request.COOKIES
            and not request.META.get("HTTP_AUTHORIZATION")
            and request.resolver_match
            and request.resolver_match.view_name in VISTAS_PUBLICAS
        ):
            response["Cache-Control"] = CACHE_PUBLICO
        return response
