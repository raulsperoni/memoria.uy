from django.urls import path

from . import datos, views

app_name = "archivo"

urlpatterns = [
    path("", views.HoyView.as_view(), name="home"),
    path("archivo/", views.HoyView.as_view(), name="hoy"),
    path("archivo/<int:y>/<int:m>/<int:d>/", views.DiaView.as_view(), name="dia"),
    path("h/<slug:slug>/", views.HistoriaView.as_view(), name="historia"),
    path("e/<int:pk>/", views.EntidadView.as_view(), name="entidad"),
    path("e/<int:pk>/<slug:slug>/", views.EntidadView.as_view(), name="entidad-slug"),
    path("cambios/", views.CambiosView.as_view(), name="cambios"),
    path("cambios/<int:pk>/", views.CambioView.as_view(), name="cambio"),
    path("medios/<slug:slug>/", views.MedioView.as_view(), name="medio"),
    path("og/h/<slug:slug>.png", views.og_historia, name="og-historia"),
    path("og/e/<int:pk>.png", views.og_entidad, name="og-entidad"),
    path("og/cambios/<int:pk>.png", views.og_cambio, name="og-cambio"),
    path("datos/", datos.datos, name="datos"),
    path("datos/<slug:nombre>.csv", datos.export, name="export"),
    path("buscar/", views.BuscarView.as_view(), name="buscar"),
]
