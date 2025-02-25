# models.py

from django.db import models
from django.contrib.auth.models import User
from core import archive
import logging
from bs4 import BeautifulSoup
import requests

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

    def get_title_from_meta_tags(self):
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/90.0.4430.93 Safari/537.36"
                )
            }

            response = requests.get(self.enlace, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract Open Graph meta tags
            og_title = soup.find("meta", property="og:title")
            og_image = soup.find("meta", property="og:image")

            title = og_title["content"] if og_title else "No title found"
            image = og_image["content"] if og_image else "No image found"
            logger.warning(f"Title: {title}, Image: {image}")
            self.titulo = title
            self.archivo_imagen = image

        except Exception as e:
            logger.error(f"Error getting title from meta tags: {e}")

    def get_archive(self):
        try:
            archive_url, archive_metadata, html = archive.capture(self.enlace)
            self.archivo_url = archive_url
            self.archivo_imagen = archive_metadata.get("screenshot_url")
            self.archivo_fecha = archive_metadata.get("archive_date")
            self.titulo = archive_metadata.get("title")
            logger.info(f"Archived {self.enlace} to {archive_url}")
            from core.tasks import parse

            parse.delay(self.id, html)
        except archive.ArchiveInProgress as e:
            logger.warning(e)
        except archive.ArchiveFailure as e:
            logger.error(e)
        except Exception as e:
            logger.error(
                f"Error archiving {self.enlace if 'noticia' in locals() else ''}: {e}"
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
