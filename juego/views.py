"""Vistas del juego diario y del voto desde el archivo."""

from urllib.parse import quote

from django.db import IntegrityError
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from archivo.models import Proposicion

from . import logica
from .models import BUCKETS, JornadaItem, VotoProposicion
from .burbujas import burbuja_de
from .votante import votante

OPINIONES = dict(VotoProposicion.OPINIONES)


def _guardar_voto(voter, proposicion, opinion, prediccion=None, jornada=None):
    """Crea el voto o devuelve el existente (no se cambia de opinión)."""
    filtro = logica.filtro_votante(voter)
    existente = VotoProposicion.objects.filter(filtro, proposicion=proposicion).first()
    if existente:
        return existente, False
    try:
        v = VotoProposicion.objects.create(
            proposicion=proposicion, opinion=opinion, prediccion=prediccion, jornada=jornada, **voter
        )
        return v, True
    except IntegrityError:
        return VotoProposicion.objects.get(filtro, proposicion=proposicion), False


class HoyView(View):
    """Juego del día: muestra la próxima proposición sin votar, o el resultado."""

    def get(self, request):
        jornada = logica.jornada_de_hoy()
        if not jornada:
            return render(request, "juego/sin_jornada.html")
        voter = votante(request)
        votos = logica.votos_de(voter, jornada)
        items = list(jornada.items_ordenados())
        pendiente = next((it for it in items if it.proposicion_id not in votos), None)
        if pendiente is None:
            return redirect("juego:resultado")
        return render(
            request,
            "juego/hoy.html",
            {
                "jornada": jornada,
                "item": pendiente,
                "n": items.index(pendiente) + 1,
                "total": len(items),
                "buckets": BUCKETS,
            },
        )


@method_decorator(ratelimit(key="ip", rate="60/m", method="POST", block=True), name="post")
class VotarItemView(View):
    """POST de opinión + predicción para un ítem de la jornada."""

    def post(self, request, item_id):
        item = get_object_or_404(JornadaItem.objects.select_related("jornada", "proposicion__historia"), pk=item_id)
        if not item.jornada.publicada:
            raise Http404
        opinion = request.POST.get("opinion")
        if opinion not in OPINIONES:
            return HttpResponseBadRequest("opinión inválida")
        try:
            prediccion = int(request.POST.get("prediccion"))
            assert 0 <= prediccion <= 4
        except (TypeError, ValueError, AssertionError):
            return HttpResponseBadRequest("predicción inválida")
        voter = votante(request)
        voto, _ = _guardar_voto(voter, item.proposicion, opinion, prediccion, item.jornada)
        r = logica.resultado(item.proposicion)
        otros = logica.resultado(item.proposicion, excluir=logica.filtro_votante(voter))
        ctx = {
            "item": item,
            "voto": voto,
            "r": r,
            "acierto": (voto.prediccion == otros.bucket) if otros.bucket is not None and voto.prediccion is not None else None,
            "bucket_label": dict(BUCKETS),
            "hay_mas": not logica.completa(voter, item.jornada),
        }
        plantilla = "juego/_resultado_item.html" if request.headers.get("HX-Request") else "juego/resultado_item_page.html"
        return render(request, plantilla, ctx)


class ResultadoView(View):
    def get(self, request):
        jornada = logica.jornada_de_hoy()
        if not jornada:
            return render(request, "juego/sin_jornada.html")
        voter = votante(request)
        if not logica.completa(voter, jornada):
            return redirect("juego:hoy")
        filas, aciertos = logica.puntaje(voter, jornada)
        texto = logica.tarjeta(voter, jornada) + "\nhttps://memoria.uy/hoy/"
        return render(
            request,
            "juego/resultado.html",
            {
                "jornada": jornada,
                "filas": filas,
                "aciertos": aciertos,
                "racha": logica.racha(voter),
                "mi_burbuja": burbuja_de(voter),
                "tarjeta": texto,
                "whatsapp": "https://wa.me/?text=" + quote(texto),
                "bucket_label": dict(BUCKETS),
            },
        )


@method_decorator(ratelimit(key="ip", rate="60/m", method="POST", block=True), name="post")
class VotarProposicionView(View):
    """Voto desde la página de una historia (sin predicción; no suma puntaje)."""

    def post(self, request, pk):
        prop = get_object_or_404(Proposicion, pk=pk, estado="publicada")
        opinion = request.POST.get("opinion")
        if opinion not in OPINIONES:
            return HttpResponseBadRequest("opinión inválida")
        voto, _ = _guardar_voto(votante(request), prop, opinion)
        if not request.headers.get("HX-Request"):
            return redirect("archivo:historia", slug=prop.historia.slug)
        return render(request, "juego/_voto_archivo.html", {"p": prop, "voto": voto, "r": logica.resultado(prop)})


class BurbujasView(View):
    def get(self, request):
        from . import burbujas as B

        run = B.ultimo_run()
        ctx = {"run": run}
        if run:
            miembros = list(run.miembros.select_related("burbuja").values_list("x", "y", "burbuja__numero", "session_key", "usuario_id"))
            xs = [m[0] for m in miembros] or [0]
            ys = [m[1] for m in miembros] or [0]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            sx = lambda x: 5 + 90 * (x - x0) / ((x1 - x0) or 1)  # noqa: E731
            sy = lambda y: 5 + 90 * (y - y0) / ((y1 - y0) or 1)  # noqa: E731
            voter = votante(request)
            yo = None
            puntos = []
            for x, y, num, sk, uid in miembros:
                es_yo = (voter.get("usuario") and uid == voter["usuario"].pk) or (sk and sk == voter.get("session_key"))
                punto = (round(sx(x), 2), round(sy(y), 2), num)
                if es_yo:
                    yo = (*punto, 0, round(punto[1] - 3.5, 2))
                puntos.append(punto)
            burbujas = list(run.burbujas.all())
            une, divide = B.consenso_y_division(run)
            ctx.update(
                {
                    "puntos": puntos,
                    "yo": yo,
                    "mi_burbuja": B.burbuja_de(voter, run),
                    "burbujas": [
                        (b, round(sx(b.cx), 2), round(sy(b.cy), 2), B.distintivas(run, b)) for b in burbujas
                    ],
                    "une": une,
                    "divide": divide,
                    "grises": dict(enumerate(["#000000", "#6b7280", "#a3a3a3", "#404040", "#d4d4d4"])),
                }
            )
        return render(request, "juego/burbujas.html", ctx)


from django.http import HttpResponse  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.views.decorators.cache import cache_page  # noqa: E402

from archivo.og import imagen  # noqa: E402


@cache_page(60 * 30)
def og_hoy(request):
    j = logica.jornada_de_hoy()
    fecha = (j.fecha if j else timezone.localdate()).strftime("%d/%m")
    primera = j.items_ordenados()[0].proposicion.texto if j and j.items.exists() else "5 frases de las noticias de hoy."
    return HttpResponse(
        imagen(f"«{primera}»", f"¿Qué piensa Uruguay? · {fecha}", "¿de acuerdo? ¿y el resto?", invertida=True),
        content_type="image/png",
    )


@cache_page(60 * 60 * 24)
def og_default(request):
    return HttpResponse(
        imagen("Lo que pasó en Uruguay, con fuentes. Y lo que pensamos.", "archivo · juego diario · burbujas", ""),
        content_type="image/png",
    )
