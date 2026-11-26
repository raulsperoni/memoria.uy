from django.contrib import admin
from django.db.models import Count

from .models import Entidad


@admin.register(Entidad)
class EntidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "n_hechos", "n_tonos")
    list_filter = ("tipo",)
    search_fields = ("nombre", "normalized_name")
    readonly_fields = ("normalized_name",)
    ordering = ("nombre",)
    show_full_result_count = False

    def view_on_site(self, obj):
        from django.urls import reverse

        return reverse("archivo:entidad", args=[obj.pk])

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _n_hechos=Count("hechos", distinct=True), _n_tonos=Count("tonos", distinct=True)
        )

    @admin.display(description="hechos", ordering="_n_hechos")
    def n_hechos(self, obj):
        return obj._n_hechos

    @admin.display(description="tonos", ordering="_n_tonos")
    def n_tonos(self, obj):
        return obj._n_tonos
