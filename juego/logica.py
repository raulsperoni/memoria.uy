"""Armado de jornadas, resultados, puntaje y racha."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from archivo.models import Proposicion

from .models import Jornada, JornadaItem, VotoProposicion, bucket_de

N_ITEMS = 5
MIN_ITEMS = 3
MIN_VOTOS_RESULTADO = 30  # debajo de esto el resultado se marca "provisorio"
CALIDAD_MIN = 0.7
DIVISIVIDAD_CONSENSO = 0.35


# ---------------------------------------------------------------------------
# Armado
# ---------------------------------------------------------------------------


def _score(p: Proposicion) -> float:
    return (p.historia.n_medios or 1) * (0.5 + (p.divisividad or 0))


def candidatas(fecha, horas=48):
    hasta = datetime.combine(fecha, time(6, 0), tzinfo=timezone.get_current_timezone())
    desde = hasta - timedelta(hours=horas)
    usadas = JornadaItem.objects.values("proposicion_id")
    return (
        Proposicion.objects.filter(
            estado="publicada",
            calidad__gte=CALIDAD_MIN,
            historia__ultima_fuente_en__gte=desde,
            historia__ultima_fuente_en__lt=hasta + timedelta(hours=18),
        )
        .exclude(pk__in=usadas)
        .select_related("historia")
    )


def recurrente(fecha):
    """Una proposición de un tema de semanas anteriores (ancla para el clustering)."""
    temas_recientes = set(
        JornadaItem.objects.filter(jornada__fecha__gte=fecha - timedelta(days=14))
        .exclude(proposicion__tema="")
        .values_list("proposicion__tema", flat=True)
    )
    qs = (
        Proposicion.objects.filter(
            estado="publicada",
            calidad__gte=CALIDAD_MIN,
            creada_en__date__lt=fecha - timedelta(days=7),
            creada_en__date__gte=fecha - timedelta(days=60),
        )
        .exclude(tema="")
        .exclude(tema__in=temas_recientes)
        .annotate(n=Count("votos"))
        .order_by("-n", "-divisividad")
    )
    return qs.first()


def armar_jornada(fecha=None, publicar=True) -> Jornada | None:
    """Arma la jornada del día (idempotente: si existe, la devuelve)."""
    fecha = fecha or timezone.localdate()
    existente = Jornada.objects.filter(fecha=fecha).first()
    if existente and existente.items.exists():
        return existente

    elegidas: list[Proposicion] = []
    historias, categorias = set(), Counter()
    rec = recurrente(fecha)
    cupo = N_ITEMS - (1 if rec else 0)

    pool = sorted(candidatas(fecha), key=_score, reverse=True)
    # Al menos una de probable consenso (no todo grieta)
    consenso = next((p for p in pool if (p.divisividad or 0) < DIVISIVIDAD_CONSENSO), None)

    def puede(p):
        return p.historia_id not in historias and categorias[p.historia.categoria] < 2

    def agregar(p):
        elegidas.append(p)
        historias.add(p.historia_id)
        categorias[p.historia.categoria] += 1

    if consenso:
        agregar(consenso)
    for p in pool:
        if len(elegidas) >= cupo:
            break
        if p not in elegidas and puede(p):
            agregar(p)
    # Si la diversidad dejó huecos, relajamos categorías.
    for p in pool:
        if len(elegidas) >= cupo:
            break
        if p not in elegidas and p.historia_id not in historias:
            agregar(p)

    if rec and rec not in elegidas:
        elegidas.append(rec)
    if len(elegidas) < MIN_ITEMS:
        return None

    # Orden: la de consenso primero suaviza la entrada; el resto por score.
    jornada = existente or Jornada.objects.create(fecha=fecha)
    for i, p in enumerate(elegidas):
        JornadaItem.objects.create(jornada=jornada, proposicion=p, orden=i, recurrente=(p == rec))
    jornada.publicada = publicar
    jornada.save(update_fields=["publicada"])
    return jornada


def jornada_de_hoy() -> Jornada | None:
    return (
        Jornada.objects.filter(fecha=timezone.localdate(), publicada=True)
        .prefetch_related("items__proposicion__historia")
        .first()
    )


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------


@dataclass
class Resultado:
    acuerdo: int
    desacuerdo: int
    nose: int

    @property
    def total(self):
        return self.acuerdo + self.desacuerdo + self.nose

    @property
    def opinan(self):
        return self.acuerdo + self.desacuerdo

    @property
    def pct_acuerdo(self) -> float | None:
        return 100 * self.acuerdo / self.opinan if self.opinan else None

    @property
    def pct_desacuerdo(self) -> float | None:
        return 100 - self.pct_acuerdo if self.opinan else None

    @property
    def provisorio(self):
        return self.opinan < MIN_VOTOS_RESULTADO

    @property
    def bucket(self):
        return bucket_de(self.pct_acuerdo) if self.pct_acuerdo is not None else None


def resultado(proposicion, hasta=None, excluir: Q | None = None) -> Resultado:
    qs = VotoProposicion.objects.filter(proposicion=proposicion)
    if hasta:
        qs = qs.filter(creado_en__lt=hasta)
    if excluir is not None:
        qs = qs.exclude(excluir)
    c = dict(qs.values_list("opinion").annotate(n=Count("id")))
    return Resultado(c.get("acuerdo", 0), c.get("desacuerdo", 0), c.get("nose", 0))


def fin_de(fecha):
    return datetime.combine(fecha + timedelta(days=1), time.min, tzinfo=timezone.get_current_timezone())


# ---------------------------------------------------------------------------
# Votantes, puntaje, racha
# ---------------------------------------------------------------------------


def filtro_votante(voter: dict) -> Q:
    if voter.get("usuario"):
        return Q(usuario=voter["usuario"])
    return Q(session_key=voter["session_key"])


def votos_de(voter, jornada):
    return {
        v.proposicion_id: v
        for v in VotoProposicion.objects.filter(filtro_votante(voter), proposicion__in=jornada.proposiciones.all())
    }


def puntaje(voter, jornada):
    """Lista de (item, voto, resultado, acierto) y total de aciertos.
    El acierto se evalúa contra el resultado al cierre del día (provisorio
    antes), sin contar el voto propio (si no, con pocos votantes, alcanzaría
    con predecir la propia opinión). Una frase pasada («no sé», sin
    predicción) cuenta como jugada pero no suma: acierto None."""
    hasta = fin_de(jornada.fecha) if jornada.fecha < timezone.localdate() else None
    votos = votos_de(voter, jornada)
    filas, aciertos = [], 0
    for item in jornada.items_ordenados():
        v = votos.get(item.proposicion_id)
        r = resultado(item.proposicion, hasta=hasta, excluir=filtro_votante(voter))
        acierto = None
        if v and v.prediccion is not None and r.bucket is not None:
            acierto = v.prediccion == r.bucket
            aciertos += int(acierto)
        filas.append((item, v, r, acierto))
    return filas, aciertos


def completa(voter, jornada) -> bool:
    return len(votos_de(voter, jornada)) >= jornada.items.count()


def racha(voter, hoy=None) -> int:
    """Días consecutivos (hasta hoy o ayer) con la jornada completa."""
    hoy = hoy or timezone.localdate()
    jornadas = {
        j.fecha: j
        for j in Jornada.objects.filter(publicada=True, fecha__lte=hoy, fecha__gte=hoy - timedelta(days=400))
        .annotate(n=Count("items"))
    }
    votadas = Counter(
        VotoProposicion.objects.filter(filtro_votante(voter), jornada__isnull=False)
        .values_list("jornada__fecha", flat=True)
    )
    dia = hoy if votadas.get(hoy, 0) >= getattr(jornadas.get(hoy), "n", 99) else hoy - timedelta(days=1)
    n = 0
    while dia in jornadas and votadas.get(dia, 0) >= jornadas[dia].n:
        n += 1
        dia -= timedelta(days=1)
    return n


def tarjeta(voter, jornada) -> str:
    """Texto compartible estilo Wordle. ➖ = frase pasada (sin predicción)."""
    filas, aciertos = puntaje(voter, jornada)
    cuadros = "".join(
        "➖" if not v or v.prediccion is None else "🟩" if a else "⬜" if a is False else "🔲"
        for _, v, _, a in filas
    )
    r = racha(voter)
    lineas = [
        f"memoria.uy · {jornada.fecha:%d/%m}",
        f"Leí a Uruguay {aciertos}/{len(filas)}",
        cuadros,
    ]
    if r > 1:
        lineas.append(f"racha 🔥 {r}")
    return "\n".join(lineas)
