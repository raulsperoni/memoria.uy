# models.py

from django.db import models
from django.contrib.auth.models import User
from core import archive
import logging

logger = logging.getLogger(__name__)


class Noticia(models.Model):
    titulo = models.CharField(max_length=255, null=True)
    enlace = models.URLField(unique=True)
    archivo_url = models.URLField(blank=True, null=True)
    archivo_fecha = models.DateTimeField(blank=True, null=True)
    archivo_imagen = models.URLField(blank=True, null=True)
    fuente = models.CharField(max_length=255, null=True)
    categoria = models.CharField(
        max_length=100,
        choices=[
            ("politica", "Política"),
            ("economia", "Economía"),
            ("salud", "Salud"),
            ("educacion", "Educación"),
            ("otros", "Otros"),
     ***REMOVED***,
    )
    agregado_por = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.titulo:
            return self.titulo
        return self.enlace

    def get_archive(self):
        try:
            archive_url, archive_metadata = archive.capture(self.enlace)
            self.archivo_url = archive_url
            self.archivo_imagen = archive_metadata.get("screenshot_url")
            self.archivo_fecha = archive_metadata.get("archive_date")
            self.titulo = archive_metadata.get("title")
            logger.info(f"Archived ***REMOVED***self.enlace***REMOVED*** to ***REMOVED***archive_url***REMOVED***")
        except archive.ArchiveInProgress as e:
            logger.warning(e)
        except archive.ArchiveFailure as e:
            logger.error(e)
        except Exception as e:
            logger.error(
                f"Error archiving ***REMOVED***self.enlace if 'noticia' in locals() else ''***REMOVED***: ***REMOVED***e***REMOVED***"
            )

    def save(self, *args, **kwargs):
        # Save the object first so we have an ID
        if not self.archivo_url:
            self.get_archive()
        super().save(*args, **kwargs)


class Voto(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE, related_name="votos")
    opinion = models.CharField(
        max_length=10,
        choices=[
            ("buena", "Buena noticia"),
            ("mala", "Mala noticia"),
            ("neutral", "Neutral"),
     ***REMOVED***,
    )
    fecha_voto = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("usuario", "noticia")

    def __str__(self):
        return f"***REMOVED***self.usuario.username***REMOVED*** - ***REMOVED***self.opinion***REMOVED*** - ***REMOVED***self.noticia.titulo***REMOVED***"
