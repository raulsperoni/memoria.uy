from django.urls import path
from django.views.generic import RedirectView

from . import datos, feeds, views

app_name = "archivo"

urlpatterns = [
    path("", views.HoyView.as_view(), name="home"),
    # Una sola URL canónica para «lo que pasó hoy»: la raíz.
    path("archivo/", RedirectView.as_view(pattern_name="archivo:home", permanent=True), name="hoy"),
    path("archivo/<int:y>/<int:m>/<int:d>/", views.DiaView.as_view(), name="dia"),
    path("h/<slug:slug>/", views.HistoriaView.as_view(), name="historia"),
    path("h/<slug:slug>.md", views.historia_md, name="historia-md"),
    path("h/<slug:slug>.json", views.historia_json, name="historia-json"),
    path("h/<slug:slug>/opinar/", views.OpinarView.as_view(), name="opinar"),
    path("feed.xml", feeds.FeedHistorias(), name="feed"),
    path("cambios/feed.xml", feeds.FeedCambios(), name="feed-cambios"),
    path("e/<int:pk>/", views.EntidadView.as_view(), name="entidad"),
    path("e/<int:pk>/<slug:slug>/", views.EntidadView.as_view(), name="entidad-slug"),
    path("tema/<slug:categoria>/", views.TemaView.as_view(), name="tema"),
    path("cambios/", views.CambiosView.as_view(), name="cambios"),
    path("cambios/<int:pk>/", views.CambioView.as_view(), name="cambio"),
    path("medios/<slug:slug>/", views.MedioView.as_view(), name="medio"),
    path("og/h/<slug:slug>.png", views.og_historia, name="og-historia"),
    path("og/e/<int:pk>.png", views.og_entidad, name="og-entidad"),
    path("og/cambios/<int:pk>.png", views.og_cambio, name="og-cambio"),
    path("datos/", datos.datos, name="datos"),
    path("datos/<slug:nombre>.csv", datos.export, name="export"),
    path("datos/<slug:nombre>.jsonl", datos.export_jsonl, name="export-jsonl"),
    path("buscar/", views.BuscarView.as_view(), name="buscar"),
]
