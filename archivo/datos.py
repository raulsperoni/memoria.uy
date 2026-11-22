"""Datos abiertos: exports CSV agregados. Nunca votos individuales."""

import csv

from django.db.models import Count, Q
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page

from .models import Cambio, Hecho, Historia, Proposicion

BASE = "https://memoria.uy"


class _Eco:
    def write(self, value):
        return value


def _csv(nombre, cabecera, filas):
    w = csv.writer(_Eco())

    def gen():
        yield "﻿"  # BOM para Excel
        yield w.writerow(cabecera)
        for f in filas:
            yield w.writerow(f)

    resp = StreamingHttpResponse(gen(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="memoria-uy-{nombre}.csv"'
    return resp


def _historias():
    for h in Historia.objects.filter(procesada_en__isnull=False).exclude(slug__isnull=True).order_by("primera_fuente_en").iterator():
        yield [h.pk, h.primera_fuente_en.date().isoformat(), h.categoria, h.n_medios, h.titulo, h.resumen, f"{BASE}/h/{h.slug}/"]


def _hechos():
    qs = Hecho.objects.filter(oculto=False, historia__procesada_en__isnull=False).prefetch_related("hechofuente_set__fuente__medio", "entidades")
    for x in qs.order_by("historia_id", "orden").iterator(chunk_size=500):
        medios = sorted({hf.fuente.medio.nombre for hf in x.hechofuente_set.all()})
        urls = [hf.fuente.url for hf in x.hechofuente_set.all()]
        yield [x.historia_id, x.pk, x.texto, x.disputado, "; ".join(medios), " ".join(urls), "; ".join(e.nombre for e in x.entidades.all())]


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
    "hechos": (["historia_id", "hecho_id", "texto", "disputado", "medios", "urls_fuentes", "entidades"], _hechos),
    "proposiciones": (["id", "historia_id", "fecha", "tema", "texto", "acuerdo", "desacuerdo", "no_se", "divisividad_estimada"], _proposiciones),
    "burbujas": (["run", "fecha", "proposicion_id", "burbuja", "tamano_burbuja", "acuerdo", "desacuerdo", "no_se"], _burbujas),
    "cambios": (["id", "detectado", "medio", "tipo", "prob_cambia_sentido", "titulo_antes", "titulo_despues", "url_nota", "url"], _cambios),
}


def datos(request):
    return render(request, "archivo/datos.html", {"exports": EXPORTS})


@cache_page(60 * 60)
def export(request, nombre):
    if nombre not in EXPORTS:
        raise Http404
    cab, gen = EXPORTS[nombre]
    return _csv(nombre, cab, gen() or [])
