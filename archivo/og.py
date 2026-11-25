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


def imagen_entidad(nombre: str, filas: list, abajo: str = "") -> bytes:
    """Nombre de la persona y una barra de tono por medio (−2..+2), hasta 5 medios.

    `filas`: dicts con `medio` (objeto con `.nombre`), `promedio` y `n`.
    """
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, W - 24, H - 24], outline="black", width=6)

    d.text((72, 62), "Cómo queda en cada medio", font=_fuente(28), fill="black")
    for tam in (60, 52, 44):
        f = _fuente(tam, negrita=True)
        lineas = _envolver(d, nombre, f, W - 144, 2)
        if len(lineas) == 1 or tam == 44:
            break
    y = 104
    for linea in lineas:
        d.text((72, y), linea, font=f, fill="black")
        y += int(tam * 1.2)

    top = y + 20
    paso = 58
    filas = filas[: max(1, (H - 130 - top) // paso)]
    x0, x1 = 72, W - 72
    ancho_barra = 640
    bx = x1 - ancho_barra
    fn, fv = _fuente(26, negrita=True), _fuente(24)
    for i, fila in enumerate(filas):
        yy = top + i * paso
        nom = fila["medio"].nombre
        while d.textlength(nom, font=fn) > bx - x0 - 20 and len(nom) > 3:
            nom = nom[:-2].rstrip() + "…"
        d.text((x0, yy), nom, font=fn, fill="black")
        # barra con degradé rojo → blanco → verde, como en la página
        for dx in range(ancho_barra):
            t = dx / (ancho_barra - 1)
            if t < 0.5:
                c = (254, int(202 + 53 * t * 2), int(202 + 53 * t * 2))
            else:
                k = (t - 0.5) * 2
                c = (int(255 - 55 * k), 255 - int(21 * k), int(255 - 55 * k))
            d.line([bx + dx, yy + 2, bx + dx, yy + 30], fill=c)
        d.rectangle([bx, yy + 2, bx + ancho_barra, yy + 30], outline="black", width=3)
        d.line([bx + ancho_barra // 2, yy + 2, bx + ancho_barra // 2, yy + 30], fill=(150, 150, 150), width=1)
        pos = bx + int((fila["promedio"] + 2) / 4 * ancho_barra)
        pos = min(max(pos, bx + 6), bx + ancho_barra - 6)
        d.rectangle([pos - 6, yy - 2, pos + 6, yy + 34], fill="black")
        n = fila["n"]
        etiqueta = f"{fila['promedio']:+.1f} · {n} nota{'s' if n != 1 else ''}".replace(".", ",")
        d.text((x0, yy + 32), etiqueta, font=fv, fill=(90, 90, 90))
    if not filas:
        d.text((72, top), "Todo lo que pasó con esta persona, con fuentes.", font=_fuente(32), fill="black")

    d.line([72, H - 120, W - 72, H - 120], fill="black", width=3)
    d.text((72, H - 100), "memoria.uy", font=_fuente(36, negrita=True), fill="black")
    if abajo:
        f = _fuente(28)
        d.text((W - 72 - d.textlength(abajo, font=f), H - 94), abajo, font=f, fill="black")

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
