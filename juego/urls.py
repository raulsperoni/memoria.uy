from django.urls import path

from . import views

app_name = "juego"

urlpatterns = [
    path("hoy/", views.HoyView.as_view(), name="hoy"),
    path("hoy/resultado/", views.ResultadoView.as_view(), name="resultado"),
    path("hoy/votar/<int:item_id>/", views.VotarItemView.as_view(), name="votar-item"),
    path("p/<int:pk>/votar/", views.VotarProposicionView.as_view(), name="votar-proposicion"),
]
