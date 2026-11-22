from django.contrib import admin

from .models import Jornada, JornadaItem, VotoProposicion


class JornadaItemInline(admin.TabularInline):
    model = JornadaItem
    raw_id_fields = ("proposicion",)
    extra = 0


@admin.register(Jornada)
class JornadaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "publicada", "n_items", "n_votos")
    list_filter = ("publicada",)
    inlines = [JornadaItemInline]

    def n_items(self, obj):
        return obj.items.count()

    def n_votos(self, obj):
        return obj.votos.count()


@admin.register(VotoProposicion)
class VotoProposicionAdmin(admin.ModelAdmin):
    list_display = ("proposicion", "opinion", "prediccion", "jornada", "creado_en")
    list_filter = ("opinion", "jornada")
    raw_id_fields = ("proposicion", "usuario", "jornada")
