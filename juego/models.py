"""
Juego diario "¿Qué piensa Uruguay?": 5 proposiciones por día. Por cada una
el votante opina (acuerdo / desacuerdo / no sé) y predice qué % de Uruguay
está de acuerdo. Ver docs/PLAN_2027.md §7.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from archivo.models import Proposicion

# Buckets de predicción del % de acuerdo
BUCKETS = [(0, "0–20 %"), (1, "20–40 %"), (2, "40–60 %"), (3, "60–80 %"), (4, "80–100 %")]


def bucket_de(pct: float) -> int:
    """0..100 → 0..4 (100 cae en el último)."""
    return min(4, int(pct // 20))


class Jornada(models.Model):
    fecha = models.DateField(unique=True, default=timezone.localdate)
    proposiciones = models.ManyToManyField(
        Proposicion, through="JornadaItem", related_name="jornadas"
    )
    publicada = models.BooleanField(default=False)
    curada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"Jornada {self.fecha:%d/%m/%Y}"

    def items_ordenados(self):
        return self.items.select_related("proposicion__historia").order_by("orden")


class JornadaItem(models.Model):
    jornada = models.ForeignKey(Jornada, on_delete=models.CASCADE, related_name="items")
    proposicion = models.ForeignKey(Proposicion, on_delete=models.CASCADE)
    orden = models.PositiveSmallIntegerField(default=0)
    recurrente = models.BooleanField(default=False, help_text="Tema de semanas anteriores")

    class Meta:
        ordering = ["orden"]
        unique_together = ("jornada", "proposicion")


class VotoProposicion(models.Model):
    OPINIONES = [
        ("acuerdo", "De acuerdo"),
        ("desacuerdo", "En desacuerdo"),
        ("nose", "No sé"),
    ]

    proposicion = models.ForeignKey(Proposicion, on_delete=models.CASCADE, related_name="votos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    opinion = models.CharField(max_length=10, choices=OPINIONES)
    prediccion = models.PositiveSmallIntegerField(null=True, blank=True, choices=BUCKETS)
    jornada = models.ForeignKey(
        Jornada, null=True, blank=True, on_delete=models.SET_NULL, related_name="votos"
    )
    creado_en = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposicion", "usuario"],
                condition=models.Q(usuario__isnull=False),
                name="voto_prop_unico_usuario",
            ),
            models.UniqueConstraint(
                fields=["proposicion", "session_key"],
                condition=models.Q(session_key__isnull=False),
                name="voto_prop_unico_sesion",
            ),
        ]

    def __str__(self):
        return f"{self.get_opinion_display()} · {self.proposicion_id}"
