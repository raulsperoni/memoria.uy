# sitemaps.py

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from core.models import Noticia


class NoticiaSitemap(Sitemap):
    """Sitemap for news articles."""

    changefreq = "daily"
    priority = 0.8

    def items(self):
        """Return all noticias ordered by date."""
        return Noticia.objects.all().order_by("-fecha_agregado")

    def lastmod(self, obj):
        """Return last modification date."""
        return obj.fecha_agregado

    def location(self, obj):
        """Return the absolute URL for each noticia."""
        return obj.get_absolute_url()


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages."""

    priority = 0.5
    changefreq = "monthly"

    def items(self):
        """Return list of static page URL names."""
        return ["timeline", "acerca_de", "privacidad", "bienvenida"]

    def location(self, item):
        """Return the absolute URL for each static page."""
        return reverse(item)


class HistoriaSitemap(Sitemap):
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


class CambioSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        from archivo.models import Cambio

        return Cambio.objects.order_by("-detectado_en")

    def lastmod(self, obj):
        return obj.detectado_en

    def location(self, obj):
        return reverse("archivo:cambio", args=[obj.pk])


class EntidadSitemap(Sitemap):
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
