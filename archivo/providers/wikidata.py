"""
Datos de una entidad en Wikidata y Wikipedia (APIs públicas, gratis).

- WikidataEnriquecedor: wbsearchentities + wbgetentities (Wikidata), imageinfo
  (Commons) y REST summary (Wikipedia en español). Serie, con pausa entre
  pedidos, User-Agent del proyecto y reintento si responden 429/maxlag.
- FakeEnriquecedor: tests.

Solo devuelve candidatos uruguayos: personas con ciudadanía Uruguay (P27),
organizaciones y lugares con país Uruguay (P17). Decidir si un candidato es la
entidad de las noticias no se hace acá: ver archivo/entidades_wikidata.py.

Env: ENRIQUECEDOR=wikidata|fake
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field, replace

import requests

USER_AGENT = "memoria.uy bot (+https://memoria.uy/acerca-de/)"
URUGUAY = "Q77"
HUMANO = "Q5"
PAUSA = 0.3  # segundos entre pedidos

API_WD = "https://www.wikidata.org/w/api.php"
API_COMMONS = "https://commons.wikimedia.org/w/api.php"
API_WP = "https://es.wikipedia.org/api/rest_v1/page/summary/"


@dataclass
class Datos:
    qid: str
    etiqueta: str = ""
    nombres: list = field(default_factory=list)  # etiqueta + alias, para comparar nombres
    descripcion: str = ""
    cargo: str = ""
    organizacion: str = ""
    wikipedia_titulo: str = ""
    wikipedia_url: str = ""
    resumen: str = ""
    foto_archivo: str = ""  # nombre del archivo en Commons (P18)
    foto_url: str = ""
    foto_pagina: str = ""
    foto_autor: str = ""
    foto_licencia: str = ""


class Enriquecedor:
    nombre = "base"

    def buscar(self, nombre: str, tipo: str) -> list[Datos]:
        """Candidatos uruguayos para ese nombre, sin foto ni resumen."""
        raise NotImplementedError

    def obtener(self, qid: str) -> Datos | None:
        """Un ítem por QID (sin foto ni resumen). None si no existe."""
        raise NotImplementedError

    def detalle(self, datos: Datos) -> Datos:
        """Agrega foto con atribución y resumen de Wikipedia."""
        raise NotImplementedError


def _qids(claims, prop, vigentes=False):
    """QIDs de un reclamo. `vigentes`: sin fecha de fin (P582)."""
    out = []
    for c in claims.get(prop, []):
        if c.get("rank") == "deprecated":
            continue
        if vigentes and "P582" in c.get("qualifiers", {}):
            continue
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            out.append((v["id"], c))
    return out


def _inicio(c):
    for q in c.get("qualifiers", {}).get("P580", []):
        t = q.get("datavalue", {}).get("value", {}).get("time", "")
        if t:
            return t
    return ""


class WikidataEnriquecedor(Enriquecedor):
    nombre = "wikidata"

    def __init__(self, pausa=PAUSA):
        self.pausa = pausa
        self.sesion = requests.Session()
        self.sesion.headers["User-Agent"] = USER_AGENT
        self._ultimo = 0.0

    def _get(self, url, **params):
        for intento in range(3):
            espera = self.pausa - (time.monotonic() - self._ultimo)
            if espera > 0:
                time.sleep(espera)
            self._ultimo = time.monotonic()
            resp = self.sesion.get(url, params=params, timeout=20)
            if resp.status_code == 404:
                return None
            data = resp.json() if resp.ok else {}
            lag = isinstance(data, dict) and data.get("error", {}).get("code") == "maxlag"
            if resp.status_code in (429, 503) or lag:
                time.sleep(min(float(resp.headers.get("Retry-After", 5)), 30))
                continue
            resp.raise_for_status()
            return data
        raise RuntimeError(f"{url} no responde (límite de pedidos)")

    def _wd(self, **params):
        return self._get(API_WD, format="json", maxlag=5, **params)

    def _etiquetas(self, qids):
        qids = sorted(set(qids))
        if not qids:
            return {}
        data = self._wd(action="wbgetentities", ids="|".join(qids), props="labels", languages="es|en")
        out = {}
        for q, e in (data or {}).get("entities", {}).items():
            ls = e.get("labels", {})
            out[q] = (ls.get("es") or ls.get("en") or {}).get("value", "")
        return out

    def _armar(self, e, tipo=None):
        """Item de wbgetentities → Datos, o None si no es uruguayo / no es del tipo."""
        claims = e.get("claims", {})
        humano = any(q == HUMANO for q, _ in _qids(claims, "P31"))
        if tipo == "persona":
            if not humano or URUGUAY not in [q for q, _ in _qids(claims, "P27")]:
                return None
        elif tipo in ("organizacion", "lugar"):
            if humano or URUGUAY not in [q for q, _ in _qids(claims, "P17")]:
                return None
        labels, aliases = e.get("labels", {}), e.get("aliases", {})
        nombres = [l["value"] for l in labels.values()]
        nombres += [a["value"] for lang in ("es", "en") for a in aliases.get(lang, [])]
        etiqueta = (labels.get("es") or labels.get("en") or {}).get("value", "")
        wp = e.get("sitelinks", {}).get("eswiki", {}).get("title", "")
        cargos = sorted(_qids(claims, "P39", vigentes=True), key=lambda x: _inicio(x[1]), reverse=True)
        partidos = sorted(_qids(claims, "P102", vigentes=True), key=lambda x: _inicio(x[1]), reverse=True)
        if not cargos:  # sin cargo vigente: la ocupación
            cargos = _qids(claims, "P106")[:2]
        pedir = [q for q, _ in cargos[:2]] + [q for q, _ in partidos[:2]]
        et = self._etiquetas(pedir)
        foto = _qids_texto(claims, "P18")
        return Datos(
            qid=e["id"],
            etiqueta=etiqueta,
            nombres=nombres,
            descripcion=(e.get("descriptions", {}).get("es") or {}).get("value", ""),
            cargo=", ".join(filter(None, (et.get(q) for q, _ in cargos[:2]))),
            organizacion=", ".join(filter(None, (et.get(q) for q, _ in partidos[:2]))),
            wikipedia_titulo=wp,
            wikipedia_url=f"https://es.wikipedia.org/wiki/{wp.replace(' ', '_')}" if wp else "",
            foto_archivo=foto,
        )

    def _items(self, qids):
        data = self._wd(
            action="wbgetentities", ids="|".join(qids), languages="es|en",
            props="labels|aliases|descriptions|claims|sitelinks",
        )
        return (data or {}).get("entities", {})

    def buscar(self, nombre, tipo):
        data = self._wd(
            action="wbsearchentities", search=nombre, language="es", uselang="es",
            type="item", limit=7,
        )
        qids = [r["id"] for r in (data or {}).get("search", [])]
        if not qids:
            return []
        out = []
        for e in self._items(qids).values():
            d = self._armar(e, tipo)
            if d:
                out.append(d)
        return out

    def obtener(self, qid):
        e = self._items([qid]).get(qid)
        if not e or "missing" in e:
            return None
        return self._armar(e)

    def detalle(self, datos):
        d = replace(datos)
        if d.foto_archivo:
            self._foto(d)
        if d.wikipedia_titulo:
            r = self._get(API_WP + requests.utils.quote(d.wikipedia_titulo.replace(" ", "_"), safe=""))
            if r and r.get("type") == "standard":
                d.resumen = r.get("extract", "")
        return d

    def _foto(self, d):
        data = self._get(
            API_COMMONS, action="query", format="json", titles=f"File:{d.foto_archivo}",
            prop="imageinfo", iiprop="url|extmetadata", iiurlwidth=320,
        )
        for p in (data or {}).get("query", {}).get("pages", {}).values():
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            d.foto_url = info.get("thumburl") or info.get("url", "")
            d.foto_pagina = info.get("descriptionurl", "")
            d.foto_autor = _texto(meta.get("Artist", {}).get("value", ""))
            d.foto_licencia = _texto(meta.get("LicenseShortName", {}).get("value", ""))


def _qids_texto(claims, prop):
    for c in claims.get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, str) and c.get("rank") != "deprecated":
            return v
    return ""


def _texto(html):
    return " ".join(re.sub(r"<[^>]+>", "", html).split())[:300]


class FakeEnriquecedor(Enriquecedor):
    """`items`: lista de Datos. `buscar` devuelve los que tengan `nombre` entre sus nombres."""

    nombre = "fake"

    def __init__(self, items=None):
        self.items = {d.qid: d for d in (items or [])}
        self.llamadas = []

    def buscar(self, nombre, tipo):
        self.llamadas.append(("buscar", nombre))
        palabras = set(nombre.lower().split())
        return [
            d for d in self.items.values()
            if any(palabras & set(n.lower().split()) for n in d.nombres)
        ]

    def obtener(self, qid):
        self.llamadas.append(("obtener", qid))
        return self.items.get(qid)

    def detalle(self, datos):
        self.llamadas.append(("detalle", datos.qid))
        return datos


_override = None


def set_enriquecedor(e):
    global _override
    _override = e


def get_enriquecedor(nombre: str | None = None) -> Enriquecedor:
    if _override is not None and nombre is None:
        return _override
    nombre = nombre or os.environ.get("ENRIQUECEDOR", "wikidata")
    return {"wikidata": WikidataEnriquecedor, "fake": FakeEnriquecedor}[nombre]()
