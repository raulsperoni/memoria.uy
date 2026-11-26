"""Feeds Atom: historias nuevas y notas editadas. Solo título, resumen propio
y enlace; nunca el cuerpo de las notas."""

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Atom1Feed

from .models import Cambio, Historia


class _Atom(Feed):
    feed_type = Atom1Feed
    author_name = "memoria.uy"
    author_link = settings.SITE_URL + "/"
    feed_copyright = f"{settings.LICENCIA_NOMBRE} (hechos y resúmenes de memoria.uy). Las notas pertenecen a sus medios."

    def link(self):
        return settings.SITE_URL + "/"

    def feed_url(self):
        return settings.SITE_URL + self.ruta

    def feed_guid(self):
        return settings.SITE_URL + self.ruta


class FeedHistorias(_Atom):
    ruta = "/feed.xml"
    title = "memoria.uy · historias nuevas"
    subtitle = "Lo que pasó en Uruguay, con fuentes: las últimas historias, con sus hechos verificados."
    description = subtitle

    def items(self):
        return (
            Historia.objects.filter(procesada_en__isnull=False, slug__isnull=False)
            .order_by("-procesada_en")[:30]
        )

    def item_title(self, h):
        return h.titulo

    def item_description(self, h):
        return h.resumen

    def item_link(self, h):
        return settings.SITE_URL + reverse("archivo:historia", args=[h.slug])

    def item_pubdate(self, h):
        return h.primera_fuente_en

    def item_updateddate(self, h):
        return h.procesada_en

    def item_categories(self, h):
        return [h.get_categoria_display()] if h.categoria else []


class FeedCambios(_Atom):
    ruta = "/cambios/feed.xml"
    title = "memoria.uy · notas editadas"
    subtitle = "Notas que un medio cambió o despublicó después de publicarlas."
    description = subtitle

    def items(self):
        return Cambio.objects.select_related("fuente__medio").order_by("-detectado_en")[:30]

    def item_title(self, c):
        return f"{c.fuente.medio.nombre}: {c.get_tipo_display()} · {c.titulo_despues or c.titulo_antes or c.fuente.titulo}"

    def item_description(self, c):
        return " ".join(x for x in (c.frase, c.resumen) if x)

    def item_link(self, c):
        return settings.SITE_URL + reverse("archivo:cambio", args=[c.pk])

    def item_pubdate(self, c):
        return c.detectado_en
