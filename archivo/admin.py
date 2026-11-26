from django.contrib import admin, messages
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from core.admin_utils import badge, link_admin, pct

from . import pipeline
from .models import (
    Cambio,
    Decision,
    FichaEntidad,
    Fuente,
    Hecho,
    HechoFuente,
    Historia,
    Medio,
    Proposicion,
    Snapshot,
    Tono,
    UsoProveedor,
)

TONO_ESTADO_FUENTE = {
    "descubierta": "mute",
    "descartada": "mute",
    "extraida": "info",
    "procesada": "ok",
    "error": "err",
    "despublicada": "warn",
}
TONO_ESTADO_PROPOSICION = {"candidata": "warn", "publicada": "ok", "descartada": "mute"}


def _sitio(nombre, *args):
    """Función para `view_on_site`: la página pública, o None si no hay."""

    def url(obj):
        try:
            return reverse(f"archivo:{nombre}", args=[getattr(obj, a) for a in args])
        except Exception:
            return None

    return staticmethod(url)


def _url_historia(h):
    return reverse("archivo:historia", args=[h.slug]) if h.slug and h.procesada_en else None


def _corto(texto, n=90):
    texto = texto or ""
    return texto if len(texto) <= n else texto[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Medios y fuentes
# ---------------------------------------------------------------------------


@admin.register(Medio)
class MedioAdmin(admin.ModelAdmin):
    list_display = (
        "nombre", "dominio", "tipo", "activo", "pago", "feeds", "n_fuentes",
        "ultimo_descubrimiento",
    )
    list_filter = ("activo", "tipo", "pago")
    list_editable = ("activo",)
    search_fields = ("nombre", "dominio", "slug")
    prepopulated_fields = {"slug": ("nombre",)}
    readonly_fields = ("ultimo_descubrimiento",)
    actions = ["activar", "desactivar", "buscar_notas"]
    view_on_site = _sitio("medio", "slug")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n_fuentes=Count("fuentes"))

    @admin.display(description="feeds")
    def feeds(self, obj):
        n = len(obj.rss_urls or []) + len(obj.sitemap_urls or [])
        return badge(n, "ok") if n else badge("sin feeds", "err")

    @admin.display(description="fuentes", ordering="_n_fuentes")
    def n_fuentes(self, obj):
        return format_html(
            '<a class="mu-num" href="{}?medio__id__exact={}">{}</a>',
            reverse("admin:archivo_fuente_changelist"), obj.pk, obj._n_fuentes,
        )

    @admin.action(description="Activar los medios elegidos")
    def activar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activo=True)} medios activados.")

    @admin.action(description="Desactivar los medios elegidos")
    def desactivar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activo=False)} medios desactivados.")

    @admin.action(description="Buscar notas nuevas ahora (lee RSS y sitemaps)")
    def buscar_notas(self, request, queryset):
        for medio in queryset[:5]:
            try:
                nuevas = pipeline.descubrir(medio)
                self.message_user(request, f"{medio}: {len(nuevas)} notas nuevas.")
            except Exception as e:
                self.message_user(request, f"{medio}: falló ({e}).", messages.ERROR)
        if queryset.count() > 5:
            self.message_user(request, "Solo se leen 5 medios por vez.", messages.WARNING)


class SnapshotInline(admin.TabularInline):
    model = Snapshot
    fields = ("capturado_en", "proveedor", "http_status", "titulo", "storage_key")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class TonoInline(admin.TabularInline):
    model = Tono
    fields = ("entidad", "valencia", "cita", "verificado")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("entidad")


@admin.register(Fuente)
class FuenteAdmin(admin.ModelAdmin):
    list_display = (
        "titulo_corto", "medio", "estado_badge", "interes_pct", "publicada",
        "historia_link", "intentos",
    )
    list_display_links = ("titulo_corto",)
    list_filter = ("estado", "medio", "seccion")
    search_fields = ("titulo", "url", "autor")
    date_hierarchy = "publicada_en"
    list_select_related = ("medio", "historia")
    raw_id_fields = ("historia", "ultimo_snapshot")
    show_full_result_count = False
    actions = ["volver_a_extraer", "recrawl_ahora", "recalcular_tonos"]
    inlines = [SnapshotInline, TonoInline]
    readonly_fields = (
        "url_hash", "descubierta_en", "url_enlace", "estado_badge", "interes",
        "motivo_descarte", "intentos", "recrawls_hechos", "tonos_en", "texto_largo",
    )
    fieldsets = (
        (None, {"fields": ("titulo", "medio", "url_enlace", "url", "autor", "seccion")}),
        ("Pipeline", {"fields": (
            "estado_badge", "estado", "motivo_descarte", "interes", "intentos",
            "historia", "ultimo_snapshot",
        )}),
        ("Tiempos", {"fields": (
            "publicada_en", "descubierta_en", "proximo_recrawl", "recrawls_hechos", "tonos_en",
        )}),
        ("Contenido", {"classes": ("collapse",), "fields": ("bajada", "texto_largo", "url_hash")}),
    )
    exclude = ("embedding", "texto")

    @admin.display(description="título", ordering="titulo")
    def titulo_corto(self, obj):
        return _corto(obj.titulo or obj.url)

    @admin.display(description="estado", ordering="estado")
    def estado_badge(self, obj):
        return badge(obj.get_estado_display(), TONO_ESTADO_FUENTE.get(obj.estado, "mute"))

    @admin.display(description="publicada", ordering="publicada_en")
    def publicada(self, obj):
        return timezone.localtime(obj.publicada_en).strftime("%d/%m %H:%M") if obj.publicada_en else "—"

    @admin.display(description="interés", ordering="interes")
    def interes_pct(self, obj):
        return pct(obj.interes)

    @admin.display(description="historia")
    def historia_link(self, obj):
        return link_admin(obj.historia, _corto(str(obj.historia), 50)) if obj.historia else "—"

    @admin.display(description="nota original")
    def url_enlace(self, obj):
        if not obj.pk:
            return "—"
        return format_html('<a href="{0}" target="_blank" rel="noopener">{0} ↗</a>', obj.url)

    @admin.display(description="texto extraído")
    def texto_largo(self, obj):
        return format_html('<div style="max-height:320px;overflow:auto;white-space:pre-wrap">{}</div>', obj.texto)

    @admin.action(description="Volver a extraer (estado → descubierta, sin intentos)")
    def volver_a_extraer(self, request, queryset):
        n = queryset.update(estado="descubierta", intentos=0, motivo_descarte="")
        self.message_user(request, f"{n} fuentes vuelven a la cola de extracción.")

    @admin.action(description="Re-capturar en el próximo ciclo (detectar ediciones)")
    def recrawl_ahora(self, request, queryset):
        n = queryset.update(proximo_recrawl=timezone.now())
        self.message_user(request, f"{n} fuentes programadas para recrawl.")

    @admin.action(description="Recalcular el tono hacia las personas")
    def recalcular_tonos(self, request, queryset):
        n = queryset.update(tonos_en=None)
        self.message_user(request, f"{n} fuentes vuelven a la cola de tonos.")


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ("fuente_corta", "capturado_en", "proveedor", "http_status", "storage_key")
    list_filter = ("proveedor", "http_status")
    search_fields = ("fuente__titulo", "fuente__url", "storage_key", "contenido_hash")
    date_hierarchy = "capturado_en"
    list_select_related = ("fuente",)
    raw_id_fields = ("fuente",)
    readonly_fields = ("fuente", "capturado_en", "storage_key", "contenido_hash", "titulo", "http_status", "proveedor")
    show_full_result_count = False

    @admin.display(description="fuente")
    def fuente_corta(self, obj):
        return _corto(str(obj.fuente), 80)

    def has_add_permission(self, request):
        return False


# ---------------------------------------------------------------------------
# Historias, hechos, proposiciones
# ---------------------------------------------------------------------------


class HechoFuenteInline(admin.TabularInline):
    model = HechoFuente
    raw_id_fields = ("fuente",)
    fields = ("fuente", "fiel", "cita")
    extra = 0


class HechoInline(admin.TabularInline):
    model = Hecho
    fields = ("orden", "texto", "disputado", "oculto")
    show_change_link = True
    extra = 0


class ProposicionInline(admin.TabularInline):
    model = Proposicion
    fields = ("texto", "tema", "estado", "calidad", "divisividad")
    show_change_link = True
    extra = 0


class FuenteInline(admin.TabularInline):
    model = Fuente
    fields = ("titulo", "medio", "estado", "publicada_en")
    readonly_fields = fields
    show_change_link = True
    extra = 0
    can_delete = False
    max_num = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("medio").order_by("publicada_en")


@admin.register(Historia)
class HistoriaAdmin(admin.ModelAdmin):
    list_display = (
        "titulo_corto", "categoria", "n_medios", "n_fuentes", "n_hechos", "estado_badge",
        "relevancia", "ultima_fuente_en", "procesada",
    )
    list_filter = ("estado", "categoria", ("procesada_en", admin.EmptyFieldListFilter))
    search_fields = ("titulo", "resumen", "slug")
    date_hierarchy = "ultima_fuente_en"
    readonly_fields = (
        "slug", "n_medios", "n_embeddings", "relevancia", "primera_fuente_en",
        "ultima_fuente_en", "procesada_en", "creada_en",
    )
    exclude = ("centroide",)
    inlines = [HechoInline, ProposicionInline, FuenteInline]
    actions = ["reprocesar", "cerrar", "reabrir"]
    show_full_result_count = False
    view_on_site = staticmethod(_url_historia)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _n_fuentes=Count("fuentes", distinct=True), _n_hechos=Count("hechos", distinct=True)
        )

    @admin.display(description="título", ordering="titulo")
    def titulo_corto(self, obj):
        return _corto(str(obj), 80)

    @admin.display(description="fuentes", ordering="_n_fuentes")
    def n_fuentes(self, obj):
        return obj._n_fuentes

    @admin.display(description="hechos", ordering="_n_hechos")
    def n_hechos(self, obj):
        return obj._n_hechos

    @admin.display(description="estado", ordering="estado")
    def estado_badge(self, obj):
        return badge(obj.get_estado_display(), "info" if obj.estado == "abierta" else "mute")

    @admin.display(description="procesada", boolean=True, ordering="procesada_en")
    def procesada(self, obj):
        return obj.procesada_en is not None

    @admin.action(description="Reprocesar (LLM: hechos, proposiciones, verificación)")
    def reprocesar(self, request, queryset):
        ok = 0
        for h in queryset[:10]:
            try:
                ok += bool(pipeline.procesar_historia(h))
            except Exception as e:
                self.message_user(request, f"{h}: falló ({e}).", messages.ERROR)
        self.message_user(request, f"{ok} historias reprocesadas (máximo 10 por vez).")

    @admin.action(description="Cerrar las historias elegidas")
    def cerrar(self, request, queryset):
        self.message_user(request, f"{queryset.update(estado='cerrada')} historias cerradas.")

    @admin.action(description="Reabrir las historias elegidas")
    def reabrir(self, request, queryset):
        self.message_user(request, f"{queryset.update(estado='abierta')} historias reabiertas.")


@admin.register(Hecho)
class HechoAdmin(admin.ModelAdmin):
    list_display = ("texto_corto", "historia_link", "n_fuentes", "disputado", "oculto")
    list_filter = ("oculto", "disputado", "historia__categoria")
    search_fields = ("texto", "historia__titulo")
    list_select_related = ("historia",)
    raw_id_fields = ("historia",)
    autocomplete_fields = ("entidades",)
    inlines = [HechoFuenteInline]
    actions = ["ocultar", "mostrar"]
    show_full_result_count = False

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n_fuentes=Count("fuentes"))

    @admin.display(description="hecho", ordering="texto")
    def texto_corto(self, obj):
        return _corto(obj.texto, 110)

    @admin.display(description="historia")
    def historia_link(self, obj):
        return link_admin(obj.historia, _corto(str(obj.historia), 50))

    @admin.display(description="fuentes", ordering="_n_fuentes")
    def n_fuentes(self, obj):
        return obj._n_fuentes

    @admin.action(description="Ocultar del sitio")
    def ocultar(self, request, queryset):
        self.message_user(request, f"{queryset.update(oculto=True)} hechos ocultos.")

    @admin.action(description="Volver a mostrar")
    def mostrar(self, request, queryset):
        self.message_user(request, f"{queryset.update(oculto=False)} hechos visibles.")


@admin.register(Proposicion)
class ProposicionAdmin(admin.ModelAdmin):
    list_display = (
        "texto_corto", "tema", "estado", "calidad_pct", "divisividad", "historia_link",
        "n_votos", "creada_en",
    )
    list_editable = ("estado",)
    list_filter = ("estado", "historia__categoria")
    search_fields = ("texto", "tema", "historia__titulo")
    date_hierarchy = "creada_en"
    list_select_related = ("historia",)
    raw_id_fields = ("historia",)
    autocomplete_fields = ("hechos", "entidades")
    readonly_fields = ("creada_en",)
    actions = ["publicar", "descartar", "volver_candidata"]
    show_full_result_count = False

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n_votos=Count("votos", distinct=True))

    @admin.display(description="proposición", ordering="texto")
    def texto_corto(self, obj):
        return _corto(obj.texto, 110)

    @admin.display(description="calidad", ordering="calidad")
    def calidad_pct(self, obj):
        return pct(obj.calidad, umbral=0.6)

    @admin.display(description="historia")
    def historia_link(self, obj):
        return link_admin(obj.historia, _corto(str(obj.historia), 45))

    @admin.display(description="votos", ordering="_n_votos")
    def n_votos(self, obj):
        return obj._n_votos

    @admin.action(description="Publicar (puede entrar a una jornada)")
    def publicar(self, request, queryset):
        self.message_user(request, f"{queryset.update(estado='publicada')} proposiciones publicadas.")

    @admin.action(description="Descartar")
    def descartar(self, request, queryset):
        self.message_user(request, f"{queryset.update(estado='descartada')} proposiciones descartadas.")

    @admin.action(description="Volver a candidata")
    def volver_candidata(self, request, queryset):
        self.message_user(request, f"{queryset.update(estado='candidata')} proposiciones candidatas.")


# ---------------------------------------------------------------------------
# Tono y notas editadas
# ---------------------------------------------------------------------------


@admin.register(Tono)
class TonoAdmin(admin.ModelAdmin):
    list_display = ("entidad", "valencia_badge", "medio", "fuente_corta", "verificado_pct", "creado_en")
    list_filter = ("valencia", "fuente__medio", "entidad__tipo")
    search_fields = ("entidad__nombre", "cita", "razon", "fuente__titulo")
    date_hierarchy = "creado_en"
    list_select_related = ("entidad", "fuente__medio")
    raw_id_fields = ("fuente", "entidad")
    readonly_fields = ("modelo", "creado_en")
    show_full_result_count = False

    @admin.display(description="valencia", ordering="valencia")
    def valencia_badge(self, obj):
        tono = "ok" if obj.valencia > 0 else "err" if obj.valencia < 0 else "mute"
        return badge(f"{obj.valencia:+d} {obj.get_valencia_display()}", tono)

    @admin.display(description="medio", ordering="fuente__medio__nombre")
    def medio(self, obj):
        return obj.fuente.medio.nombre

    @admin.display(description="nota")
    def fuente_corta(self, obj):
        return link_admin(obj.fuente, _corto(str(obj.fuente), 60))

    @admin.display(description="verificado", ordering="verificado")
    def verificado_pct(self, obj):
        return pct(obj.verificado)


@admin.register(Cambio)
class CambioAdmin(admin.ModelAdmin):
    list_display = ("fuente_corta", "medio", "tipo_badge", "sentido", "resumen", "detectado_en")
    list_filter = ("tipo", "fuente__medio")
    search_fields = ("fuente__titulo", "titulo_antes", "titulo_despues", "resumen")
    date_hierarchy = "detectado_en"
    list_select_related = ("fuente__medio",)
    raw_id_fields = ("fuente", "antes", "despues")
    readonly_fields = ("diff_html", "frase_html")
    fields = (
        "fuente", "tipo", "frase_html", "titulo_antes", "titulo_despues", "cambia_sentido",
        "resumen", "detectado_en", "antes", "despues", "diff_html",
    )
    show_full_result_count = False
    view_on_site = _sitio("cambio", "pk")

    @admin.display(description="nota")
    def fuente_corta(self, obj):
        return _corto(str(obj.fuente), 70)

    @admin.display(description="medio", ordering="fuente__medio__nombre")
    def medio(self, obj):
        return obj.fuente.medio.nombre

    @admin.display(description="tipo", ordering="tipo")
    def tipo_badge(self, obj):
        return badge(obj.get_tipo_display(), "err" if obj.tipo == "despublicada" else "info")

    @admin.display(description="¿cambia el sentido?", ordering="cambia_sentido")
    def sentido(self, obj):
        v = obj.cambia_sentido
        return badge("—") if v is None else badge(f"{v:.0%}", "err" if v >= 0.5 else "mute")

    @admin.display(description="qué pasó")
    def frase_html(self, obj):
        return obj.frase if obj.pk else "—"

    @admin.display(description="diff")
    def diff_html(self, obj):
        def pieza(op, texto):
            if op == "+":
                return format_html("<ins>{}</ins>", texto)
            if op == "-":
                return format_html("<del>{}</del>", texto)
            return format_html("<span>{}</span>", _corto(texto, 160))

        ops = (obj.diff or [])[:400]
        if not ops:
            return "—"
        return format_html(
            '<div class="mu-diff" style="max-height:360px;overflow:auto">{}</div>',
            format_html_join(" ", "{}", ((pieza(op, t),) for op, t in ops)),
        )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    list_display = ("pregunta", "valor", "modelo", "costo_usd", "creada_en")
    list_filter = ("pregunta", "modelo")
    search_fields = ("pregunta", "entrada_hash")
    date_hierarchy = "creada_en"
    readonly_fields = ("pregunta", "entrada_hash", "valor", "modelo", "costo_usd", "creada_en")
    show_full_result_count = False

    def has_add_permission(self, request):
        return False


@admin.register(UsoProveedor)
class UsoProveedorAdmin(admin.ModelAdmin):
    list_display = ("fecha", "proveedor", "operacion", "cantidad", "costo_usd")
    list_filter = ("proveedor", "operacion")
    date_hierarchy = "fecha"
    ordering = ("-fecha", "proveedor", "operacion")


@admin.register(FichaEntidad)
class FichaEntidadAdmin(admin.ModelAdmin):
    """Ficha de Wikidata. Para corregir el QID a mano, marcar «fijada»: la tarea no la vuelve a tocar."""

    list_display = ("entidad_link", "qid_link", "confianza_pct", "fijada", "cargo", "organizacion", "consultada_en")
    list_filter = ("fijada", "entidad__tipo")
    search_fields = ("entidad__nombre", "qid", "etiqueta", "cargo", "organizacion")
    list_select_related = ("entidad",)
    raw_id_fields = ("entidad",)
    readonly_fields = ("consultada_en",)
    show_full_result_count = False

    @admin.display(description="entidad", ordering="entidad__nombre")
    def entidad_link(self, obj):
        return link_admin(obj.entidad)

    @admin.display(description="QID", ordering="qid")
    def qid_link(self, obj):
        if not obj.qid:
            return badge("sin ficha")
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.wikidata_url, obj.qid)

    @admin.display(description="confianza", ordering="confianza")
    def confianza_pct(self, obj):
        return pct(obj.confianza, umbral=0.8)
