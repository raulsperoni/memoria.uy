# models.py

from django.db import models
from django.contrib.auth.models import User
from core import parse
from core import archive_ph as archive
import logging

logger = logging.getLogger(__name__)


class Noticia(models.Model):
    enlace = models.URLField(unique=True)

    meta_titulo = models.CharField(max_length=255, blank=True, null=True)
    meta_imagen = models.URLField(blank=True, null=True)

    archivo_titulo = models.CharField(max_length=255, blank=True, null=True)
    archivo_url = models.URLField(blank=True, null=True)
    archivo_fecha = models.DateTimeField(blank=True, null=True)
    archivo_imagen = models.URLField(blank=True, null=True)

    markdown = models.TextField(blank=True, null=True)

    titulo = models.CharField(max_length=255, blank=True, null=True)
    fuente = models.CharField(max_length=255, null=True)
    categoria = models.CharField(
        max_length=100,
        choices=[
            ("politica", "Política"),
            ("economia", "Economía"),
            ("seguridad", "Seguridad"),
            ("salud", "Salud"),
            ("educacion", "Educación"),
            ("otros", "Otros"),
        ],
    )
    resumen = models.TextField(blank=True, null=True)

    agregado_por = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.titulo:
            return self.titulo
        return self.enlace

    @property
    def mostrar_titulo(self):
        return self.titulo or self.archivo_titulo or self.meta_titulo

    @property
    def mostrar_imagen(self):
        if self.meta_imagen and "meta/la-diaria-1000x1000" not in self.meta_imagen:
            return self.meta_imagen or self.archivo_imagen
        return self.archivo_imagen or self.meta_imagen

    def update_title_image_from_original_url(self):
        title, image_url = parse.parse_from_meta_tags(self.enlace)
        if title:
            self.meta_titulo = title
        if image_url:
            self.meta_imagen = image_url
        self.save()

    def update_title_image_from_archive(self):
        if self.archivo_url:
            title, image_url = parse.parse_from_meta_tags(self.archivo_url)
            if title:
                self.archivo_titulo = title
            if image_url:
                self.archivo_imagen = image_url
            self.save()
        else:
            self.update_title_image_from_original_url()

    def find_archived(self):
        try:
            self.archivo_url, html = archive.get_latest_snapshot(self.enlace)
            self.save()
            if not self.markdown:
                # Enrich the markdown content asynchronously
                from core.tasks import enrich_markdown

                enrich_markdown.delay(self.id, html)
            self.update_title_image_from_archive()
            return self.archivo_url
        except (archive.ArchiveNotFound, archive.ArchiveInProgress) as e:
            logger.error(f"Error finding archived URL: {e}")
            return None


class Voto(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE, related_name="votos")
    opinion = models.CharField(
        max_length=10,
        choices=[
            ("buena", "Buena noticia"),
            ("mala", "Mala noticia"),
            ("neutral", "Neutral"),
        ],
    )
    fecha_voto = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("usuario", "noticia")

    def __str__(self):
        return f"{self.usuario.username} - {self.opinion} - {self.noticia.titulo}"


class Entidad(models.Model):
    nombre = models.CharField(max_length=255)
    tipo = models.CharField(
        max_length=100,
        choices=[
            ("persona", "Persona"),
            ("organizacion", "Organización"),
            ("lugar", "Lugar"),
            ("otro", "Otro"),
        ],
    )

    def __str__(self):
        return self.nombre


class NoticiaEntidad(models.Model):
    noticia = models.ForeignKey(
        Noticia, on_delete=models.CASCADE, related_name="entidades"
    )
    entidad = models.ForeignKey(Entidad, on_delete=models.CASCADE)
    sentimiento = models.CharField(
        max_length=10,
        choices=[
            ("positivo", "Positivo"),
            ("negativo", "Negativo"),
            ("neutral", "Neutral"),
        ],
    )

    class Meta:
        unique_together = ("noticia", "entidad")

    def __str__(self):
        return f"{self.noticia.titulo} -{self.entidad.nombre}"
