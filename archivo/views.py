"""Páginas públicas del archivo."""

import json

from datetime import date, datetime, time, timedelta

from django.contrib.postgres.search import SearchQuery, SearchVector  # noqa: F401
from django.db import connection
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.text import slugify
from django.views.generic import DetailView, ListView, TemplateView

from core.models import Entidad

from .models import Cambio, HechoFuente, Hecho, Historia, Medio, Proposicion
from .pipeline import historias_top


def _historias_publicas():
    return Historia.objects.filter(procesada_en__isnull=False).exclude(slug__isnull=True)


class HoyView(TemplateView):
    """Lo que pasó hoy: historias top de las últimas 48 h."""

    template_name = "archivo/hoy.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["historias"] = historias_top(n=20, horas=48)
        from juego.logica import completa, jornada_de_hoy
        from juego.votante import votante

        jornada = jornada_de_hoy()
        ctx["jornada"] = jornada
        ctx["jornada_completa"] = bool(jornada and completa(votante(self.request), jornada))
        ctx["cambios"] = (
            Cambio.objects.select_related("fuente__medio")
            .filter(Q(cambia_sentido__gte=0.5) | Q(tipo="despublicada"))
            .order_by("-detectado_en")[:5]
        )
        return ctx


class HistoriaView(DetailView):
    template_name = "archivo/historia.html"
    context_object_name = "historia"

    def get_queryset(self):
        hechos = Hecho.objects.filter(oculto=False).prefetch_related(
            Prefetch(
                "hechofuente_set",
                queryset=HechoFuente.objects.select_related("fuente__medio", "fuente__ultimo_snapshot"),
            ),
            "entidades",
        )
        return _historias_publicas().prefetch_related(
            Prefetch("hechos", queryset=hechos),
            Prefetch("proposiciones", queryset=Proposicion.objects.filter(estado="publicada").order_by("pk")),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        h = self.object
        ctx["fuentes"] = h.fuentes.select_related("medio").order_by("publicada_en")
        # Un chip por medio en cada hecho (si dos notas del mismo medio lo respaldan)
        for hecho in h.hechos.all():
            vistos, unicos = set(), []
            for hf in hecho.hechofuente_set.all():
                if hf.fuente.medio_id not in vistos:
                    vistos.add(hf.fuente.medio_id)
                    unicos.append(hf)
            hecho.respaldos = unicos
        ctx["cambios"] = Cambio.objects.filter(fuente__historia=h).select_related("fuente__medio")
        ctx["entidades"] = (
            Entidad.objects.filter(hechos__historia=h).distinct().order_by("nombre")
        )
        from juego.logica import filtro_votante, resultado
        from juego.models import VotoProposicion
        from juego.votante import votante

        props = list(h.proposiciones.all())
        mis_votos = {
            v.proposicion_id: v
            for v in VotoProposicion.objects.filter(filtro_votante(votante(self.request)), proposicion__in=props)
        }
        from juego.burbujas import patrones_por_proposicion, ultimo_run

        run = ultimo_run()
        pats = patrones_por_proposicion(run) if run else {}
        ctx["props_votos"] = [(p, mis_votos.get(p.pk), resultado(p), pats.get(p.pk, {})) for p in props]
        ctx["jsonld"] = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "CreativeWork",
                "name": h.titulo,
                "abstract": h.resumen,
                "dateCreated": h.primera_fuente_en.isoformat(),
                "inLanguage": "es-UY",
                "citation": [
                    {
                        "@type": "NewsArticle",
                        "url": f.url,
                        "headline": f.titulo,
                        "publisher": {"@type": "Organization", "name": f.medio.nombre},
                    }
                    for f in ctx["fuentes"]
                ],
            },
            ensure_ascii=False,
        ).replace("</", "<\\/")
        return ctx


class EntidadView(DetailView):
    template_name = "archivo/entidad.html"
    context_object_name = "entidad"

    def get_object(self):
        ent = Entidad.objects.filter(pk=self.kwargs["pk"]).first()
        if not ent:
            raise Http404
        return ent

    def get(self, request, *args, **kwargs):
        # Una sola URL por entidad: /e/<id>/ y slugs viejos o inventados van a la canónica.
        ent = self.get_object()
        slug = slugify(ent.nombre)
        if slug and kwargs.get("slug") != slug:
            return redirect("archivo:entidad-slug", pk=ent.pk, slug=slug, permanent=True)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ent = self.object
        historias = (
            _historias_publicas()
            .filter(hechos__entidades=ent)
            .distinct()
            .order_by("-primera_fuente_en")[:100]
        )
        ctx["historias"] = historias
        if ent.tipo == "persona":
            from .tonos import resumen_por_medio

            ctx["tonos_medios"] = resumen_por_medio(ent, _historias_publicas())
        ctx["proposiciones"] = ent.proposiciones.filter(estado="publicada").select_related("historia")[:30]
        from juego.burbujas import patrones_por_proposicion, ultimo_run

        run = ultimo_run()
        if run:
            pats = patrones_por_proposicion(run)
            ctx["props_burbujas"] = [(p, pats[p.pk]) for p in ctx["proposiciones"] if p.pk in pats]
        return ctx


class CambiosView(ListView):
    template_name = "archivo/cambios.html"
    context_object_name = "cambios"
    paginate_by = 30

    def get_queryset(self):
        qs = Cambio.objects.select_related("fuente__medio", "fuente__historia")
        if self.request.GET.get("sentido"):
            qs = qs.filter(Q(cambia_sentido__gte=0.5) | Q(tipo="despublicada"))
        if medio := self.request.GET.get("medio"):
            qs = qs.filter(fuente__medio__slug=medio)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["medios"] = Medio.objects.filter(tipo="medio")
        return ctx


class CambioView(DetailView):
    template_name = "archivo/cambio.html"
    context_object_name = "cambio"
    queryset = Cambio.objects.select_related("fuente__medio", "fuente__historia", "antes", "despues")


class MedioView(DetailView):
    template_name = "archivo/medio.html"
    context_object_name = "medio"
    queryset = Medio.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        m = self.object
        ctx["fuentes"] = (
            m.fuentes.filter(historia__procesada_en__isnull=False)
            .select_related("historia")
            .order_by("-publicada_en")[:50]
        )
        ctx["cambios"] = Cambio.objects.filter(fuente__medio=m)[:20]
        ctx["n_fuentes"] = m.fuentes.filter(estado="procesada").count()
        ctx["n_cambios"] = Cambio.objects.filter(fuente__medio=m).count()
        return ctx


# Antes de esta fecha no hay archivo; evita fechas absurdas (y el OverflowError de date.min).
PRIMER_DIA = date(2024, 1, 1)


class DiaView(TemplateView):
    template_name = "archivo/dia.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            d = date(int(kwargs["y"]), int(kwargs["m"]), int(kwargs["d"]))
        except (ValueError, OverflowError):
            raise Http404
        if d < PRIMER_DIA or d > timezone.localdate():
            raise Http404
        tz = timezone.get_current_timezone()
        desde = datetime.combine(d, time.min, tzinfo=tz)
        hasta = desde + timedelta(days=1)
        ctx["dia"] = d
        ctx["anterior"] = d - timedelta(days=1) if d > PRIMER_DIA else None
        ctx["siguiente"] = d + timedelta(days=1) if d < timezone.localdate() else None
        ctx["historias"] = (
            _historias_publicas()
            .filter(primera_fuente_en__gte=desde, primera_fuente_en__lt=hasta)
            .order_by("-n_medios", "-primera_fuente_en")
        )
        return ctx


class BuscarView(ListView):
    template_name = "archivo/buscar.html"
    context_object_name = "historias"
    paginate_by = 30

    def get_queryset(self):
        q = (self.request.GET.get("q") or "").strip()
        if not q:
            return Historia.objects.none()
        qs = _historias_publicas()
        if connection.vendor == "postgresql":
            vector = SearchVector("titulo", weight="A", config="spanish") + SearchVector(
                "resumen", weight="B", config="spanish"
            )
            query = SearchQuery(q, config="spanish", search_type="websearch")
            return (
                qs.annotate(search=vector)
                .filter(Q(search=query) | Q(hechos__texto__icontains=q))
                .distinct()
                .order_by("-primera_fuente_en")
            )
        return (
            qs.filter(Q(titulo__icontains=q) | Q(resumen__icontains=q) | Q(hechos__texto__icontains=q))
            .distinct()
            .order_by("-primera_fuente_en")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()
        ctx["q"] = q
        ctx["entidades"] = (
            Entidad.objects.filter(nombre__icontains=q)
            .annotate(n=Count("hechos"))
            .filter(n__gt=0)
            .order_by("-n")[:10]
            if q
            else []
        )
        return ctx


# ---------------------------------------------------------------------------
# Imágenes OG
# ---------------------------------------------------------------------------

from django.http import HttpResponse  # noqa: E402
from django.views.decorators.cache import cache_page  # noqa: E402

from .og import imagen, imagen_entidad  # noqa: E402


@cache_page(60 * 60 * 6)
def og_historia(request, slug):
    h = _historias_publicas().filter(slug=slug).first()
    if not h:
        raise Http404
    arriba = f"{h.primera_fuente_en:%d/%m/%Y}" + (f" · #{h.categoria}" if h.categoria else "")
    abajo = f"{h.n_medios} medio{'s' if h.n_medios != 1 else ''} · hechos con fuentes"
    return HttpResponse(imagen(h.titulo, arriba, abajo), content_type="image/png")


@cache_page(60 * 60 * 6)
def og_entidad(request, pk):
    ent = Entidad.objects.filter(pk=pk).first()
    if not ent:
        raise Http404
    filas = []
    if ent.tipo == "persona":
        from .tonos import resumen_por_medio

        filas = resumen_por_medio(ent, _historias_publicas())
    n = _historias_publicas().filter(hechos__entidades=ent).distinct().count()
    abajo = f"{n} historia{'s' if n != 1 else ''}"
    return HttpResponse(imagen_entidad(ent.nombre, filas, abajo), content_type="image/png")


@cache_page(60 * 60 * 6)
def og_cambio(request, pk):
    c = Cambio.objects.select_related("fuente__medio").filter(pk=pk).first()
    if not c:
        raise Http404
    titulo = c.titulo_despues if c.tipo == "titulo" and c.titulo_despues else (c.titulo_antes or c.fuente.titulo)
    return HttpResponse(
        imagen(titulo, f"{c.fuente.medio.nombre} · {c.get_tipo_display().lower()}", "notas editadas"),
        content_type="image/png",
    )
