"""Datos abiertos: exports CSV agregados. Nunca votos individuales."""

import csv

from django.db.models import Count, Q
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page

from .models import Cambio, Hecho, HechoFuente, Historia, Proposicion

BASE = "https://memoria.uy"


class _Eco:
    def write(self, value):
        return value


LICENCIA = "CC BY 4.0; títulos y citas de los medios excluidos"


def _csv(nombre, cabecera, filas):
    w = csv.writer(_Eco())

    def gen():
        yield "\ufeff"  # BOM para Excel
        yield w.writerow([*cabecera, "licencia"])
        for f in filas:
            yield w.writerow([*f, LICENCIA])

    resp = StreamingHttpResponse(gen(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="memoria-uy-{nombre}.csv"'
    return resp


def _historias():
    for h in Historia.objects.filter(procesada_en__isnull=False).exclude(slug__isnull=True).order_by("primera_fuente_en").iterator():
        yield [h.pk, h.primera_fuente_en.date().isoformat(), h.categoria, h.n_medios, h.titulo, h.resumen, f"{BASE}/h/{h.slug}/"]


def _hechos():
    qs = Hecho.objects.filter(oculto=False, historia__procesada_en__isnull=False).select_related("historia").prefetch_related("hechofuente_set__fuente__medio", "entidades")
    for x in qs.order_by("historia_id", "orden").iterator(chunk_size=500):
        medios = sorted({hf.fuente.medio.nombre for hf in x.hechofuente_set.all()})
        urls = [hf.fuente.url for hf in x.hechofuente_set.all()]
        yield [x.historia_id, x.pk, f"{BASE}/h/{x.historia.slug}/#hecho-{x.pk}", x.texto, x.disputado, "; ".join(medios), " ".join(urls), "; ".join(e.nombre for e in x.entidades.all())]


def _fuentes_de_hechos():
    """Una fila por hecho y nota que lo respalda: la procedencia completa."""
    qs = HechoFuente.objects.filter(hecho__oculto=False, hecho__historia__procesada_en__isnull=False).select_related(
        "hecho__historia", "fuente__medio", "fuente__ultimo_snapshot"
    )
    for hf in qs.order_by("hecho__historia_id", "hecho__orden", "pk").iterator(chunk_size=500):
        snap = hf.fuente.ultimo_snapshot
        yield [
            hf.hecho.historia_id, hf.hecho_id, f"{BASE}/h/{hf.hecho.historia.slug}/#hecho-{hf.hecho_id}",
            hf.fuente.medio.nombre, hf.fuente.url, hf.fuente.titulo, hf.cita,
            snap.capturado_en.isoformat() if snap else "", snap.contenido_hash if snap else "",
        ]


def _proposiciones():
    qs = Proposicion.objects.filter(estado="publicada").annotate(
        acuerdo=Count("votos", filter=Q(votos__opinion="acuerdo")),
        desacuerdo=Count("votos", filter=Q(votos__opinion="desacuerdo")),
        nose=Count("votos", filter=Q(votos__opinion="nose")),
    )
    for p in qs.order_by("pk").iterator():
        yield [p.pk, p.historia_id, p.creada_en.date().isoformat(), p.tema, p.texto, p.acuerdo, p.desacuerdo, p.nose, p.divisividad]


def _burbujas():
    from juego.burbujas import ultimo_run

    run = ultimo_run()
    if not run:
        return
    for pat in run.patrones.select_related("burbuja").order_by("proposicion_id", "burbuja__numero").iterator():
        yield [run.pk, run.creada_en.date().isoformat(), pat.proposicion_id, pat.burbuja.letra, pat.burbuja.tamano, pat.acuerdo, pat.desacuerdo, pat.nose]


def _cambios():
    for c in Cambio.objects.select_related("fuente__medio").order_by("detectado_en").iterator():
        yield [c.pk, c.detectado_en.isoformat(), c.fuente.medio.nombre, c.tipo, c.cambia_sentido, c.titulo_antes, c.titulo_despues, c.fuente.url, f"{BASE}/cambios/{c.pk}/"]


EXPORTS = {
    "historias": (["id", "fecha", "categoria", "n_medios", "titulo", "resumen", "url"], _historias),
    "hechos": (["historia_id", "hecho_id", "url_hecho", "texto", "disputado", "medios", "urls_fuentes", "entidades"], _hechos),
    "fuentes": (["historia_id", "hecho_id", "url_hecho", "medio", "url_nota", "titulo_nota", "cita", "capturado_en", "sha256"], _fuentes_de_hechos),
    "proposiciones": (["id", "historia_id", "fecha", "tema", "texto", "acuerdo", "desacuerdo", "no_se", "divisividad_estimada"], _proposiciones),
    "burbujas": (["run", "fecha", "proposicion_id", "burbuja", "tamano_burbuja", "acuerdo", "desacuerdo", "no_se"], _burbujas),
    "cambios": (["id", "detectado", "medio", "tipo", "prob_cambia_sentido", "titulo_antes", "titulo_despues", "url_nota", "url"], _cambios),
}


def datos(request):
    from django.db.models import Max, Min
    from django.utils import timezone

    from . import estructurados

    rango = Historia.objects.filter(procesada_en__isnull=False).aggregate(d=Min("primera_fuente_en"), h=Max("primera_fuente_en"))
    ld = estructurados.dataset(EXPORTS, rango["d"], rango["h"] or timezone.now())
    return render(request, "archivo/datos.html", {"exports": EXPORTS, "jsonld": estructurados.jsonld(ld)})


@cache_page(60 * 60)
def export(request, nombre):
    if nombre not in EXPORTS:
        raise Http404
    cab, gen = EXPORTS[nombre]
    return _csv(nombre, cab, gen() or [])


@cache_page(60 * 60)
def export_jsonl(request, nombre):
    """`hechos.jsonl`: un hecho por línea, con sus fuentes (JSON, UTF-8)."""
    import json

    from django.http import StreamingHttpResponse

    if nombre != "hechos":
        raise Http404
    qs = Hecho.objects.filter(oculto=False, historia__procesada_en__isnull=False).select_related("historia").prefetch_related(
        "hechofuente_set__fuente__medio", "hechofuente_set__fuente__ultimo_snapshot", "entidades"
    )

    def gen():
        for x in qs.order_by("historia_id", "orden").iterator(chunk_size=200):
            snap = lambda f: f.ultimo_snapshot  # noqa: E731
            yield json.dumps(
                {
                    "historia": f"{BASE}/h/{x.historia.slug}/",
                    "hecho": f"{BASE}/h/{x.historia.slug}/#hecho-{x.pk}",
                    "texto": x.texto,
                    "fuentes_difieren": x.disputado,
                    "entidades": [e.nombre for e in x.entidades.all()],
                    "fuentes": [
                        {
                            "medio": hf.fuente.medio.nombre,
                            "url": hf.fuente.url,
                            "titulo": hf.fuente.titulo,
                            "cita": hf.cita or None,
                            "capturado_en": snap(hf.fuente).capturado_en.isoformat() if snap(hf.fuente) else None,
                            "sha256": snap(hf.fuente).contenido_hash if snap(hf.fuente) else None,
                        }
                        for hf in x.hechofuente_set.all()
                    ],
                    "licencia": LICENCIA,
                },
                ensure_ascii=False,
            ) + "\n"

    return StreamingHttpResponse(gen(), content_type="application/x-ndjson; charset=utf-8")
