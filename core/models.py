# models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from core import parse
import logging

logger = logging.getLogger(__name__)


class Noticia(models.Model):
    """
    A news article submitted by a user (or anonymously).
    Stores the original URL and metadata extracted from meta tags.
    """
    enlace = models.URLField(unique=True, help_text="Original news article URL")

    # Metadata extracted from og: / twitter: tags
    meta_titulo = models.CharField(max_length=255, blank=True, null=True)
    meta_imagen = models.URLField(blank=True, null=True)
    meta_descripcion = models.TextField(blank=True, null=True)

    fecha_agregado = models.DateTimeField(auto_now_add=True)

    # Optional: Who submitted this (can be anonymous)
    agregado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who submitted (null if anonymous)"
    )

    def __str__(self):
        return self.meta_titulo or self.enlace

    @property
    def mostrar_titulo(self):
        """Display title with fallback chain."""
        return self.meta_titulo or self.enlace

    @property
    def mostrar_imagen(self):
        """Display image, filtering out generic logos."""
        if self.meta_imagen and "meta/la-diaria-1000x1000" not in self.meta_imagen:
            return self.meta_imagen
        return None

    @property
    def mostrar_fecha(self):
        """Display date (just submission date for MVP)."""
        return self.fecha_agregado

    def update_meta_from_url(self):
        """
        Fetch title, image, and description from original URL meta tags.
        Fast, synchronous operation (just HTTP HEAD + parse <meta> tags).
        """
        title, image = parse.parse_from_meta_tags(self.enlace)
        if title:
            self.meta_titulo = title
        if image:
            self.meta_imagen = image
        # TODO: Also extract og:description
        self.save()


class Voto(models.Model):
    """
    User vote on a news article.
    Can be anonymous (session-based) or authenticated (user account).
    """
    # Either usuario OR session_key must be set (not both, not neither)
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Authenticated user (null if anonymous)"
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text="Session ID for anonymous votes"
    )

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
        constraints = [
            # One vote per user per article (if authenticated)
            models.UniqueConstraint(
                fields=['usuario', 'noticia'],
                condition=models.Q(usuario__isnull=False),
                name='unique_user_vote'
            ),
            # One vote per session per article (if anonymous)
            models.UniqueConstraint(
                fields=['session_key', 'noticia'],
                condition=models.Q(session_key__isnull=False),
                name='unique_session_vote'
            )
        ]

    def __str__(self):
        voter = self.usuario.username if self.usuario else f"Anon-{self.session_key[:8]}"
        return f"{voter} - {self.opinion} - {self.noticia}"

    @property
    def is_anonymous(self):
        """Check if this is an anonymous vote."""
        return self.usuario is None

    def clean(self):
        """Validate that either usuario or session_key is set, not both."""
        if not self.usuario and not self.session_key:
            raise ValidationError("Vote must have either usuario or session_key")
        if self.usuario and self.session_key:
            raise ValidationError("Vote cannot have both usuario and session_key")


class Entidad(models.Model):
    """
    Named entity extracted from news (person, organization, location, etc.)
    Currently unused in MVP (requires LLM enrichment).
    """
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
    """
    Link between a news article and an entity, with sentiment.
    Currently unused in MVP (requires LLM enrichment).
    """
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
        return f"{self.noticia} - {self.entidad.nombre}"
