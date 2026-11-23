"""Modelos compartidos. El archivo y el juego viven en sus propias apps."""

from django.db import models


def normalize_entity_name(name: str) -> str:
    """
    Normalize entity name for deduplication.
    - Lowercase
    - Remove accents/diacritics
    - Strip whitespace
    """
    import unicodedata
    # Normalize unicode, decompose accents, remove combining chars
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.lower().strip()


class Entidad(models.Model):
    """
    Persona, organización o lugar que aparece en los hechos del archivo
    (archivo.Hecho.entidades, archivo.Proposicion.entidades).
    """
    nombre = models.CharField(max_length=255)
    normalized_name = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Normalized name for deduplication (lowercase, no accents)"
    )
    tipo = models.CharField(
        max_length=100,
        choices=[
            ("persona", "Persona"),
            ("organizacion", "Organización"),
            ("lugar", "Lugar"),
            ("otro", "Otro"),
        ],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['normalized_name', 'tipo'],
                name='unique_normalized_entity'
            )
        ]

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_entity_name(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre
