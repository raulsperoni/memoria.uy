import pytest
from django.urls import reverse



@pytest.mark.django_db
class TestViews:
    """Test cases for views."""

    def test_homepage_authenticated(self, authenticated_client):
        """Test that authenticated users can access the homepage."""
        url = reverse('archivo:home')
        response = authenticated_client.get(url)
        assert response.status_code == 200

    def test_admin_access(self, admin_client):
        """Test that admin users can access the admin page."""
        url = reverse('admin:index')
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_admin_access_denied(self, authenticated_client):
        """Test that regular users cannot access the admin page."""
        url = reverse('admin:index')
        response = authenticated_client.get(url)
        assert response.status_code == 302  # Redirect to login page


@pytest.mark.django_db
@pytest.mark.parametrize(
    "viejo,nuevo",
    [
        ("/noticias/", "/"),
        ("/noticias/alguna-noticia/", "/"),
        ("/bienvenida/", "/"),
        ("/mapa/", "/burbujas/"),
        ("/clusters/report/", "/burbujas/"),
        ("/clusters/stats/", "/burbujas/"),
    ],
)
def test_paginas_viejas_redirigen(client, viejo, nuevo):
    r = client.get(viejo)
    assert r.status_code == 301 and r.url == nuevo


@pytest.mark.django_db
def test_voto_limitado_por_minuto(client, settings):
    """El juego limita los votos por IP (django-ratelimit) y responde 429."""
    from django.core.cache import cache

    from juego.tests.test_juego import _prop

    cache.clear()
    p = _prop(1)
    url = reverse("juego:votar-proposicion", args=[p.pk])
    codigos = [client.post(url, {"opinion": "acuerdo"}, HTTP_HX_REQUEST="true").status_code for _ in range(61)]
    assert codigos[-1] == 429


@pytest.mark.django_db
def test_acerca_y_privacidad_describen_el_producto_actual(client):
    for nombre in ("acerca_de", "privacidad"):
        html = client.get(reverse(nombre)).content.decode()
        assert "extensión" not in html and "buena noticia" not in html
        assert "¿Qué piensa Uruguay?" in html or "votos individuales" in html
