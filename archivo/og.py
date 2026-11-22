"""Imágenes Open Graph (1200×630, monocromo) generadas en el servidor."""

import io
import os
import textwrap

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
FUENTES = os.path.join(settings.BASE_DIR, "core", "static", "core", "fonts")


def _fuente(tam, negrita=False):
    nombre = "JetBrainsMono-Bold.ttf" if negrita else "JetBrainsMono-Regular.ttf"
    return ImageFont.truetype(os.path.join(FUENTES, nombre), tam)


def _envolver(draw, texto, fuente, ancho_px, max_lineas):
    # Ancho aproximado por carácter (fuente monoespaciada)
    ancho_char = draw.textlength("M", font=fuente)
    lineas = textwrap.wrap(texto, width=max(10, int(ancho_px // ancho_char)))
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1][: max(0, len(lineas[-1]) - 1)].rstrip() + "…"
    return lineas


def imagen(titulo: str, arriba: str = "", abajo: str = "", invertida=False) -> bytes:
    fondo, tinta = ("black", "white") if invertida else ("white", "black")
    img = Image.new("RGB", (W, H), fondo)
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, W - 24, H - 24], outline=tinta, width=6)

    if arriba:
        d.text((72, 70), arriba, font=_fuente(30), fill=tinta)

    # Título: probamos tamaños de mayor a menor hasta que entre en 5 líneas
    for tam in (64, 56, 48, 42):
        f = _fuente(tam, negrita=True)
        lineas = _envolver(d, titulo, f, W - 144, 5)
        if len(lineas) * tam * 1.25 <= 360:
            break
    y = 140
    for linea in lineas:
        d.text((72, y), linea, font=f, fill=tinta)
        y += int(tam * 1.25)

    d.line([72, H - 120, W - 72, H - 120], fill=tinta, width=3)
    d.text((72, H - 100), "memoria.uy", font=_fuente(36, negrita=True), fill=tinta)
    if abajo:
        f = _fuente(28)
        d.text((W - 72 - d.textlength(abajo, font=f), H - 94), abajo, font=f, fill=tinta)

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
