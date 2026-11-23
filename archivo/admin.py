from django.contrib import admin

from .models import (
    Cambio,
    Decision,
    Fuente,
    Hecho,
    HechoFuente,
    Historia,
    Medio,
    Proposicion,
    Snapshot,
    UsoProveedor,
)


@admin.register(Medio)
class MedioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "dominio", "tipo", "activo", "ultimo_descubrimiento")
    list_filter = ("tipo", "activo")
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(Fuente)
class FuenteAdmin(admin.ModelAdmin):
    list_display = ("titulo", "medio", "estado", "interes", "publicada_en", "historia")
    list_filter = ("estado", "medio")
    search_fields = ("titulo", "url")
    raw_id_fields = ("historia", "ultimo_snapshot")
    readonly_fields = ("url_hash", "descubierta_en")
    exclude = ("embedding",)


class HechoFuenteInline(admin.TabularInline):
    model = HechoFuente
    raw_id_fields = ("fuente",)
    extra = 0


@admin.register(Hecho)
class HechoAdmin(admin.ModelAdmin):
    list_display = ("texto", "historia", "disputado", "oculto")
    list_filter = ("oculto", "disputado")
    inlines = [HechoFuenteInline]
    raw_id_fields = ("historia",)
    filter_horizontal = ("entidades",)


class HechoInline(admin.TabularInline):
    model = Hecho
    fields = ("orden", "texto", "disputado", "oculto")
    extra = 0


class ProposicionInline(admin.TabularInline):
    model = Proposicion
    fields = ("texto", "tema", "estado", "calidad", "divisividad")
    extra = 0


@admin.register(Historia)
class HistoriaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "n_medios", "estado", "relevancia", "ultima_fuente_en")
    list_filter = ("estado", "categoria")
    search_fields = ("titulo",)
    exclude = ("centroide",)
    inlines = [HechoInline, ProposicionInline]


@admin.register(Proposicion)
class ProposicionAdmin(admin.ModelAdmin):
    list_display = ("texto", "tema", "estado", "calidad", "divisividad", "creada_en")
    list_filter = ("estado",)
    list_editable = ("estado",)
    search_fields = ("texto", "tema")
    raw_id_fields = ("historia",)


@admin.register(Cambio)
class CambioAdmin(admin.ModelAdmin):
    list_display = ("fuente", "tipo", "cambia_sentido", "detectado_en")
    list_filter = ("tipo",)
    raw_id_fields = ("fuente", "antes", "despues")


admin.site.register(Snapshot)


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    list_display = ("pregunta", "valor", "modelo", "creada_en")
    list_filter = ("pregunta", "modelo")


@admin.register(UsoProveedor)
class UsoProveedorAdmin(admin.ModelAdmin):
    list_display = ("fecha", "proveedor", "operacion", "cantidad", "costo_usd")
    list_filter = ("proveedor", "operacion")
