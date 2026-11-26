import pytest
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from archivo.models import Historia, Proposicion
from core.ratelimit import ip_cliente


def _req(**meta):
    return RequestFactory().post("/x", **meta)


@override_settings(RATELIMIT_CONFIAR_X_REAL_IP=True)
def test_usa_x_real_ip_si_viene():
    assert ip_cliente(_req(REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="203.0.113.7")) == "203.0.113.7"


@override_settings(RATELIMIT_CONFIAR_X_REAL_IP=True)
def test_sin_header_o_vacio_cae_a_remote_addr():
    assert ip_cliente(_req(REMOTE_ADDR="10.0.0.1")) == "10.0.0.1"
    assert ip_cliente(_req(REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="  ")) == "10.0.0.1"


@override_settings(RATELIMIT_CONFIAR_X_REAL_IP=False)
def test_sin_confianza_ignora_el_header():
    assert ip_cliente(_req(REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="203.0.113.7")) == "10.0.0.1"


def test_produccion_confia_y_dev_no():
    import json, os, subprocess, sys

    def valor(debug):
        env = {**os.environ, "DEBUG": debug, "DJANGO_SETTINGS_MODULE": "memoria.settings"}
        out = subprocess.run(
            [sys.executable, "-c", "from django.conf import settings as s;print(s.RATELIMIT_CONFIAR_X_REAL_IP)"],
            env=env, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip().splitlines()[-1]

    assert valor("False") == "True" and valor("True") == "False"


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=True, RATELIMIT_CONFIAR_X_REAL_IP=True)
def test_el_limite_es_por_cliente_y_no_por_proxy(client):
    h = Historia.objects.create(titulo="h", slug="h", resumen="r", procesada_en=timezone.now())
    p = Proposicion.objects.create(historia=h, texto="t", estado="publicada")
    url = reverse("juego:votar-proposicion", args=[p.pk])
    # 60 votos del cliente A (misma IP de proxy): el 61 es 429
    for _ in range(60):
        assert client.post(url, {"opinion": "acuerdo"}, REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="198.51.100.1").status_code != 429
    r = client.post(url, {"opinion": "acuerdo"}, REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="198.51.100.1")
    assert r.status_code == 429 and r["Retry-After"] == "60"
    # otro cliente detrás del mismo proxy no queda bloqueado
    assert client.post(url, {"opinion": "acuerdo"}, REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="198.51.100.2").status_code != 429
