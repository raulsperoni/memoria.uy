"""
Archivo: noticias uruguayas capturadas automáticamente, agrupadas en
Historias, con Hechos (con procedencia) y Proposiciones (opinables).

Ver docs/PLAN_2027.md.
"""

import hashlib

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


class Medio(models.Model):
    TIPO_CHOICES = [("medio", "Medio"), ("oficial", "Fuente oficial")]

    nombre = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    dominio = models.CharField(max_length=255, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="medio")
    rss_urls = models.JSONField(default=list, blank=True)
    sitemap_urls = models.JSONField(default=list, blank=True)
    secciones_incluidas = models.JSONField(
        default=list, blank=True, help_text="Patrones de path; vacío = todas"
    )
    secciones_excluidas = models.JSONField(default=list, blank=True)
    activo = models.BooleanField(default=True)
    pago = models.BooleanField(default=False, help_text="Tiene paywall")
    lineas_repetidas = models.JSONField(
        default=list, blank=True, help_text="Líneas que el medio repite en todas sus notas (avisos, muro de pago); se sacan del texto"
    )
    ultimo_descubrimiento = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "medios"

    def __str__(self):
        return self.nombre


class Historia(models.Model):
    CATEGORIAS = [
        ("politica", "Política"),
        ("economia", "Economía"),
        ("seguridad", "Seguridad"),
        ("salud", "Salud"),
        ("educacion", "Educación"),
        ("sociedad", "Sociedad"),
        ("internacional", "Internacional"),
        ("otros", "Otros"),
    ]
    ESTADOS = [("abierta", "Abierta"), ("cerrada", "Cerrada")]

    titulo = models.CharField(max_length=300, blank=True)
    slug = models.SlugField(max_length=120, unique=True, null=True, blank=True)
    resumen = models.TextField(blank=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, blank=True)
    primera_fuente_en = models.DateTimeField(default=timezone.now, db_index=True)
    ultima_fuente_en = models.DateTimeField(default=timezone.now)
    n_medios = models.PositiveIntegerField(default=0)
    centroide = models.JSONField(default=list, blank=True)
    n_embeddings = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="abierta")
    relevancia = models.FloatField(
        null=True, blank=True, help_text="Decisión tipada: ¿vale una historia?"
    )
    procesada_en = models.DateTimeField(null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ultima_fuente_en"]
        verbose_name_plural = "historias"

    def __str__(self):
        return self.titulo or f"Historia #{self.pk}"

    def asignar_slug(self):
        if self.slug or not self.titulo:
            return
        base = slugify(self.titulo)[:100] or "historia"
        slug, n = base, 2
        while Historia.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base}-{n}"
            n += 1
        self.slug = slug

    def recalcular_n_medios(self):
        self.n_medios = (
            self.fuentes.filter(medio__tipo="medio")
            .values("medio")
            .distinct()
            .count()
        )


class Fuente(models.Model):
    ESTADOS = [
        ("descubierta", "Descubierta"),
        ("descartada", "Descartada"),
        ("extraida", "Extraída"),
        ("procesada", "Procesada"),
        ("error", "Error"),
        ("despublicada", "Despublicada"),
    ]

    medio = models.ForeignKey(Medio, on_delete=models.CASCADE, related_name="fuentes")
    url = models.URLField(max_length=1000, unique=True)
    url_hash = models.CharField(max_length=64, db_index=True, editable=False)
    titulo = models.CharField(max_length=500, blank=True)
    bajada = models.TextField(blank=True)
    seccion = models.CharField(max_length=120, blank=True)
    autor = models.CharField(max_length=255, blank=True)
    publicada_en = models.DateTimeField(null=True, blank=True, db_index=True)
    descubierta_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=15, choices=ESTADOS, default="descubierta", db_index=True
    )
    motivo_descarte = models.CharField(max_length=255, blank=True)
    interes = models.FloatField(
        null=True, blank=True, help_text="Decisión tipada: interés público uruguayo"
    )
    texto = models.TextField(blank=True)
    embedding = models.JSONField(default=list, blank=True)
    historia = models.ForeignKey(
        Historia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fuentes",
    )
    ultimo_snapshot = models.ForeignKey(
        "Snapshot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    proximo_recrawl = models.DateTimeField(null=True, blank=True, db_index=True)
    recrawls_hechos = models.PositiveSmallIntegerField(default=0)
    intentos = models.PositiveSmallIntegerField(default=0)
    tonos_en = models.DateTimeField(
        null=True, blank=True, help_text="Última vez que se calculó el tono hacia las personas"
    )

    class Meta:
        ordering = ["-publicada_en"]
        verbose_name_plural = "fuentes"

    def save(self, *args, **kwargs):
        self.url_hash = sha256(self.url)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo or self.url


class Snapshot(models.Model):
    fuente = models.ForeignKey(
        Fuente, on_delete=models.CASCADE, related_name="snapshots"
    )
    capturado_en = models.DateTimeField(default=timezone.now)
    storage_key = models.CharField(max_length=255)
    contenido_hash = models.CharField(max_length=64, db_index=True)
    titulo = models.CharField(max_length=500, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    proveedor = models.CharField(max_length=40)

    class Meta:
        ordering = ["-capturado_en"]

    def __str__(self):
        return f"{self.fuente_id} @ {self.capturado_en:%Y-%m-%d %H:%M}"


class Cambio(models.Model):
    TIPOS = [
        ("titulo", "Cambió el título"),
        ("cuerpo", "Cambió el cuerpo"),
        ("despublicada", "Despublicada"),
    ]

    fuente = models.ForeignKey(Fuente, on_delete=models.CASCADE, related_name="cambios")
    antes = models.ForeignKey(
        Snapshot, on_delete=models.CASCADE, related_name="+"
    )
    despues = models.ForeignKey(
        Snapshot, on_delete=models.CASCADE, related_name="+", null=True, blank=True
    )
    tipo = models.CharField(max_length=15, choices=TIPOS)
    diff = models.JSONField(default=list, blank=True)
    titulo_antes = models.CharField(max_length=500, blank=True)
    titulo_despues = models.CharField(max_length=500, blank=True)
    cambia_sentido = models.FloatField(
        null=True, blank=True, help_text="Probabilidad de que cambie el sentido"
    )
    resumen = models.CharField(max_length=300, blank=True)
    detectado_en = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-detectado_en"]

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.fuente}"

    @property
    def frase(self) -> str:
        """Qué pasó, en una frase, con lo que ya sabemos (medio, tipo y cuándo
        lo vimos). No es cuándo editó el medio: solo sabemos que fue entre dos
        capturas."""
        medio = self.fuente.medio.nombre
        if self.tipo == "titulo":
            que = "cambió el titular"
        elif self.tipo == "despublicada":
            que = "borró la nota"
        else:
            ops = {op[0] for op in self.diff or []}
            if "-" in ops and "+" not in ops:
                que = "sacó texto de la nota"
            elif "+" in ops and "-" not in ops:
                que = "agregó texto a la nota"
            else:
                que = "cambió el texto de la nota"
        frase = f"{medio} {que}"
        if publicada := self.fuente.publicada_en:
            horas = (self.detectado_en - publicada).total_seconds() / 3600
            if horas >= 0:
                if horas < 1:
                    cuando = "menos de una hora"
                elif horas < 36:
                    n = round(horas)
                    cuando = f"{n} hora{'s' if n != 1 else ''}"
                else:
                    n = round(horas / 24)
                    cuando = f"{n} días"
                frase += f". Lo vimos {cuando} después de publicada"
        return frase + "."

    def extracto(self, max_bloques=2, contexto=4, max_palabras=25):
        """Los primeros bloques del diff, con unas palabras de contexto a cada
        lado, para mostrar qué cambió sin abrir la nota."""
        ops = self.diff or []
        bloques, i = [], 0
        while i < len(ops) and len(bloques) < max_bloques:
            if ops[i][0] == "=":
                i += 1
                continue
            j = i
            quitado, agregado = [], []
            while j < len(ops) and ops[j][0] != "=":
                (quitado if ops[j][0] == "-" else agregado).append(ops[j][1])
                j += 1
            previo = ops[i - 1][1].split()[-contexto:] if i and ops[i - 1][0] == "=" else []
            siguiente = ops[j][1].split()[:contexto] if j < len(ops) else []

            def corto(textos):
                palabras = " ".join(textos).split()
                return " ".join(palabras[:max_palabras]) + (" …" if len(palabras) > max_palabras else "")

            bloques.append({
                "antes": " ".join(previo),
                "quitado": corto(quitado),
                "agregado": corto(agregado),
                "despues": " ".join(siguiente),
            })
            i = j
        return bloques


class Hecho(models.Model):
    historia = models.ForeignKey(
        Historia, on_delete=models.CASCADE, related_name="hechos"
    )
    texto = models.CharField(max_length=400)
    fuentes = models.ManyToManyField(Fuente, through="HechoFuente", related_name="hechos")
    entidades = models.ManyToManyField("core.Entidad", blank=True, related_name="hechos")
    orden = models.PositiveSmallIntegerField(default=0)
    disputado = models.BooleanField(default=False)
    oculto = models.BooleanField(default=False)

    class Meta:
        ordering = ["historia", "orden"]
        verbose_name_plural = "hechos"

    def __str__(self):
        return self.texto


class HechoFuente(models.Model):
    hecho = models.ForeignKey(Hecho, on_delete=models.CASCADE)
    fuente = models.ForeignKey(Fuente, on_delete=models.CASCADE)
    cita = models.CharField(max_length=400, blank=True)
    fiel = models.FloatField(
        null=True, blank=True, help_text="Probabilidad de que la fuente lo respalde"
    )

    class Meta:
        unique_together = ("hecho", "fuente")


class Proposicion(models.Model):
    ESTADOS = [
        ("candidata", "Candidata"),
        ("publicada", "Publicada"),
        ("descartada", "Descartada"),
    ]

    historia = models.ForeignKey(
        Historia, on_delete=models.CASCADE, related_name="proposiciones"
    )
    texto = models.CharField(max_length=250)
    hechos = models.ManyToManyField(Hecho, blank=True, related_name="proposiciones")
    entidades = models.ManyToManyField(
        "core.Entidad", blank=True, related_name="proposiciones"
    )
    tema = models.CharField(max_length=80, blank=True, db_index=True)
    divisividad = models.FloatField(null=True, blank=True)
    calidad = models.FloatField(null=True, blank=True)
    estado = models.CharField(
        max_length=12, choices=ESTADOS, default="candidata", db_index=True
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]
        verbose_name_plural = "proposiciones"

    def __str__(self):
        return self.texto


class Tono(models.Model):
    """Cómo deja una nota a una persona: valencia de -2 (muy mal) a 2 (muy bien).

    Mide la valencia de la nota, no el encuadre del medio: una noticia mala
    para la persona cuenta como negativa aunque esté contada con neutralidad
    (docs/decisiones/0013-tono-de-los-medios.md).
    """

    VALENCIAS = [
        (-2, "Muy mal parada"),
        (-1, "Mal parada"),
        (0, "Neutra"),
        (1, "Bien parada"),
        (2, "Muy bien parada"),
    ]

    fuente = models.ForeignKey(Fuente, on_delete=models.CASCADE, related_name="tonos")
    entidad = models.ForeignKey("core.Entidad", on_delete=models.CASCADE, related_name="tonos")
    valencia = models.SmallIntegerField(choices=VALENCIAS)
    cita = models.CharField(max_length=400)
    razon = models.CharField(max_length=300, blank=True)
    verificado = models.FloatField(
        null=True, blank=True, help_text="Probabilidad (Jev) de que la cita respalde la valencia"
    )
    modelo = models.CharField(max_length=80, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("fuente", "entidad")
        ordering = ["-fuente__publicada_en"]

    def __str__(self):
        return f"{self.entidad} en {self.fuente_id}: {self.valencia:+d}"


class Decision(models.Model):
    """Registro de cada decisión tipada, para auditar y recalibrar umbrales."""

    pregunta = models.CharField(max_length=60, db_index=True)
    entrada_hash = models.CharField(max_length=64, db_index=True)
    valor = models.FloatField()
    modelo = models.CharField(max_length=80)
    costo_usd = models.FloatField(default=0)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]
        indexes = [models.Index(fields=["pregunta", "entrada_hash"])]

    def __str__(self):
        return f"{self.pregunta}={self.valor:.2f}"


class UsoProveedor(models.Model):
    """Contador diario de uso por proveedor (cupos y costo)."""

    fecha = models.DateField(default=timezone.localdate)
    proveedor = models.CharField(max_length=40)
    operacion = models.CharField(max_length=40)
    cantidad = models.PositiveIntegerField(default=0)
    costo_usd = models.FloatField(default=0)

    class Meta:
        unique_together = ("fecha", "proveedor", "operacion")
