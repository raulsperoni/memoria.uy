"""IP del cliente para django-ratelimit.

Detrás de Railway `REMOTE_ADDR` es el proxy, así que todos los votantes
compartirían un solo contador. Railway manda la IP del cliente en `X-Real-IP`
(docs.railway.com/networking/public-networking/specs-and-limits). Se usa solo
si viene y solo en producción: con `DEBUG` no hay proxy y cualquiera podría
mandar el header y esquivar el límite."""

from django.conf import settings


def ip_cliente(request) -> str:
    if getattr(settings, "RATELIMIT_CONFIAR_X_REAL_IP", False):
        real = request.META.get("HTTP_X_REAL_IP", "").strip()
        if real:
            return real
    return request.META.get("REMOTE_ADDR", "")


def clave(group, request) -> str:
    """`key` de `@ratelimit`."""
    return ip_cliente(request)
