# sitemaps.py

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class _Https(Sitemap):
    protocol = "https"  # no depender de que el proxy avise el esquema


class StaticViewSitemap(_Https):
    """Sitemap for static pages."""

    priority = 0.5
    changefreq = "monthly"

    def items(self):
        """Return list of static page URL names."""
        return ["archivo:home", "juego:hoy", "juego:burbujas", "archivo:cambios", "archivo:datos", "acerca_de", "privacidad"]

    def location(self, item):
        """Return the absolute URL for each static page."""
        return reverse(item)


class HistoriaSitemap(_Https):
    changefreq = "weekly"
    priority = 0.9
    limit = 5000

    def items(self):
        from archivo.models import Historia

        return (
            Historia.objects.filter(procesada_en__isnull=False, slug__isnull=False)
            .order_by("-primera_fuente_en")
        )

    def lastmod(self, obj):
        return obj.procesada_en

    def location(self, obj):
        return reverse("archivo:historia", args=[obj.slug])


class CambioSitemap(_Https):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        from archivo.models import Cambio

        return Cambio.objects.order_by("-detectado_en")

    def lastmod(self, obj):
        return obj.detectado_en

    def location(self, obj):
        return reverse("archivo:cambio", args=[obj.pk])


class EntidadSitemap(_Https):
    changefreq = "daily"
    priority = 0.7

    def items(self):
        from django.db.models import Count

        from core.models import Entidad

        return (
            Entidad.objects.annotate(n=Count("hechos"))
            .filter(n__gt=0)
            .order_by("pk")
        )

    def location(self, obj):
        from django.utils.text import slugify

        return reverse("archivo:entidad-slug", args=[obj.pk, slugify(obj.nombre) or "x"])
