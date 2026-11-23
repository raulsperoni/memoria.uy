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


# ---------------------------------------------------------------------------
# Burbujas (clustering Polis-style sobre proposiciones)
# ---------------------------------------------------------------------------


class BurbujaRun(models.Model):
    creada_en = models.DateTimeField(auto_now_add=True)
    n_votantes = models.PositiveIntegerField(default=0)
    n_proposiciones = models.PositiveIntegerField(default=0)
    k = models.PositiveSmallIntegerField(default=0)
    silhouette = models.FloatField(null=True, blank=True)
    varianza = models.JSONField(default=list, blank=True)
    parametros = models.JSONField(default=dict, blank=True)
    estado = models.CharField(max_length=20, default="ok")  # ok / insuficiente / error
    mensaje = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-creada_en"]

    def __str__(self):
        return f"Run {self.pk} · {self.k} burbujas · {self.n_votantes} votantes"


class Burbuja(models.Model):
    run = models.ForeignKey(BurbujaRun, on_delete=models.CASCADE, related_name="burbujas")
    numero = models.PositiveSmallIntegerField()
    nombre = models.CharField(max_length=80, blank=True)
    descripcion = models.CharField(max_length=300, blank=True)
    tamano = models.PositiveIntegerField(default=0)
    cx = models.FloatField(default=0)
    cy = models.FloatField(default=0)

    class Meta:
        ordering = ["run", "numero"]
        unique_together = ("run", "numero")

    def __str__(self):
        return self.nombre or f"Burbuja {'ABCDEFGH'[self.numero]}"

    @property
    def letra(self):
        return "ABCDEFGH"[self.numero]


class BurbujaMiembro(models.Model):
    run = models.ForeignKey(BurbujaRun, on_delete=models.CASCADE, related_name="miembros")
    burbuja = models.ForeignKey(Burbuja, on_delete=models.CASCADE, related_name="miembros")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    x = models.FloatField()
    y = models.FloatField()


class BurbujaPatron(models.Model):
    """Cómo votó una burbuja una proposición."""

    run = models.ForeignKey(BurbujaRun, on_delete=models.CASCADE, related_name="patrones")
    burbuja = models.ForeignKey(Burbuja, on_delete=models.CASCADE, related_name="patrones")
    proposicion = models.ForeignKey(Proposicion, on_delete=models.CASCADE, related_name="patrones_burbuja")
    acuerdo = models.PositiveIntegerField(default=0)
    desacuerdo = models.PositiveIntegerField(default=0)
    nose = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("burbuja", "proposicion")

    @property
    def opinan(self):
        return self.acuerdo + self.desacuerdo

    @property
    def pct_acuerdo(self):
        return 100 * self.acuerdo / self.opinan if self.opinan else None

    @property
    def pct_desacuerdo(self):
        return 100 - self.pct_acuerdo if self.opinan else None
