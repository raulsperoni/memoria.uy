"""
Extracción de artículos.

- CloudflareExtractor: Browser Rendering `/content` (HTML renderizado) +
  trafilatura local para quedarse con el texto del artículo.
- TrafilaturaExtractor: descarga directa (gratis; fallback y desarrollo).
- FakeExtractor: tests.

Env: EXTRACTOR=cloudflare|trafilatura|fake, CLOUDFLARE_ACCOUNT_ID,
CLOUDFLARE_API_TOKEN.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

import requests
import trafilatura

logger = logging.getLogger(__name__)

USER_AGENT = "memoria.uy archivo (+https://memoria.uy/acerca-de/)"


class ExtractError(Exception):
    """Fallo de extracción (reintentable salvo que `permanente`)."""

    def __init__(self, msg, permanente=False, status=None):
        super().__init__(msg)
        self.permanente = permanente
        self.status = status


@dataclass
class ExtractResult:
    url: str
    status: int
    html: str
    titulo: str = ""
    texto: str = ""
    autor: str = ""
    fecha: str = ""
    proveedor: str = ""
    meta: dict = field(default_factory=dict)


def limpiar_html(url: str, html: str) -> dict:
    """Extrae título, texto y metadatos de un HTML de artículo."""
    texto = (
        trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        or ""
    )
    meta = trafilatura.extract_metadata(html, default_url=url)
    return {
        "texto": texto.strip(),
        "titulo": (meta.title if meta and meta.title else "").strip(),
        "autor": (meta.author if meta and meta.author else "").strip(),
        "fecha": (meta.date if meta and meta.date else "") or "",
    }


class Extractor:
    nombre = "base"

    def fetch_html(self, url: str) -> tuple[int, str]:
        raise NotImplementedError

    def extract(self, url: str) -> ExtractResult:
        status, html = self.fetch_html(url)
        if status in (404, 410):
            raise ExtractError(f"{status} en {url}", permanente=True, status=status)
        if status >= 400:
            raise ExtractError(f"{status} en {url}", status=status)
        datos = limpiar_html(url, html)
        if len(datos["texto"]) < 200:
            raise ExtractError(f"texto demasiado corto en {url}", status=status)
        return ExtractResult(url=url, status=status, html=html, proveedor=self.nombre, **datos)


class CloudflareExtractor(Extractor):
    nombre = "cloudflare"

    def __init__(self, account_id=None, token=None, timeout=60, reintentos=3):
        self.account_id = account_id or os.environ["CLOUDFLARE_ACCOUNT_ID"]
        # En sandbox el proxy inyecta el token; cualquier valor sirve.
        self.token = token or os.environ.get("CLOUDFLARE_API_TOKEN", "proxy-injected")
        self.timeout = timeout
        self.reintentos = reintentos
        self.ms_usados = 0.0

    def fetch_html(self, url):
        endpoint = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/browser-rendering/content"
        )
        payload = {
            "url": url,
            "rejectResourceTypes": ["image", "media", "font", "stylesheet"],
            "gotoOptions": {"waitUntil": "domcontentloaded", "timeout": 30000},
            "userAgent": USER_AGENT,
        }
        espera = 5
        for intento in range(self.reintentos + 1):
            resp = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {self.token}"},
                json=payload,
                timeout=self.timeout,
            )
            if resp.status_code != 429 or intento == self.reintentos:
                break
            # Rate limit de Cloudflare: esperar y reintentar.
            time.sleep(float(resp.headers.get("Retry-After") or espera))
            espera *= 2
        if resp.status_code == 429:
            raise ExtractError("cloudflare rate limit", status=429)
        if resp.status_code >= 400:
            raise ExtractError(
                f"cloudflare {resp.status_code}: {resp.text[:200]}", status=resp.status_code
            )
        data = resp.json()
        if not data.get("success"):
            raise ExtractError(f"cloudflare error: {data.get('errors')}")
        self.ms_usados += float(resp.headers.get("X-Browser-Ms-Used") or 0)
        return 200, data.get("result") or ""


class TrafilaturaExtractor(Extractor):
    nombre = "trafilatura"

    def fetch_html(self, url):
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        return resp.status_code, resp.text


class FakeExtractor(Extractor):
    """Devuelve HTML registrado en `paginas` (url -> (status, html))."""

    nombre = "fake"

    def __init__(self, paginas=None):
        self.paginas = paginas or {}

    def fetch_html(self, url):
        if url not in self.paginas:
            return 404, ""
        return self.paginas[url]


_override = None


def set_extractor(extractor):
    """Para tests: fuerza un extractor."""
    global _override
    _override = extractor


def get_extractor(nombre: str | None = None) -> Extractor:
    if _override is not None and nombre is None:
        return _override
    nombre = nombre or os.environ.get("EXTRACTOR", "trafilatura")
    return {
        "cloudflare": CloudflareExtractor,
        "trafilatura": TrafilaturaExtractor,
        "fake": FakeExtractor,
    }[nombre]()


def comprobar_publicada(url: str) -> int | None:
    """HEAD gratis para detectar notas despublicadas. Devuelve status o None."""
    try:
        resp = requests.head(
            url, headers={"User-Agent": USER_AGENT}, timeout=15, allow_redirects=True
        )
    except requests.RequestException:
        return None
    # Redirect a la home del medio = despublicada.
    if resp.history and resp.url.rstrip("/").count("/") <= 2:
        return 410
    return resp.status_code
