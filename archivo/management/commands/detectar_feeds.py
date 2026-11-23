"""Detecta RSS y sitemaps de noticias de cada medio y los guarda.

Busca: <link rel=alternate type=rss> en la home, rutas comunes (/rss, /feed…)
y `Sitemap:` en robots.txt (prefiriendo sitemaps de noticias).
"""

import re
from urllib.parse import urljoin

import feedparser
import requests
from django.core.management.base import BaseCommand

from archivo.models import Medio
from archivo.providers.extract import USER_AGENT

RUTAS_RSS = ["/rss", "/feed", "/rss.xml", "/feed.xml", "/rss/", "/feed/", "/rss/portada", "/arc/outboundfeeds/rss/"]
H = {"User-Agent": USER_AGENT}


def _get(url):
    try:
        r = requests.get(url, headers=H, timeout=20)
        return r if r.status_code == 200 else None
    except requests.RequestException:
        return None


def _es_feed(url):
    r = _get(url)
    if not r:
        return False
    f = feedparser.parse(r.content)
    return len(f.entries) > 0


def detectar(medio):
    base = f"https://{'www.' if medio.dominio.count('.') <= 2 and not medio.dominio.startswith('www.') else ''}{medio.dominio}"
    rss, sitemaps = [], []

    home = _get(base) or _get(f"https://{medio.dominio}")
    if home:
        base = home.url.rstrip("/")
        for href in re.findall(
            r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)', home.text
        ):
            u = urljoin(base + "/", href)
            if u not in rss and _es_feed(u):
                rss.append(u)
    if not rss:
        for ruta in RUTAS_RSS:
            u = base + ruta
            if _es_feed(u):
                rss.append(u)
                break

    robots = _get(base + "/robots.txt")
    if robots:
        todos = re.findall(r"(?im)^sitemap:\s*(\S+)", robots.text)
        noticias = [s for s in todos if "news" in s.lower() or "noticia" in s.lower()]
        sitemaps = noticias[:2]
    return rss[:3], sitemaps


class Command(BaseCommand):
    help = "Detecta feeds RSS y sitemaps de noticias de los medios activos."

    def add_arguments(self, parser):
        parser.add_argument("--forzar", action="store_true", help="Re-detectar aunque ya tengan feeds")

    def handle(self, *args, forzar=False, **opts):
        for medio in Medio.objects.filter(activo=True):
            if (medio.rss_urls or medio.sitemap_urls) and not forzar:
                self.stdout.write(f"= {medio.nombre}: ya tiene feeds")
                continue
            rss, sm = detectar(medio)
            medio.rss_urls, medio.sitemap_urls = rss, sm
            medio.save(update_fields=["rss_urls", "sitemap_urls"])
            estado = "OK" if (rss or sm) else "SIN FEEDS (cargar a mano en admin)"
            self.stdout.write(f"{medio.nombre}: {estado} rss={rss} sitemaps={sm}")
