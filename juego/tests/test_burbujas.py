import random

import pytest
from django.urls import reverse

from juego import burbujas
from juego.models import BurbujaRun, VotoProposicion

from .test_juego import _prop


@pytest.fixture
def dos_grupos(db):
    """40 votantes 'A' y 30 'B'. Props 0-5 dividen; 6-7 unen (todos de acuerdo)."""
    random.seed(1)
    props = [_prop(i) for i in range(8)]
    for g, n in (("A", 40), ("B", 30)):
        for v in range(n):
            for i, p in enumerate(props):
                if random.random() < 0.15:
                    continue  # matriz sparse
                if i >= 6:
                    op = "acuerdo"
                else:
                    a_favor = (i % 2 == 0) == (g == "A")
                    op = "acuerdo" if a_favor else "desacuerdo"
                    if random.random() < 0.1:
                        op = "desacuerdo" if op == "acuerdo" else "acuerdo"
                VotoProposicion.objects.create(proposicion=p, opinion=op, session_key=f"{g}{v}")
    return props


def test_insuficiente(db):
    run = burbujas.calcular_burbujas(min_votantes=50, nombrar=False)
    assert run.estado == "insuficiente"


def test_detecta_dos_burbujas(dos_grupos):
    run = burbujas.calcular_burbujas(min_votantes=20, nombrar=False)
    assert run.estado == "ok"
    assert run.k == 2
    tam = sorted(b.tamano for b in run.burbujas.all())
    assert abs(tam[0] - 30) <= 2 and abs(tam[1] - 40) <= 2
    # Pureza: cada grupo sintético cae casi entero en una burbuja
    a = burbujas.burbuja_de({"session_key": "A0"}, run)
    puros = sum(burbujas.burbuja_de({"session_key": f"A{i}"}, run) == a for i in range(40))
    assert puros >= 38
    une, divide = burbujas.consenso_y_division(run)
    assert {p.texto for p, _, _, _ in une} == {"Proposición 6", "Proposición 7"}
    assert len(divide) >= 5
    dist = burbujas.distintivas(run, a)
    assert dist and abs(dist[0][3]) > 50


def test_pagina_burbujas(client, dos_grupos):
    assert client.get(reverse("juego:burbujas")).status_code == 200  # sin run
    burbujas.calcular_burbujas(min_votantes=20, nombrar=False)
    r = client.get(reverse("juego:burbujas"))
    html = r.content.decode()
    assert r.status_code == 200
    assert "Lo que nos une" in html and "Proposición 6" in html
    assert "<svg" in html
