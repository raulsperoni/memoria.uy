"""Cookies solo cuando hacen falta, Cache-Control del HTML público y ajustes de producción."""

import json
import os
import subprocess
import sys

import pytest
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from archivo.models import Historia, Proposicion
from juego import logica
from juego.models import VotoProposicion


@pytest.fixture
def prop(db):
    h = Historia.objects.create(
        titulo="Historia uno", slug="historia-uno", resumen="r", categoria="politica",
        n_medios=3, procesada_en=timezone.now(),
    )
    return Proposicion.objects.create(historia=h, texto="Una frase", estado="publicada", calidad=0.9, divisividad=0.6)


PAGINAS = ["/", "/hoy/", "/burbujas/", "/cambios/", "/datos/", "/acerca-de/", "/privacidad/", "/h/historia-uno/"]


@pytest.mark.parametrize("url", PAGINAS)
def test_get_anonimo_no_setea_sesion(client, prop, url):
    logica.armar_jornada()
    r = client.get(url)
    assert r.status_code == 200, url
    assert "sessionid" not in r.cookies, url
    assert not VotoProposicion.objects.exists()
    assert "votante_anonimo" not in client.session


def test_paginas_publicas_sin_ninguna_cookie(client, prop):
    for url in ["/", "/h/historia-uno/", "/cambios/", "/datos/", "/acerca-de/"]:
        r = client.get(url)
        assert not r.cookies, (url, dict(r.cookies))


def test_votar_crea_sesion_y_voto(prop):
    c = Client(enforce_csrf_checks=True)
    r = c.get(reverse("archivo:opinar", args=[prop.historia.slug]), HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and "csrftoken" in r.cookies
    token = r.cookies["csrftoken"].value
    r = c.post(
        reverse("juego:votar-proposicion", args=[prop.pk]),
        {"opinion": "acuerdo"},
        HTTP_X_CSRFTOKEN=token,
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    v = VotoProposicion.objects.get()
    assert v.session_key and v.session_key == c.session["votante_anonimo"]


def test_votos_anonimos_pasan_a_la_cuenta_al_login(prop, client):
    from allauth.account.models import EmailAddress

    client.post(reverse("juego:votar-proposicion", args=[prop.pk]), {"opinion": "desacuerdo"})
    u = User.objects.create_user("ana", "ana@x.uy", "clave-segura-123")
    EmailAddress.objects.create(user=u, email="ana@x.uy", verified=True, primary=True)
    client.post(reverse("account_login"), {"login": "ana@x.uy", "password": "clave-segura-123"})
    voto = VotoProposicion.objects.get()
    assert voto.usuario == u and voto.session_key is None


def test_lectura_sin_sesion_no_ve_votos_ajenos(client, prop):
    VotoProposicion.objects.create(proposicion=prop, opinion="acuerdo", usuario=User.objects.create_user("x"))
    r = client.get(reverse("archivo:opinar", args=[prop.historia.slug]), HTTP_HX_REQUEST="true")
    assert "vos:" not in r.content.decode()


# --- Cache-Control -----------------------------------------------------------


def test_html_publico_anonimo_se_puede_cachear(client, prop):
    cc = client.get("/h/historia-uno/")["Cache-Control"]
    assert "public" in cc and "s-maxage" in cc and "stale-while-revalidate" in cc


def test_con_sesion_no_se_cachea_en_publico(prop):
    c = Client()
    c.cookies["sessionid"] = "x"
    assert "public" not in c.get("/h/historia-uno/").get("Cache-Control", "")


def test_paginas_personales_o_de_busqueda_no_se_cachean(client, prop):
    logica.armar_jornada()
    for url in ["/hoy/", "/burbujas/", "/buscar/?q=uno", "/hoy/resultado/", reverse("archivo:opinar", args=[prop.historia.slug])]:
        r = client.get(url)
        assert "public" not in r.get("Cache-Control", ""), url


def test_error_y_post_no_se_cachean(client, prop):
    assert "public" not in client.get("/h/no-existe/").get("Cache-Control", "")


# --- Ajustes de producción ---------------------------------------------------


def _ajustes(debug):
    env = {**os.environ, "DEBUG": debug, "DJANGO_SETTINGS_MODULE": "memoria.settings"}
    code = (
        "import json;from django.conf import settings as s;"
        "print(json.dumps([s.SECURE_PROXY_SSL_HEADER, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, s.SECURE_HSTS_SECONDS]))"
    )
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_produccion_cookies_secure_hsts_y_proxy():
    assert _ajustes("False") == [["HTTP_X_FORWARDED_PROTO", "https"], True, True, 30 * 24 * 3600]


def test_dev_local_sin_https():
    assert _ajustes("True") == [None, False, False, 0]


def test_sitemap_https_detras_del_proxy(client, prop):
    with override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")):
        r = client.get("/sitemap.xml", HTTP_X_FORWARDED_PROTO="https", HTTP_HOST="memoria.uy")
    cuerpo = r.content.decode()
    assert "<loc>https://memoria.uy/h/historia-uno/</loc>" in cuerpo
    assert "http://memoria.uy" not in cuerpo
