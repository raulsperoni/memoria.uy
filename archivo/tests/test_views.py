import pytest
from django.urls import reverse
from django.utils import timezone

from archivo import pipeline
from archivo.models import Cambio, Fuente, Historia, Medio

from .test_pipeline import TEXTO_PRAXIS, _extraida, fakes, medios  # noqa: F401


@pytest.fixture
def historia(fakes, medios):  # noqa: F811
    ext, dec = fakes
    a, b = medios
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Sánchez y ediles hablaron de Praxis", TEXTO_PRAXIS)
    h = pipeline.agrupar(f1)
    pipeline.agrupar(f2)
    h.refresh_from_db()
    pipeline.procesar_historia(h)
    h.refresh_from_db()
    # Un cambio de título con sentido
    from archivo.providers.extract import set_extractor  # noqa
    from .test_pipeline import html
    ext.paginas[f1.url] = (200, html("Sánchez desmiente reunión por Praxis", TEXTO_PRAXIS))
    dec.respuestas["cambia_sentido"] = 0.9
    pipeline.recrawl(f1)
    return h


def test_paginas_publicas(client, historia):
    hoy = timezone.localdate()
    cambio = Cambio.objects.first()
    urls = [
        reverse("archivo:hoy"),
        reverse("archivo:historia", args=[historia.slug]),
        reverse("archivo:cambios"),
        reverse("archivo:cambios") + "?sentido=1&medio=a",
        reverse("archivo:cambio", args=[cambio.pk]),
        reverse("archivo:medio", args=["a"]),
        reverse("archivo:dia", kwargs={"y": hoy.year, "m": hoy.month, "d": hoy.day}),
        reverse("archivo:buscar") + "?q=Praxis",
        reverse("archivo:buscar"),
    ]
    for url in urls:
        r = client.get(url)
        assert r.status_code == 200, url

    r = client.get(reverse("archivo:historia", args=[historia.slug]))
    html = r.content.decode()
    assert historia.titulo in html
    assert "Diario A" in html and "Diario B" in html
    assert "application/ld+json" in html

    r = client.get(reverse("archivo:cambio", args=[cambio.pk]))
    assert "Sánchez desmiente" in r.content.decode()
    assert "altera el sentido" in r.content.decode()


def test_busqueda_encuentra(client, historia):
    r = client.get(reverse("archivo:buscar") + "?q=Praxis")
    assert historia.titulo in r.content.decode()


def test_dia_invalido_404(client, db):
    assert client.get("/archivo/2026/13/40/").status_code == 404


def test_historia_no_procesada_404(client, db):
    h = Historia.objects.create(titulo="x", slug="x")
    assert client.get(reverse("archivo:historia", args=["x"])).status_code == 404


def test_sitemap_incluye_historias(client, historia):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert f"/h/{historia.slug}/" in r.content.decode()


def test_metricas_resumen(historia):
    from archivo.metricas import lineas_html, lineas_texto, resumen_ingesta

    r = resumen_ingesta()
    assert r["historias"] == 1
    assert r["cambios"] == 1
    assert lineas_texto(r) and lineas_html(r)


def test_og_y_pwa(client, historia):
    r = client.get(f"/og/h/{historia.slug}.png")
    assert r.status_code == 200 and r["Content-Type"] == "image/png" and r.content[:4] == b"\x89PNG"
    assert client.get("/og/hoy.png").status_code == 200
    assert client.get("/og/memoria.png").status_code == 200
    assert client.get("/og/h/no-existe.png").status_code == 404
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200 and r.json()["short_name"] == "memoria.uy"
    assert client.get("/sw.js")["Content-Type"] == "application/javascript"
    html = client.get(f"/h/{historia.slug}/").content.decode()
    assert f"/og/h/{historia.slug}.png" in html
