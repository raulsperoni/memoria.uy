from django.db import models
from django.contrib.auth.models import User


class Noticia(models.Model):
    titulo = models.CharField(max_length=255)
    enlace = models.URLField(unique=True)
    archivo_url = models.URLField(blank=True, null=True)
    archivo_fecha = models.DateTimeField(blank=True, null=True)
    archivo_imagen = models.URLField(blank=True, null=True)
    fecha_publicacion = models.DateField()
    fuente = models.CharField(max_length=255)
    categoria = models.CharField(
        max_length=100,
        choices=[
            ("politica", "Política"),
            ("economia", "Economía"),
            ("salud", "Salud"),
            ("educacion", "Educación"),
            ("otros", "Otros"),
        ],
    )
    agregado_por = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        # Save the object first so we have an ID
        super().save(*args, **kwargs)
        if not self.archivo_url:
            from core.tasks import archive_url_async

            archive_url_async.delay(self.pk)


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
