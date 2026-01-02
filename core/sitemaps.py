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
