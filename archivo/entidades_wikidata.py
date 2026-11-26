"""
Fichas de entidades con datos de Wikidata y Wikipedia.

Asociar una entidad con un ítem de Wikidata es lo delicado: una persona
equivocada en la ficha es peor que ninguna. Por eso el candidato tiene que:

 1. ser uruguayo (lo filtra el proveedor: P27 / P17),
 2. llamarse igual (etiqueta o alias; las personas también si el nombre de las
    noticias tiene ≥ 2 palabras y todas están en la etiqueta), y
 3. que Jev, con los hechos donde aparece la entidad, diga que es la misma
    (≥ UMBRAL_WIKIDATA) y le gane al segundo candidato por ≥ MARGEN_WIKIDATA.

Sin eso no se asocia nada. Lo que staff fija (`FichaEntidad.fijada`) no se
vuelve a buscar. Ver docs/decisiones/0016-fichas-de-wikidata.md.

    enriquecer(entidad)            # busca o refresca una
    entidades_pendientes()         # cola: más hechos primero, nuevas antes que refrescos
    enriquecer_pendientes(limite)  # respeta el cupo diario
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import timedelta

from django.db.models import Case, Count, IntegerField, Q, When
from django.utils import timezone

from core.models import Entidad, normalize_entity_name

from .models import FichaEntidad, UsoProveedor
from .providers.decide import decidir
from .providers.wikidata import get_enriquecedor

logger = logging.getLogger(__name__)

TIPOS = ("persona", "organizacion", "lugar")
MAX_DIA = lambda: int(os.environ.get("MAX_ENRIQUECIMIENTOS_DIA", 100))  # noqa: E731
POR_CORRIDA = lambda: int(os.environ.get("ENRIQUECER_POR_CORRIDA", 15))  # noqa: E731
SEGUNDOS_POR_CORRIDA = lambda: int(os.environ.get("ENRIQUECER_SEGUNDOS_POR_CORRIDA", 300))  # noqa: E731
UMBRAL_WIKIDATA = lambda: float(os.environ.get("UMBRAL_WIKIDATA", 0.8))  # noqa: E731
MARGEN_WIKIDATA = lambda: float(os.environ.get("MARGEN_WIKIDATA", 0.2))  # noqa: E731
MIN_HECHOS = lambda: int(os.environ.get("MIN_HECHOS_ENRIQUECER", 2))  # noqa: E731
REFRESCO_DIAS = lambda: int(os.environ.get("REFRESCO_FICHA_DIAS", 30))  # noqa: E731
REINTENTO_DIAS = lambda: int(os.environ.get("REINTENTO_FICHA_DIAS", 90))  # noqa: E731
MAX_ERRORES_SEGUIDOS = 3
HECHOS_DE_CONTEXTO = 6


def _norm(texto):
    return " ".join(re.sub(r"[^\w\s]", " ", normalize_entity_name(texto)).split())


def mismo_nombre(entidad, datos) -> bool:
    """El nombre de la entidad es la etiqueta o un alias del candidato; en
    personas también cuando sus palabras (≥ 2) están todas en la etiqueta."""
    n = _norm(entidad.nombre)
    if not n:
        return False
    nombres = [_norm(x) for x in datos.nombres]
    if n in nombres:
        return True
    palabras = set(n.split())
    return entidad.tipo == "persona" and len(palabras) >= 2 and any(palabras <= set(x.split()) for x in nombres)


def _hechos(entidad):
    return list(
        entidad.hechos.filter(oculto=False).order_by("-historia__primera_fuente_en").values_list("texto", flat=True)[
            :HECHOS_DE_CONTEXTO
        ]
    )


def _estado(entidad, datos, hechos):
    return {
        "entidad": entidad.nombre,
        "tipo": entidad.get_tipo_display(),
        "hechos_donde_aparece": hechos,
        "candidato": {
            "etiqueta": datos.etiqueta,
            "descripcion": datos.descripcion,
            "cargo": datos.cargo,
            "organizacion": datos.organizacion,
        },
    }


def elegir_candidato(entidad, enr=None):
    """(datos, confianza) del único candidato claro, o (None, mejor confianza)."""
    enr = enr or get_enriquecedor()
    candidatos = [d for d in enr.buscar(entidad.nombre, entidad.tipo) if mismo_nombre(entidad, d)]
    if not candidatos:
        return None, 0.0
    hechos = _hechos(entidad)
    puntos = sorted(
        ((decidir("misma_entidad", _estado(entidad, d, hechos)), d) for d in candidatos),
        key=lambda x: -x[0],
    )
    mejor, datos = puntos[0]
    segundo = puntos[1][0] if len(puntos) > 1 else 0.0
    if mejor < UMBRAL_WIKIDATA() or mejor - segundo < MARGEN_WIKIDATA():
        return None, mejor
    return datos, mejor


def _aplicar(ficha, d, confianza=None):
    ficha.qid = d.qid
    for campo in (
        "etiqueta", "descripcion", "cargo", "organizacion", "resumen", "wikipedia_url",
        "foto_url", "foto_pagina", "foto_autor", "foto_licencia",
    ):
        setattr(ficha, campo, getattr(d, campo))
    if confianza is not None:
        ficha.confianza = confianza
    ficha.consultada_en = timezone.now()
    ficha.save()


def _vaciar(ficha):
    for campo in (
        "qid", "etiqueta", "descripcion", "cargo", "organizacion", "resumen", "wikipedia_url",
        "foto_url", "foto_pagina", "foto_autor", "foto_licencia",
    ):
        setattr(ficha, campo, "")
    ficha.confianza = 0
    ficha.consultada_en = timezone.now()
    ficha.save()


def enriquecer(entidad, enr=None) -> str:
    """Busca la ficha de la entidad, o refresca la que ya tiene. Devuelve qué pasó:
    asociada, sin_candidato, refrescada, perdida (el ítem ya no existe) o fijada_vacia."""
    enr = enr or get_enriquecedor()
    ficha, _ = FichaEntidad.objects.get_or_create(entidad=entidad)
    if ficha.fijada and not ficha.qid:
        return "fijada_vacia"
    if ficha.qid:
        d = enr.obtener(ficha.qid)
        if d is None:
            if ficha.fijada:  # staff puso un QID que no existe: se deja y se reintenta más tarde
                ficha.consultada_en = timezone.now()
                ficha.save(update_fields=["consultada_en"])
                return "perdida"
            _vaciar(ficha)
            return "perdida"
        _aplicar(ficha, enr.detalle(d))
        return "refrescada"
    d, confianza = elegir_candidato(entidad, enr)
    if d is None:
        ficha.confianza = confianza
        ficha.consultada_en = timezone.now()
        ficha.save(update_fields=["confianza", "consultada_en"])
        return "sin_candidato"
    _aplicar(ficha, enr.detalle(d), confianza)
    return "asociada"


def fijar(entidad, qid, enr=None) -> str:
    """Staff: asocia la entidad con `qid` (vacío = anular) y no se vuelve a buscar."""
    enr = enr or get_enriquecedor()
    ficha, _ = FichaEntidad.objects.get_or_create(entidad=entidad)
    qid = (qid or "").strip().upper()
    if not qid:
        _vaciar(ficha)
        ficha.fijada = True
        ficha.save(update_fields=["fijada"])
        return "anulada"
    d = enr.obtener(qid)
    if d is None:
        raise ValueError(f"{qid} no existe en Wikidata")
    ficha.fijada = True
    _aplicar(ficha, enr.detalle(d), confianza=1)
    return "fijada"


def entidades_pendientes():
    """Sin ficha, o con ficha vencida (asociadas cada REFRESCO_DIAS, sin
    asociar cada REINTENTO_DIAS). Nuevas primero; en cada grupo, más hechos primero."""
    ahora = timezone.now()
    vencida = Q(ficha__isnull=True)
    vencida |= Q(ficha__qid__gt="", ficha__consultada_en__lt=ahora - timedelta(days=REFRESCO_DIAS()))
    vencida |= Q(ficha__qid__gt="", ficha__consultada_en__isnull=True)
    vencida |= Q(ficha__qid="", ficha__fijada=False, ficha__consultada_en__lt=ahora - timedelta(days=REINTENTO_DIAS()))
    vencida |= Q(ficha__qid="", ficha__fijada=False, ficha__consultada_en__isnull=True)
    return (
        Entidad.objects.filter(tipo__in=TIPOS)
        .annotate(n_hechos=Count("hechos", filter=Q(hechos__oculto=False), distinct=True))
        .filter(n_hechos__gte=MIN_HECHOS())
        .filter(vencida)
        .annotate(nueva=Case(When(ficha__isnull=True, then=0), default=1, output_field=IntegerField()))
        .order_by("nueva", "-n_hechos", "pk")
    )


def enriquecimientos_hoy():
    return sum(
        UsoProveedor.objects.filter(fecha=timezone.localdate(), operacion="enriquecer").values_list(
            "cantidad", flat=True
        )
    )


def enriquecer_pendientes(limite=None, segundos=None) -> str:
    from .pipeline import registrar_uso

    enr = get_enriquecedor()
    fin = time.monotonic() + segundos if segundos else None
    cuenta = {}
    errores = hechas = 0
    for e in entidades_pendientes().iterator():
        if enriquecimientos_hoy() >= MAX_DIA() or (limite is not None and hechas >= limite):
            break
        if fin is not None and time.monotonic() >= fin:
            break
        hechas += 1
        registrar_uso("wikidata", "enriquecer")
        try:
            r = enriquecer(e, enr)
            errores = 0
        except Exception:
            logger.exception("Ficha falló para %s", e)
            errores += 1
            if errores >= MAX_ERRORES_SEGUIDOS:  # Wikidata caído: no seguir golpeando
                break
            continue
        cuenta[r] = cuenta.get(r, 0) + 1
    detalle = " ".join(f"{k}={v}" for k, v in sorted(cuenta.items()))
    return f"entidades={hechas} {detalle} errores={errores} hoy={enriquecimientos_hoy()}/{MAX_DIA()}".replace("  ", " ")
