"""Datos estructurados (schema.org / JSON-LD) de las páginas públicas.

Cada función devuelve un dict listo para `jsonld()`. Lo que produce
memoria.uy (hechos, resúmenes, datos) va con licencia CC BY 4.0; los títulos
y citas de las notas son de sus medios (docs/decisiones/0015).
"""

import json

from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify

CONTEXT = "https://schema.org"


def _abs(path):
    return f"{settings.SITE_URL}{path}"


def jsonld(datos) -> str:
    """Serializa para pegar dentro de <script type="application/ld+json">.
    Escapa `<` (así un título con `</script>` no rompe la página)."""
    return json.dumps(datos, ensure_ascii=False).replace("<", "\\u003c")


def organizacion():
    return {
        "@type": "Organization",
        "@id": _abs("/#organizacion"),
        "name": "memoria.uy",
        "url": _abs("/"),
        "logo": _abs("/static/core/icons/icon-512.png"),
        "sameAs": ["https://github.com/raulsperoni/memoria.uy"],
    }


def _org_ref():
    return {"@id": _abs("/#organizacion")}


def sitio():
    """Home: el sitio, con búsqueda, y quién lo publica."""
    return {
        "@context": CONTEXT,
        "@graph": [
            organizacion(),
            {
                "@type": "WebSite",
                "@id": _abs("/#sitio"),
                "url": _abs("/"),
                "name": "memoria.uy",
                "description": "Lo que pasó en Uruguay, con fuentes.",
                "inLanguage": "es-UY",
                "publisher": _org_ref(),
                "license": settings.LICENCIA_URL,
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": {"@type": "EntryPoint", "urlTemplate": _abs(reverse("archivo:buscar")) + "?q={search_term_string}"},
                    "query-input": "required name=search_term_string",
                },
            },
        ],
    }


def migas(*items):
    """BreadcrumbList. `items`: (nombre, path); el último puede no tener path."""
    lista = []
    for i, (nombre, path) in enumerate(items, 1):
        el = {"@type": "ListItem", "position": i, "name": nombre}
        if path:
            el["item"] = _abs(path)
        lista.append(el)
    return {"@type": "BreadcrumbList", "itemListElement": lista}


def _nota(fuente):
    return {
        "@type": "NewsArticle",
        "url": fuente.url,
        "headline": fuente.titulo,
        "publisher": {"@type": "Organization", "name": fuente.medio.nombre},
    }


TIPOS_ENTIDAD = {"persona": "Person", "organizacion": "Organization", "lugar": "Place", "otro": "Thing"}


def entidad_ref(e):
    return {
        "@type": TIPOS_ENTIDAD.get(e.tipo, "Thing"),
        "name": e.nombre,
        "url": _abs(reverse("archivo:entidad-slug", args=[e.pk, slugify(e.nombre) or "x"])),
    }


def historia(h, hechos, fuentes, entidades):
    """NewsArticle con la procedencia: cada hecho es un `Claim` que aparece
    en las notas que lo respaldan. No hay `ClaimReview` ni `reviewRating`:
    «disputado» no se puede mapear honestamente a una calificación."""
    url = _abs(reverse("archivo:historia", args=[h.slug]))
    partes = []
    for hecho in hechos:
        partes.append(
            {
                "@type": "Claim",
                "@id": f"{url}#hecho-{hecho.pk}",
                "text": hecho.texto,
                "appearance": [_nota(hf.fuente) for hf in hecho.respaldos],
            }
        )
    articulo = {
        "@type": "NewsArticle",
        "@id": f"{url}#historia",
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "url": url,
        "headline": h.titulo[:110],
        "name": h.titulo,
        "description": h.resumen,
        "abstract": h.resumen,
        "datePublished": h.primera_fuente_en.isoformat(),
        "dateModified": (h.procesada_en or h.ultima_fuente_en).isoformat(),
        "inLanguage": "es-UY",
        "image": _abs(reverse("archivo:og-historia", args=[h.slug])),
        "isAccessibleForFree": True,
        "license": settings.LICENCIA_URL,
        "author": _org_ref(),
        "publisher": _org_ref(),
        "citation": [_nota(f) for f in fuentes],
        "hasPart": partes,
    }
    if h.categoria:
        articulo["articleSection"] = h.get_categoria_display()
    if entidades:
        articulo["about"] = [entidad_ref(e) for e in entidades]
    return {
        "@context": CONTEXT,
        "@graph": [
            articulo,
            organizacion(),
            migas(("Inicio", "/"), *([(h.get_categoria_display(), reverse("archivo:tema", args=[h.categoria]))] if h.categoria else []), (h.titulo, None)),
        ],
    }


def datos_entidad_extra(entidad) -> dict:
    """Punto de extensión: campos extra del JSON-LD de la entidad (`sameAs`,
    `image`, `description`, `birthDate`…). Hoy no hay ninguno; cuando la
    entidad tenga datos externos (p. ej. Wikidata) se devuelven acá y se
    suman sin tocar el resto."""
    return {}


def entidad(e, historias):
    url = entidad_ref(e)["url"]
    nodo = {
        **entidad_ref(e),
        "@id": f"{url}#entidad",
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "subjectOf": [
            {
                "@type": "NewsArticle",
                "headline": h.titulo,
                "url": _abs(reverse("archivo:historia", args=[h.slug])),
                "datePublished": h.primera_fuente_en.isoformat(),
            }
            for h in historias[:20]
        ],
    }
    nodo.update(datos_entidad_extra(e))
    return {
        "@context": CONTEXT,
        "@graph": [nodo, migas(("Inicio", "/"), (e.nombre, None))],
    }


def cambio(c):
    url = _abs(reverse("archivo:cambio", args=[c.pk]))
    titulo = c.titulo_despues if c.tipo == "titulo" and c.titulo_despues else (c.titulo_antes or c.fuente.titulo)
    nodo = {
        "@type": "NewsArticle",
        "@id": f"{url}#cambio",
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "url": url,
        "headline": f"{c.get_tipo_display()}: {titulo}"[:110],
        "description": c.frase,
        "datePublished": c.detectado_en.isoformat(),
        "dateModified": c.detectado_en.isoformat(),
        "inLanguage": "es-UY",
        "image": _abs(reverse("archivo:og-cambio", args=[c.pk])),
        "isBasedOn": _nota(c.fuente),
        "license": settings.LICENCIA_URL,
        "author": _org_ref(),
        "publisher": _org_ref(),
    }
    return {
        "@context": CONTEXT,
        "@graph": [nodo, organizacion(), migas(("Inicio", "/"), ("Notas editadas", reverse("archivo:cambios")), (titulo, None))],
    }


def dataset(exports, desde=None, hasta=None):
    """`/datos/`: cada CSV es una distribución del mismo conjunto."""
    nodo = {
        "@type": "Dataset",
        "@id": _abs(reverse("archivo:datos")) + "#datos",
        "name": "Archivo de memoria.uy",
        "description": "Historias, hechos con fuentes, proposiciones con resultados agregados, burbujas y notas editadas de los medios uruguayos. Nunca incluye votos individuales.",
        "url": _abs(reverse("archivo:datos")),
        "inLanguage": "es-UY",
        "isAccessibleForFree": True,
        "license": settings.LICENCIA_URL,
        "creator": _org_ref(),
        "publisher": _org_ref(),
        "spatialCoverage": "Uruguay",
        "distribution": [
            {
                "@type": "DataDownload",
                "name": f"{nombre}.csv",
                "encodingFormat": "text/csv",
                "contentUrl": _abs(reverse("archivo:export", args=[nombre])),
                "license": settings.LICENCIA_URL,
            }
            for nombre in exports
        ],
    }
    if desde and hasta:
        nodo["temporalCoverage"] = f"{desde:%Y-%m-%d}/{hasta:%Y-%m-%d}"
    return {
        "@context": CONTEXT,
        "@graph": [nodo, organizacion(), migas(("Inicio", "/"), ("Datos abiertos", None))],
    }


def pagina_con_migas(*items):
    """Para páginas sin otro dato estructurado (día, tema)."""
    return {"@context": CONTEXT, **migas(*items)}
