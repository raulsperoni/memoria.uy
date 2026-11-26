"""Manifest, íconos y service worker."""

import re
from pathlib import Path

from django.conf import settings
from PIL import Image

ESTATICOS = Path(settings.BASE_DIR) / "core" / "static"


def _archivo(src):
    # el src puede traer hash; el original sigue en core/static
    nombre = re.sub(r"\.[0-9a-f]{12}(\.\w+)$", r"\1", src.removeprefix("/static/"))
    return ESTATICOS / nombre


def test_manifest_completo(client, db):
    r = client.get("/manifest.webmanifest")
    m = r.json()
    assert m["id"] == "/" and m["start_url"].startswith("/") and m["display"] == "standalone"
    assert m["theme_color"] == "#ffffff" == m["background_color"]
    html = client.get("/").content.decode()
    assert '<meta name="theme-color" content="#ffffff">' in html
    assert {s["form_factor"] for s in m["screenshots"]} == {"wide", "narrow"}
    for s in m["screenshots"]:
        w, h = Image.open(_archivo(s["src"])).size
        assert s["sizes"] == f"{w}x{h}"


def test_iconos_any_y_maskable_separados(client):
    icons = client.get("/manifest.webmanifest").json()["icons"]
    assert all(i["purpose"] in ("any", "maskable") for i in icons)  # nunca "any maskable"
    assert {(i["sizes"], i["purpose"]) for i in icons} >= {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")}
    for i in icons:
        img = Image.open(_archivo(i["src"]))
        assert f"{img.width}x{img.height}" == i["sizes"]
        assert img.mode == "RGB"  # opaco, sin alfa


def test_maskable_tiene_la_marca_dentro_de_la_zona_segura():
    img = Image.open(ESTATICOS / "core/icons/icon-maskable-512.png").convert("L")
    tam = img.width
    # ningún píxel negro fuera del círculo de radio 40 % del lado
    cx = cy = tam / 2
    for y in range(0, tam, 4):
        for x in range(0, tam, 4):
            if img.getpixel((x, y)) < 128:
                assert (x - cx) ** 2 + (y - cy) ** 2 <= (0.4 * tam) ** 2, (x, y)


def test_icono_a_sangre_es_la_marca_de_la_marca():
    """13 celdas negras y 3 blancas, como memoria-uy-mark.svg (no al revés)."""
    img = Image.open(ESTATICOS / "core/icons/icon-512.png").convert("L")
    celdas = [img.getpixel((int((c + 0.5) * 128), int((f + 0.5) * 128))) < 128 for f in range(4) for c in range(4)]
    assert sum(celdas) == 13 and celdas[6] is False and celdas[9] is False and celdas[15] is False


def test_apple_touch_icon_180_opaco(client, db):
    html = client.get("/").content.decode()
    assert re.search(r'rel="apple-touch-icon" sizes="180x180" href="/static/core/icons/apple-touch-icon-180(\.[0-9a-f]{12})?\.png"', html)
    img = Image.open(ESTATICOS / "core/icons/apple-touch-icon-180.png")
    assert img.size == (180, 180) and img.mode == "RGB"


def test_service_worker_no_guarda_lo_personal(client):
    r = client.get("/sw.js")
    assert r.status_code == 200 and "javascript" in r["Content-Type"] and r["Cache-Control"] == "no-cache"
    js = r.content.decode()
    assert "/opinar/" in js and "'/hoy/'" in js and "memoria-v3" in js
