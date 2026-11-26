"""Historias en formatos para máquinas: dict (JSON) y Markdown.

Llevan lo que produce memoria.uy (título propio de la historia, resumen,
hechos) y, de las notas, solo el título, el enlace y la cita breve que
respalda cada hecho. Nunca el cuerpo de las notas.
"""

from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify

AVISO = (
    "Hechos, resúmenes y datos de memoria.uy: CC BY 4.0 (citar a memoria.uy y enlazar la historia). "
    "Los títulos y citas de las notas pertenecen a sus medios y no entran en la licencia."
)


def _abs(path):
    return f"{settings.SITE_URL}{path}"


def _iso(dt):
    return dt.isoformat() if dt else None


def url_historia(h):
    return _abs(reverse("archivo:historia", args=[h.slug]))


def _fuente_de_hecho(hf):
    f = hf.fuente
    snap = f.ultimo_snapshot
    return {
        "medio": f.medio.nombre,
        "url": f.url,
        "titulo": f.titulo,
        "cita": hf.cita or None,
        "capturado_en": _iso(snap.capturado_en) if snap else None,
        "sha256": snap.contenido_hash if snap else None,
    }


def historia_dict(h, hechos, fuentes, entidades, proposiciones=()):
    """`hechos`: Hecho con `respaldos` (un HechoFuente por medio)."""
    url = url_historia(h)
    return {
        "id": h.slug,
        "url": url,
        "titulo": h.titulo,
        "resumen": h.resumen,
        "categoria": h.categoria or None,
        "primera_nota_en": _iso(h.primera_fuente_en),
        "actualizada_en": _iso(h.procesada_en or h.ultima_fuente_en),
        "n_medios": h.n_medios,
        "licencia": {"nombre": settings.LICENCIA_NOMBRE, "url": settings.LICENCIA_URL, "aviso": AVISO},
        "hechos": [
            {
                "id": f"hecho-{x.pk}",
                "url": f"{url}#hecho-{x.pk}",
                "texto": x.texto,
                "fuentes_difieren": x.disputado,
                "entidades": [e.nombre for e in x.entidades.all()],
                "fuentes": [_fuente_de_hecho(hf) for hf in x.respaldos],
            }
            for x in hechos
        ],
        "notas": [
            {
                "medio": f.medio.nombre,
                "url": f.url,
                "titulo": f.titulo,
                "publicada_en": _iso(f.publicada_en),
                "despublicada": f.estado == "despublicada",
            }
            for f in fuentes
        ],
        "entidades": [
            {
                "nombre": e.nombre,
                "tipo": e.tipo,
                "url": _abs(reverse("archivo:entidad-slug", args=[e.pk, slugify(e.nombre) or "x"])),
            }
            for e in entidades
        ],
        "frases_para_opinar": [p.texto for p in proposiciones],
    }


def historia_markdown(d) -> str:
    """Markdown de `historia_dict`."""
    L = [f"# {d['titulo']}", ""]
    meta = [f"Primera nota: {d['primera_nota_en'][:10]}", f"actualizada: {d['actualizada_en'][:10]}", f"{d['n_medios']} medio(s)"]
    if d["categoria"]:
        meta.insert(0, f"Tema: {d['categoria']}")
    L += [" · ".join(meta), "", d["resumen"], "", "## Hechos", ""]
    for i, x in enumerate(d["hechos"], 1):
        marca = " (las fuentes difieren)" if x["fuentes_difieren"] else ""
        L.append(f"{i}. {x['texto']}{marca} [#]({x['url']})")
        for f in x["fuentes"]:
            linea = f"   - [{f['medio']}]({f['url']})"
            if f["cita"]:
                linea += f": «{f['cita']}»"
            if f["capturado_en"]:
                linea += f" (capturada {f['capturado_en']}, sha256 {f['sha256'][:12]}…)"
            L.append(linea)
    if not d["hechos"]:
        L.append("Sin hechos verificados.")
    L += ["", "## Qué publicó cada medio", ""]
    for n in d["notas"]:
        L.append(f"- {n['publicada_en'][:16].replace('T', ' ') if n['publicada_en'] else ''} [{n['medio']}: {n['titulo']}]({n['url']})" + (" (despublicada)" if n["despublicada"] else ""))
    if d["entidades"]:
        L += ["", "## Quiénes aparecen", ""]
        L += [f"- [{e['nombre']}]({e['url']}) ({e['tipo']})" for e in d["entidades"]]
    L += ["", "---", "", f"Fuente: {d['url']}", "", f"Licencia: [{d['licencia']['nombre']}]({d['licencia']['url']}). {AVISO}", ""]
    return "\n".join(L)
