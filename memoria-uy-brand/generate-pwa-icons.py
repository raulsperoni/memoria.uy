#!/usr/bin/env python3
"""Íconos del sitio (PWA, apple-touch, favicon) dibujados desde la marca,
`src/logo/memoria-uy-mark.svg`: no hay que copiar el dibujo a mano ni hace
falta ImageMagick (para eso está generate-exports.sh). Solo Pillow.

    poetry run python memoria-uy-brand/generate-pwa-icons.py

Salida en core/static/core/ (se versiona; el build no regenera).
"""

import re
from pathlib import Path

from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent
SVG = AQUI / "src" / "logo" / "memoria-uy-mark.svg"
SALIDA = AQUI.parent / "core" / "static" / "core"
BLANCO = (255, 255, 255)


def rects(svg: Path):
    """(x, y, ancho, alto, color) de cada <rect> del SVG, en la grilla de 100."""
    for m in re.finditer(r"<rect\s+([^>]*?)/>", svg.read_text()):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        color = a["fill"].lstrip("#")
        color = "".join(c * 2 for c in color) if len(color) == 3 else color
        yield float(a.get("x", 0)), float(a.get("y", 0)), float(a["width"]), float(a["height"]), tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def marca(tam: int, escala: float = 1.0, fondo=BLANCO) -> Image.Image:
    """La marca centrada en un lienzo opaco de tam×tam; `escala` es la
    fracción del lienzo que ocupa. Los bordes de cada celda caen en píxeles
    enteros (sin líneas de unión entre celdas)."""
    lienzo = Image.new("RGB", (tam, tam), fondo)
    lado = tam * escala
    ini = (tam - lado) / 2
    d = ImageDraw.Draw(lienzo)
    for x, y, w, h, color in rects(SVG):
        x0, y0 = round(ini + x * lado / 100), round(ini + y * lado / 100)
        x1, y1 = round(ini + (x + w) * lado / 100), round(ini + (y + h) * lado / 100)
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=color)
    return lienzo


def guardar(img: Image.Image, nombre: str, **kw):
    destino = SALIDA / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, optimize=True, **kw)
    print("→", destino.relative_to(AQUI.parent), img.size)


if __name__ == "__main__":
    # purpose "any": a sangre
    guardar(marca(192), "icons/icon-192.png")
    guardar(marca(512), "icons/icon-512.png")
    # purpose "maskable": Android recorta un círculo de radio 40 % del lado;
    # la diagonal de la marca tiene que entrar ahí → 56 % del lado como máximo.
    guardar(marca(512, escala=0.56), "icons/icon-maskable-512.png")
    # iOS: 180×180 opaco, redondea las esquinas solo; con margen
    guardar(marca(180, escala=0.76), "icons/apple-touch-icon-180.png")
    # favicon: a sangre, sin líneas finas
    guardar(marca(32), "favicon-32x32.png")
    guardar(marca(16), "favicon-16x16.png")
    guardar(marca(48), "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], format="ICO")
