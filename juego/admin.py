from django.contrib import admin
from django.db.models import Count
from django.urls import reverse

from archivo.admin import _corto
from core.admin_utils import badge, link_admin

from .models import (
    Burbuja,
    BurbujaMiembro,
    BurbujaPatron,
    BurbujaRun,
    Jornada,
    JornadaItem,
    VotoProposicion,
)


class JornadaItemInline(admin.TabularInline):
    model = JornadaItem
    raw_id_fields = ("proposicion",)
    fields = ("orden", "proposicion", "recurrente")
    extra = 0


@admin.register(Jornada)
class JornadaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "estado", "n_items", "n_votos", "curada_por", "creada_en")
    list_filter = ("publicada",)
    date_hierarchy = "fecha"
    list_select_related = ("curada_por",)
    raw_id_fields = ("curada_por",)
    readonly_fields = ("creada_en",)
    inlines = [JornadaItemInline]
    actions = ["publicar", "despublicar"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _n_items=Count("items", distinct=True), _n_votos=Count("votos", distinct=True)
        )

    def view_on_site(self, obj):
        return reverse("juego:hoy") if obj.publicada else None

    @admin.display(description="estado", ordering="publicada")
    def estado(self, obj):
        return badge("publicada", "ok") if obj.publicada else badge("sin publicar", "warn")

    @admin.display(description="proposiciones", ordering="_n_items")
    def n_items(self, obj):
        return obj._n_items

    @admin.display(description="votos", ordering="_n_votos")
    def n_votos(self, obj):
        return obj._n_votos

    @admin.action(description="Publicar")
    def publicar(self, request, queryset):
        self.message_user(request, f"{queryset.update(publicada=True)} jornadas publicadas.")

    @admin.action(description="Sacar de publicación")
    def despublicar(self, request, queryset):
        self.message_user(request, f"{queryset.update(publicada=False)} jornadas sin publicar.")


@admin.register(VotoProposicion)
class VotoProposicionAdmin(admin.ModelAdmin):
    list_display = ("proposicion_corta", "opinion", "prediccion", "votante", "jornada", "creado_en")
    list_filter = ("opinion", "prediccion")
    search_fields = ("proposicion__texto", "usuario__username", "usuario__email")
    date_hierarchy = "creado_en"
    list_select_related = ("proposicion", "usuario", "jornada")
    raw_id_fields = ("proposicion", "usuario", "jornada")
    show_full_result_count = False

    @admin.display(description="proposición")
    def proposicion_corta(self, obj):
        return _corto(obj.proposicion.texto, 90)

    @admin.display(description="votante")
    def votante(self, obj):
        if obj.usuario_id:
            return str(obj.usuario)
        return badge("anónimo")


class BurbujaInline(admin.TabularInline):
    model = Burbuja
    fields = ("numero", "nombre", "descripcion", "tamano")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BurbujaRun)
class BurbujaRunAdmin(admin.ModelAdmin):
    list_display = ("creada_en", "estado_badge", "k", "n_votantes", "n_proposiciones", "silhouette")
    list_filter = ("estado",)
    date_hierarchy = "creada_en"
    readonly_fields = (
        "creada_en", "n_votantes", "n_proposiciones", "k", "silhouette", "varianza",
        "parametros", "estado", "mensaje",
    )
    inlines = [BurbujaInline]

    def has_add_permission(self, request):
        return False

    @admin.display(description="estado", ordering="estado")
    def estado_badge(self, obj):
        return badge(obj.estado, {"ok": "ok", "insuficiente": "warn"}.get(obj.estado, "err"))


@admin.register(Burbuja)
class BurbujaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "run_link", "numero", "tamano", "descripcion")
    search_fields = ("nombre", "descripcion")
    list_select_related = ("run",)
    raw_id_fields = ("run",)
    show_full_result_count = False

    @admin.display(description="corrida")
    def run_link(self, obj):
        return link_admin(obj.run)


@admin.register(BurbujaPatron)
class BurbujaPatronAdmin(admin.ModelAdmin):
    list_display = ("burbuja", "proposicion_corta", "acuerdo", "desacuerdo", "nose")
    list_select_related = ("burbuja", "proposicion")
    raw_id_fields = ("run", "burbuja", "proposicion")
    show_full_result_count = False

    @admin.display(description="proposición")
    def proposicion_corta(self, obj):
        return _corto(obj.proposicion.texto, 90)


@admin.register(BurbujaMiembro)
class BurbujaMiembroAdmin(admin.ModelAdmin):
    list_display = ("burbuja", "usuario", "session_key", "x", "y")
    list_select_related = ("burbuja", "usuario")
    raw_id_fields = ("run", "burbuja", "usuario")
    show_full_result_count = False
