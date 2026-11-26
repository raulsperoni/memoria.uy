"""
Pipeline del archivo. Funciones síncronas y testeables; `archivo/tasks.py`
las envuelve como tasks de Celery.

descubrir → filtrar → extraer → agrupar → procesar_historia
                                  └→ (top del día) recrawl → Cambio
"""

from __future__ import annotations

import difflib
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone as dt_tz
from urllib.parse import urlparse

import feedparser
import requests
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from core.models import Entidad
from core.utils import normalize_url

from .limpieza import limpiar, lineas_del_medio
from .llm import get_procesador
from .models import (
    Cambio,
    Fuente,
    Hecho,
    HechoFuente,
    Historia,
    Medio,
    Proposicion,
    Snapshot,
    UsoProveedor,
    sha256,
)
from .providers import get_embedder, get_extractor, get_storage
from .providers.decide import decidir
from .providers.embed import coseno
from .providers.extract import ExtractError, USER_AGENT, comprobar_publicada

logger = logging.getLogger(__name__)


def env_float(nombre, default):
    return float(os.environ.get(nombre, default))


def env_int(nombre, default):
    return int(os.environ.get(nombre, default))


# Umbrales (calibrables por env)
UMBRAL_INTERES = lambda: env_float("UMBRAL_INTERES", 0.6)  # noqa: E731
UMBRAL_VALE_HISTORIA = lambda: env_float("UMBRAL_VALE_HISTORIA", 0.34)  # noqa: E731
UMBRAL_FIEL = lambda: env_float("UMBRAL_FIEL", 0.5)  # noqa: E731
UMBRAL_CALIDAD = lambda: env_float("UMBRAL_CALIDAD", 0.6)  # noqa: E731
RATIO_RECORTE = lambda: env_float("RATIO_RECORTE", 0.6)  # noqa: E731
UMBRAL_MISMA_PROPOSICION = lambda: env_float("UMBRAL_MISMA_PROPOSICION", 0.5)  # noqa: E731
SIM_MISMA = lambda: env_float("SIM_MISMA_HISTORIA", 0.75)  # noqa: E731
SIM_DUDA = lambda: env_float("SIM_DUDA_HISTORIA", 0.40)  # noqa: E731
MAX_CANDIDATAS_DUDA = 3
MAX_EXTRACCIONES_DIA = lambda: env_int("MAX_EXTRACCIONES_DIA", 150)  # noqa: E731
MAX_EDAD_HORAS = lambda: env_int("MAX_EDAD_HORAS", 48)  # noqa: E731
VENTANA_HISTORIA_HORAS = 72
RECRAWL_OFFSETS_HORAS = lambda: [  # noqa: E731
    int(x) for x in os.environ.get("RECRAWL_OFFSETS_HORAS", "24,168").split(",") if x
]


# ---------------------------------------------------------------------------
# Cupos y uso
# ---------------------------------------------------------------------------


def registrar_uso(proveedor, operacion, cantidad=1, costo=0.0):
    obj, _ = UsoProveedor.objects.get_or_create(
        fecha=timezone.localdate(), proveedor=proveedor, operacion=operacion
    )
    UsoProveedor.objects.filter(pk=obj.pk).update(
        cantidad=F("cantidad") + cantidad, costo_usd=F("costo_usd") + costo
    )


def extracciones_hoy():
    return sum(
        UsoProveedor.objects.filter(
            fecha=timezone.localdate(), operacion="extraer"
        ).values_list("cantidad", flat=True)
    )


# ---------------------------------------------------------------------------
# 1. Descubrimiento (gratis: RSS + sitemaps)
# ---------------------------------------------------------------------------


def _parse_fecha(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=dt_tz.utc)
    return None


def _items_rss(url):
    feed = feedparser.parse(url, agent=USER_AGENT)
    for e in feed.entries:
        link = e.get("link")
        if not link:
            continue
        bajada = re.sub(r"<[^>]+>", " ", e.get("summary", "") or "")
        yield {
            "url": link,
            "titulo": (e.get("title") or "").strip(),
            "bajada": re.sub(r"\s+", " ", bajada).strip()[:1000],
            "publicada_en": _parse_fecha(e),
            "seccion": ", ".join(t.get("term", "") for t in e.get("tags", []))[:120],
        }


NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}


def _items_sitemap(url):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    for u in root.findall("sm:url", NS):
        loc = u.findtext("sm:loc", default="", namespaces=NS).strip()
        if not loc:
            continue
        titulo = u.findtext("news:news/news:title", default="", namespaces=NS)
        fecha = u.findtext(
            "news:news/news:publication_date", default="", namespaces=NS
        ) or u.findtext("sm:lastmod", default="", namespaces=NS)
        publicada = None
        if fecha:
            try:
                publicada = datetime.fromisoformat(fecha.replace("Z", "+00:00"))
                if publicada.tzinfo is None:
                    publicada = publicada.replace(tzinfo=dt_tz.utc)
            except ValueError:
                pass
        yield {
            "url": loc,
            "titulo": titulo.strip(),
            "bajada": "",
            "publicada_en": publicada,
            "seccion": "",
        }


def descubrir(medio: Medio) -> list[Fuente]:
    """Lee RSS/sitemaps del medio y crea Fuentes nuevas. Devuelve las nuevas."""
    nuevas = []
    items = []
    for url in medio.rss_urls:
        try:
            items.extend(_items_rss(url))
        except Exception as e:
            logger.warning("RSS %s falló: %s", url, e)
    for url in medio.sitemap_urls:
        try:
            items.extend(_items_sitemap(url))
        except Exception as e:
            logger.warning("Sitemap %s falló: %s", url, e)

    for it in items:
        url = normalize_url(it["url"])
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if not host.endswith(medio.dominio.removeprefix("www.")):
            continue
        if Fuente.objects.filter(url_hash=sha256(url)).exists():
            continue
        f = Fuente.objects.create(
            medio=medio,
            url=url,
            titulo=it["titulo"][:500],
            bajada=it["bajada"],
            seccion=it["seccion"],
            publicada_en=it["publicada_en"],
        )
        nuevas.append(f)
    medio.ultimo_descubrimiento = timezone.now()
    medio.save(update_fields=["ultimo_descubrimiento"])
    return nuevas


# ---------------------------------------------------------------------------
# 2. Filtro (gratis primero, después decisión tipada)
# ---------------------------------------------------------------------------


def _descartar(fuente, motivo):
    fuente.estado = "descartada"
    fuente.motivo_descarte = motivo[:255]
    fuente.save(update_fields=["estado", "motivo_descarte"])
    return False


def filtrar(fuente: Fuente) -> bool:
    """True si la fuente debe extraerse."""
    medio = fuente.medio
    path = urlparse(fuente.url).path.lower()

    if any(p in path for p in medio.secciones_excluidas):
        return _descartar(fuente, "sección excluida")
    if medio.secciones_incluidas and not any(
        p in path for p in medio.secciones_incluidas
    ):
        return _descartar(fuente, "sección no incluida")
    if fuente.publicada_en and fuente.publicada_en < timezone.now() - timedelta(
        hours=MAX_EDAD_HORAS()
    ):
        return _descartar(fuente, "antigua")

    if medio.tipo == "oficial":
        fuente.interes = 1.0
        fuente.save(update_fields=["interes"])
        return True

    titulo = fuente.titulo or path.rsplit("/", 1)[-1].replace("-", " ")
    fuente.interes = decidir(
        "interes_publico",
        {"medio": f"{medio.nombre} (Uruguay)", "titulo": titulo, "bajada": fuente.bajada[:500], "seccion": fuente.seccion or path},
    )
    fuente.save(update_fields=["interes"])
    if fuente.interes < UMBRAL_INTERES():
        return _descartar(fuente, f"interés {fuente.interes:.2f}")
    return True


# ---------------------------------------------------------------------------
# 3. Extracción + snapshot
# ---------------------------------------------------------------------------


def guardar_snapshot(fuente, res) -> Snapshot:
    clave = get_storage().put(res.html.encode("utf-8"))
    return Snapshot.objects.create(
        fuente=fuente,
        storage_key=clave,
        contenido_hash=sha256(res.texto),
        titulo=res.titulo[:500],
        http_status=res.status,
        proveedor=res.proveedor,
    )


def extraer(fuente: Fuente, respetar_cupo=True) -> bool:
    if respetar_cupo and extracciones_hoy() >= MAX_EXTRACCIONES_DIA():
        logger.info("Cupo diario de extracción agotado")
        return False
    extractor = get_extractor()
    fuente.intentos += 1
    try:
        res = extractor.extract(fuente.url)
    except ExtractError as e:
        fuente.estado = "error" if (e.permanente or fuente.intentos >= 3) else fuente.estado
        fuente.motivo_descarte = str(e)[:255]
        fuente.save(update_fields=["estado", "motivo_descarte", "intentos"])
        return False
    registrar_uso(extractor.nombre, "extraer")
    res.texto = limpiar(res.texto, lineas_del_medio(fuente.medio, res.texto))

    snap = guardar_snapshot(fuente, res)
    fuente.ultimo_snapshot = snap
    fuente.texto = res.texto
    fuente.titulo = res.titulo[:500] or fuente.titulo
    fuente.autor = res.autor[:255]
    if not fuente.publicada_en and res.fecha:
        try:
            fuente.publicada_en = datetime.fromisoformat(res.fecha).replace(tzinfo=dt_tz.utc)
        except ValueError:
            pass
    fuente.estado = "extraida"
    fuente.save()
    return True


# ---------------------------------------------------------------------------
# 4. Agrupamiento en historias
# ---------------------------------------------------------------------------


def _texto_para_embedding(fuente):
    # El primer párrafo con contenido: un saludo o una línea suelta de la
    # página no alcanza para saber de qué trata la nota.
    lineas = [x for x in (fuente.texto or fuente.bajada).split("\n") if x.strip()]
    primer_parrafo = next((x for x in lineas if len(x) >= 40), lineas[0] if lineas else "")[:600]
    return f"{fuente.titulo}\n{primer_parrafo}"


def _actualizar_centroide(historia, emb):
    n = historia.n_embeddings
    if not historia.centroide:
        historia.centroide = emb
    else:
        c = [(x * n + y) / (n + 1) for x, y in zip(historia.centroide, emb)]
        norma = sum(x * x for x in c) ** 0.5 or 1.0
        historia.centroide = [x / norma for x in c]
    historia.n_embeddings = n + 1


def agrupar(fuente: Fuente) -> Historia | None:
    if fuente.estado not in ("extraida", "procesada") or not fuente.texto:
        return None
    # Una nota guardada antes de que su aviso se repitiera lo bastante como
    # para reconocerlo.
    limpio = limpiar(fuente.texto, lineas_del_medio(fuente.medio))
    if limpio != fuente.texto:
        fuente.texto = limpio
        fuente.embedding = None
        fuente.save(update_fields=["texto"])
    if not fuente.embedding:
        fuente.embedding = get_embedder().embed([_texto_para_embedding(fuente)])[0]
        registrar_uso("embed", "embed")

    desde = timezone.now() - timedelta(hours=VENTANA_HISTORIA_HORAS)
    candidatas = Historia.objects.filter(estado="abierta", ultima_fuente_en__gte=desde)

    ranking = sorted(
        ((coseno(fuente.embedding, h.centroide), h) for h in candidatas),
        key=lambda t: -t[0],
    )

    historia = None
    if ranking and ranking[0][0] >= SIM_MISMA():
        historia = ranking[0][1]
    else:
        # Zona de duda: los embeddings separan mal notas del mismo hecho con
        # ángulos distintos (0.4–0.75 en bge-m3); Jev decide, es barato y
        # separa bien (≈0.03 vs ≈0.9). Probamos hasta 3 candidatas.
        for sim, h in ranking[:MAX_CANDIDATAS_DUDA]:
            if sim < SIM_DUDA():
                break
            otra = h.fuentes.exclude(pk=fuente.pk).first()
            if not otra:
                continue
            p = decidir(
                "mismo_hecho",
                {
                    "A": {"titulo": otra.titulo, "texto": (otra.texto or otra.bajada)[:800]},
                    "B": {"titulo": fuente.titulo, "texto": (fuente.texto or fuente.bajada)[:800]},
                },
            )
            if p >= 0.5:
                historia = h
                break

    with transaction.atomic():
        if historia is None:
            historia = Historia.objects.create(
                primera_fuente_en=fuente.publicada_en or timezone.now()
            )
        _actualizar_centroide(historia, fuente.embedding)
        historia.ultima_fuente_en = timezone.now()
        fuente.historia = historia
        fuente.save(update_fields=["embedding", "historia"])
        historia.recalcular_n_medios()
        historia.save()
    return historia


# ---------------------------------------------------------------------------
# 5. Procesamiento de historia (LLM + verificación)
# ---------------------------------------------------------------------------


def historias_listas(quieta_horas=2, min_medios_inmediato=3):
    """Historias abiertas con fuentes nuevas sin procesar, ya 'quietas'."""
    ahora = timezone.now()
    qs = Historia.objects.filter(estado="abierta", fuentes__estado="extraida").distinct()
    for h in qs:
        if h.n_medios >= min_medios_inmediato or h.ultima_fuente_en <= ahora - timedelta(hours=quieta_horas):
            yield h


def _entidad(nombre, tipo="otro"):
    from core.models import normalize_entity_name

    nombre = nombre.strip()[:255]
    if not nombre:
        return None
    existente = Entidad.objects.filter(normalized_name=normalize_entity_name(nombre)).first()
    if existente:
        return existente
    return Entidad.objects.create(nombre=nombre, tipo=tipo)


def procesar_historia(historia: Historia) -> bool:
    fuentes = list(
        historia.fuentes.filter(estado__in=["extraida", "procesada"])
        .select_related("medio")
        .order_by("medio_id", "publicada_en")
    )
    if not fuentes:
        return False
    # Una fuente por medio, priorizando las más largas.
    por_medio = {}
    for f in sorted(fuentes, key=lambda f: -len(f.texto)):
        por_medio.setdefault(f.medio_id, f)
    elegidas = list(por_medio.values())

    # Filtro 2: ¿vale una historia? (solo si cobertura baja)
    if historia.n_medios <= 1 and historia.relevancia is None:
        f0 = elegidas[0]
        historia.relevancia = decidir(
            "vale_historia",
            {"titulo": f0.titulo, "texto": (f0.texto or f0.bajada)[:1200]},
        )
        historia.save(update_fields=["relevancia"])
    if historia.n_medios <= 1 and (historia.relevancia or 0) < UMBRAL_VALE_HISTORIA():
        Fuente.objects.filter(pk__in=[f.pk for f in fuentes]).update(estado="procesada")
        return False

    temas = list(
        Proposicion.objects.exclude(tema="")
        .values_list("tema", flat=True)
        .distinct()[:50]
    )
    # Las proposiciones con votos o en una jornada se quedan; el resto se
    # reemplaza en cada reproceso (antes se acumulaban: ver docs/decisiones/0011).
    fijas = list(proposiciones_fijas(historia).filter(estado="publicada").values_list("texto", flat=True))
    salida = get_procesador().procesar(elegidas, temas, proposiciones_existentes=fijas)
    registrar_uso("llm", "historia")

    with transaction.atomic():
        historia.hechos.all().delete()
        historia.proposiciones.exclude(pk__in=proposiciones_fijas(historia)).delete()

        historia.titulo = salida.titulo[:300]
        historia.resumen = salida.resumen
        historia.categoria = salida.categoria
        historia.asignar_slug()
        historia.procesada_en = timezone.now()
        historia.save()

        tipos = {e.nombre.strip().lower(): e.tipo for e in salida.entidades}
        cache_ent = {}

        def ent(nombre):
            k = nombre.strip().lower()
            if k not in cache_ent:
                cache_ent[k] = _entidad(nombre, tipos.get(k, "otro"))
            return cache_ent[k]

        for e in salida.entidades:
            ent(e.nombre)

        hechos = []
        for i, h in enumerate(salida.hechos):
            hecho = Hecho.objects.create(
                historia=historia, texto=h.texto[:400], orden=i, disputado=h.disputado
            )
            for j, idx in enumerate(h.fuentes):
                if 0 <= idx < len(elegidas):
                    cita = h.citas[j] if j < len(h.citas) else ""
                    HechoFuente.objects.get_or_create(
                        hecho=hecho, fuente=elegidas[idx], defaults={"cita": cita[:400]}
                    )
            hecho.entidades.set([x for x in (ent(n) for n in h.entidades) if x])
            hechos.append(hecho)

        for p in salida.proposiciones:
            prop = Proposicion.objects.create(
                historia=historia, texto=p.texto[:250], tema=p.tema[:80]
            )
            prop.hechos.set([hechos[i] for i in p.hechos if 0 <= i < len(hechos)])
            prop.entidades.set([x for x in (ent(n) for n in p.entidades) if x])

        Fuente.objects.filter(pk__in=[f.pk for f in fuentes]).update(estado="procesada")

    verificar_historia(historia)
    return True


def verificar_historia(historia: Historia):
    """Verifica procedencia de hechos, completa atribuciones, chequea el
    resumen y puntúa proposiciones."""
    fuentes = [
        f
        for f in historia.fuentes.filter(estado__in=["extraida", "procesada"])
        .select_related("medio")
        .order_by("-publicada_en")[:8]
        if f.texto
    ]
    umbral = UMBRAL_FIEL()
    for hecho in historia.hechos.all():
        fieles = set()
        for hf in HechoFuente.objects.filter(hecho=hecho).select_related("fuente"):
            hf.fiel = decidir(
                "fuente_respalda",
                {"afirmacion": hecho.texto, "fuente": hf.fuente.texto[:4000]},
            )
            if hf.fiel >= umbral:
                hf.save(update_fields=["fiel"])
                fieles.add(hf.fuente_id)
            else:
                hf.delete()
        # Atribuir el hecho a otras fuentes de la historia que también lo respaldan.
        for f in fuentes:
            if f.pk in fieles:
                continue
            p = decidir("fuente_respalda", {"afirmacion": hecho.texto, "fuente": f.texto[:4000]})
            if p >= umbral:
                HechoFuente.objects.create(hecho=hecho, fuente=f, fiel=p)
                fieles.add(f.pk)
        if not fieles:
            hecho.delete()

    hechos = list(historia.hechos.order_by("orden"))
    if historia.resumen and hechos:
        p = decidir(
            "resumen_fiel",
            {"resumen": historia.resumen, "hechos": [h.texto for h in hechos]},
        )
        if p < 0.5:
            # El resumen afirma algo no verificado: lo rearmamos con hechos verificados.
            historia.resumen = " ".join(h.texto for h in hechos[:3])
            historia.save(update_fields=["resumen"])

    for prop in historia.proposiciones.filter(estado="candidata").order_by("pk"):
        repetida = proposicion_repetida(prop)
        if repetida:
            logger.info("Proposición %s repite a %s; descartada", prop.pk, repetida.pk)
            prop.estado = "descartada"
            prop.save(update_fields=["estado"])
            continue
        estado = {"proposicion": prop.texto, "contexto": historia.resumen}
        prop.calidad = decidir("calidad_proposicion", estado)
        prop.divisividad = decidir("divisividad", estado)
        prop.estado = "publicada" if prop.calidad >= UMBRAL_CALIDAD() else "descartada"
        prop.save(update_fields=["calidad", "divisividad", "estado"])


MAX_COMPARACIONES_PROPOSICION = 12


def proposiciones_fijas(historia):
    """Proposiciones que no se pueden reemplazar: tienen votos o están en una jornada."""
    return historia.proposiciones.filter(
        Q(votos__isnull=False) | Q(jornadas__isnull=False)
    ).distinct()


def proposicion_repetida(prop: Proposicion) -> Proposicion | None:
    """Devuelve una proposición publicada que plantea la misma discusión, o None.

    Compara con las publicadas de la misma historia y con las de otras
    historias recientes del mismo tema. Jev decide; la caché es simétrica."""
    misma = Proposicion.objects.filter(historia=prop.historia, estado="publicada")
    otras = Proposicion.objects.none()
    if prop.tema:
        otras = Proposicion.objects.filter(
            estado="publicada",
            tema=prop.tema,
            creada_en__gte=timezone.now() - timedelta(days=14),
        ).exclude(historia=prop.historia)
    candidatas = list(misma.exclude(pk=prop.pk).order_by("pk")) + list(
        otras.order_by("-creada_en")[:MAX_COMPARACIONES_PROPOSICION]
    )
    for otra in candidatas:
        a, b = sorted([prop.texto, otra.texto])
        if decidir("misma_proposicion", {"A": a, "B": b}) >= UMBRAL_MISMA_PROPOSICION():
            return otra
    return None


# ---------------------------------------------------------------------------
# 6. Top del día, recrawl y cambios
# ---------------------------------------------------------------------------


def score_historia(h: Historia, ahora=None) -> float:
    ahora = ahora or timezone.now()
    horas = max(1.0, (ahora - h.ultima_fuente_en).total_seconds() / 3600)
    div = max(
        [p.divisividad or 0 for p in h.proposiciones.filter(estado="publicada")] or [0]
    )
    return h.n_medios * (1 + div) / (horas ** 0.5)


def historias_top(n=20, horas=48):
    desde = timezone.now() - timedelta(hours=horas)
    qs = Historia.objects.filter(procesada_en__isnull=False, ultima_fuente_en__gte=desde)
    return sorted(qs, key=score_historia, reverse=True)[:n]


def programar_recrawls(n=20):
    """Programa recrawl de las fuentes de las historias top que no lo tengan."""
    offsets = RECRAWL_OFFSETS_HORAS()
    if not offsets:
        return 0
    total = 0
    for h in historias_top(n):
        for f in h.fuentes.filter(
            proximo_recrawl__isnull=True, recrawls_hechos=0, ultimo_snapshot__isnull=False
        ):
            base = f.ultimo_snapshot.capturado_en
            f.proximo_recrawl = base + timedelta(hours=offsets[0])
            f.save(update_fields=["proximo_recrawl"])
            total += 1
    return total


def _diff(a: str, b: str):
    sm = difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False)
    ops = []
    wa, wb = a.split(), b.split()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            ops.append(["=", " ".join(wa[i1:i2])])
        else:
            if i2 > i1:
                ops.append(["-", " ".join(wa[i1:i2])])
            if j2 > j1:
                ops.append(["+", " ".join(wb[j1:j2])])
    return ops


def _tokens(texto: str) -> list[str]:
    return re.findall(r"\w+", texto.lower())


def _hunks(ops):
    """Agrupa las operaciones del diff en bloques de cambio. Un tramo igual de
    hasta 3 palabras entre dos cambios queda dentro del bloque (difflib parte
    un titular reemplazado por otro en las palabras que comparten)."""
    hunks, actual = [], None
    for i, (op, texto) in enumerate(ops):
        if op == "=":
            sigue = i + 1 < len(ops) and ops[i + 1][0] != "="
            if actual and sigue and len(texto.split()) <= 3:
                actual["-"].append(texto)
                actual["+"].append(texto)
                continue
            if actual:
                hunks.append(actual)
                actual = None
            continue
        actual = actual or {"-": [], "+": []}
        actual[op].append(texto)
    if actual:
        hunks.append(actual)
    return [{k: " ".join(v) for k, v in h.items()} for h in hunks]


def _es_titular(texto: str, titulares: list[set]) -> bool:
    toks = _tokens(texto)
    if not toks:
        return True
    if len(toks) < 4:
        return False
    return any(sum(t in tit for t in toks) / len(toks) >= 0.85 for tit in titulares)


def titulares_del_medio(fuente, dias=7) -> list[set]:
    """Titulares de otras notas del mismo medio en esos días: los sitios los
    muestran en bloques de «últimas noticias» que el extractor a veces incluye."""
    desde = (fuente.publicada_en or fuente.descubierta_en or timezone.now()) - timedelta(days=dias)
    titulos = (
        Fuente.objects.filter(medio_id=fuente.medio_id, descubierta_en__gte=desde)
        .exclude(pk=fuente.pk)
        .exclude(titulo="")
        .values_list("titulo", flat=True)
    )
    return [set(_tokens(t)) for t in titulos]


def clasificar_cambio_cuerpo(antes: str, despues: str, fuente) -> str:
    """«igual», «recorte» (la nueva captura es mucho más corta: muro de pago o
    captura parcial), «completa» (la anterior era la recortada), «ruido» (solo
    cambian titulares de otras notas del medio) o «real»."""
    if " ".join(antes.split()) == " ".join(despues.split()):
        return "igual"
    ratio = len(despues) / max(1, len(antes))
    if ratio < RATIO_RECORTE():
        return "recorte"
    if ratio > 1 / RATIO_RECORTE():
        return "completa"
    hunks = _hunks(_diff(antes, despues))
    # Muro de pago: el texto se corta en una palabra seguida de «…».
    if ratio < 0.9 and any(re.search(r"\w…", h["+"]) and not re.search(r"\w…", h["-"]) for h in hunks):
        return "recorte"
    titulares = titulares_del_medio(fuente)
    if hunks and all(_es_titular(h["-"], titulares) and _es_titular(h["+"], titulares) for h in hunks):
        return "ruido"
    return "real"


def _siguiente_recrawl(fuente):
    offsets = RECRAWL_OFFSETS_HORAS()
    fuente.recrawls_hechos += 1
    if fuente.recrawls_hechos < len(offsets):
        primera = fuente.snapshots.order_by("capturado_en").first()
        fuente.proximo_recrawl = primera.capturado_en + timedelta(
            hours=offsets[fuente.recrawls_hechos]
        )
    else:
        fuente.proximo_recrawl = None


def recrawl(fuente: Fuente) -> Cambio | None:
    anterior = fuente.ultimo_snapshot
    if anterior is None:
        return None
    cambio = None

    status = comprobar_publicada(fuente.url)
    if status in (404, 410):
        cambio = Cambio.objects.create(
            fuente=fuente,
            antes=anterior,
            tipo="despublicada",
            titulo_antes=anterior.titulo,
            resumen="La nota ya no está disponible en el sitio del medio.",
        )
        fuente.estado = "despublicada"
        fuente.proximo_recrawl = None
        fuente.save(update_fields=["estado", "proximo_recrawl"])
        return cambio

    extractor = get_extractor()
    try:
        res = extractor.extract(fuente.url)
    except ExtractError as e:
        logger.info("Recrawl falló %s: %s", fuente.url, e)
        _siguiente_recrawl(fuente)
        fuente.save(update_fields=["recrawls_hechos", "proximo_recrawl"])
        return None
    registrar_uso(extractor.nombre, "recrawl")
    # Las dos versiones se comparan limpias: si no, un aviso nuevo del medio
    # (o uno que antes no se limpiaba) parece una edición.
    lineas = lineas_del_medio(fuente.medio, res.texto)
    res.texto = limpiar(res.texto, lineas)
    fuente.texto = limpiar(fuente.texto, lineas)

    cambio_titulo = res.titulo != anterior.titulo
    clase = "igual"
    if sha256(res.texto) != anterior.contenido_hash:
        clase = clasificar_cambio_cuerpo(fuente.texto, res.texto, fuente)
    if clase == "completa" and not cambio_titulo:
        # La captura anterior era la recortada: guardamos la completa sin
        # registrar un cambio.
        nuevo = guardar_snapshot(fuente, res)
        fuente.ultimo_snapshot = nuevo
        fuente.texto = res.texto
    elif clase in ("recorte", "ruido") and not cambio_titulo:
        logger.info("Recrawl %s: captura %s, no es un cambio", fuente.url, clase)
    elif cambio_titulo or clase == "real":
        nuevo = guardar_snapshot(fuente, res)
        texto_antes = fuente.texto
        tipo = "titulo" if cambio_titulo else "cuerpo"
        cambio = Cambio.objects.create(
            fuente=fuente,
            antes=anterior,
            despues=nuevo,
            tipo=tipo,
            titulo_antes=anterior.titulo,
            titulo_despues=res.titulo,
            diff=_diff(texto_antes, res.texto) if tipo == "cuerpo" else _diff(anterior.titulo, res.titulo),
        )
        if clase != "recorte":
            fuente.ultimo_snapshot = nuevo
            fuente.texto = res.texto
        analizar_cambio(cambio, texto_antes)

    _siguiente_recrawl(fuente)
    fuente.save()
    return cambio


def analizar_cambio(cambio: Cambio, texto_antes: str):
    cambiado = [op for op in cambio.diff if op[0] != "="]
    cambio.cambia_sentido = decidir(
        "cambia_sentido",
        {
            "titulo_antes": cambio.titulo_antes,
            "titulo_despues": cambio.titulo_despues,
            "cambios": cambiado[:40],
        },
    )
    quitado = sum(len(op[1]) for op in cambiado if op[0] == "-")
    agregado = sum(len(op[1]) for op in cambiado if op[0] == "+")
    if cambio.tipo == "titulo":
        cambio.resumen = f"Título cambiado: «{cambio.titulo_antes}» → «{cambio.titulo_despues}»"[:300]
    else:
        cambio.resumen = f"Cuerpo editado: {quitado} caracteres quitados, {agregado} agregados."
    cambio.save(update_fields=["cambia_sentido", "resumen"])


def fusionar_duplicadas() -> int:
    """Fusiona historias abiertas que resultan ser el mismo hecho (p.ej. notas
    que llegaron antes de que existiera la otra). La más nueva se absorbe en
    la más vieja, salvo que sus proposiciones ya tengan votos o estén en una
    jornada (no perdemos votos)."""
    abiertas = list(Historia.objects.filter(estado="abierta").exclude(centroide=[]).order_by("pk"))
    absorbidas, fusiones = set(), 0
    for i, vieja in enumerate(abiertas):
        if vieja.pk in absorbidas:
            continue
        for nueva in abiertas[i + 1 :]:
            if nueva.pk in absorbidas:
                continue
            if coseno(vieja.centroide, nueva.centroide) < SIM_DUDA():
                continue
            if nueva.proposiciones.filter(Q(votos__isnull=False) | Q(jornadas__isnull=False)).exists():
                continue
            a, b = vieja.fuentes.first(), nueva.fuentes.first()
            if not a or not b:
                continue
            p = decidir(
                "mismo_hecho",
                {
                    "A": {"titulo": a.titulo, "texto": (a.texto or a.bajada)[:800]},
                    "B": {"titulo": b.titulo, "texto": (b.texto or b.bajada)[:800]},
                },
            )
            if p < 0.5:
                continue
            with transaction.atomic():
                for f in nueva.fuentes.all():
                    _actualizar_centroide(vieja, f.embedding or nueva.centroide)
                nueva.fuentes.update(historia=vieja, estado="extraida")
                vieja.fuentes.filter(estado="procesada").update(estado="extraida")
                vieja.ultima_fuente_en = max(vieja.ultima_fuente_en, nueva.ultima_fuente_en)
                vieja.recalcular_n_medios()
                vieja.save()
                nueva.delete()
            absorbidas.add(nueva.pk)
            fusiones += 1
    return fusiones


def cerrar_historias():
    limite = timezone.now() - timedelta(hours=VENTANA_HISTORIA_HORAS)
    return Historia.objects.filter(estado="abierta", ultima_fuente_en__lt=limite).update(
        estado="cerrada"
    )
