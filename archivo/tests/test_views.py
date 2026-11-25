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


def test_datos_abiertos(client, historia):
    from juego.models import VotoProposicion

    p = historia.proposiciones.filter(estado="publicada").first()
    VotoProposicion.objects.create(proposicion=p, opinion="acuerdo", session_key="secreta-123")
    assert client.get("/datos/").status_code == 200
    for nombre in ("historias", "hechos", "proposiciones", "burbujas", "cambios"):
        r = client.get(f"/datos/{nombre}.csv")
        assert r.status_code == 200 and r["Content-Type"].startswith("text/csv")
        contenido = b"".join(r.streaming_content).decode()
        assert "secreta-123" not in contenido  # nunca datos de votantes
    contenido = b"".join(client.get("/datos/proposiciones.csv").streaming_content).decode()
    assert p.texto in contenido
    assert client.get("/datos/otra.csv").status_code == 404


@pytest.mark.parametrize("url", ["/archivo/1/1/1/", "/archivo/9999/12/31/", "/archivo/2023/12/31/"])
def test_dia_fuera_de_rango_404(client, db, url):
    assert client.get(url).status_code == 404


def test_dia_futuro_404(client, db):
    d = timezone.localdate() + timezone.timedelta(days=2)
    assert client.get(f"/archivo/{d.year}/{d.month}/{d.day}/").status_code == 404


def test_404_con_estilo(client, db, settings):
    settings.DEBUG = False
    r = client.get("/no-existe/")
    assert r.status_code == 404 and "Esta página no existe" in r.content.decode()


def test_entidad_redirige_a_url_canonica(client, db):
    from core.models import Entidad
    from django.utils.text import slugify

    e = Entidad.objects.create(nombre="Intendencia de Montevideo")
    canonica = reverse("archivo:entidad-slug", args=[e.pk, slugify(e.nombre)])
    for url in (reverse("archivo:entidad", args=[e.pk]), f"/e/{e.pk}/cualquier-cosa/"):
        r = client.get(url)
        assert r.status_code == 301 and r.url == canonica
    assert client.get(canonica).status_code == 200


def test_home_sin_juego_lo_anuncia(client, db):
    html = client.get(reverse("archivo:home")).content.decode()
    assert "¿Qué piensa Uruguay?" in html and "05:30" in html
    assert "Votá noticias anónimamente" not in html


def test_offline_y_service_worker(client, db):
    assert client.get("/offline/").status_code == 200
    sw = client.get("/sw.js").content.decode()
    assert "/offline/" in sw and "'/accounts/'" in sw


def test_no_invita_a_registrarse_si_esta_cerrado(client, db, settings):
    settings.ACCOUNT_ALLOW_SIGNUPS = False
    html = client.get(reverse("account_login")).content.decode()
    assert "Registrate" not in html and "crear cuenta" not in html


def test_extracto_muestra_lo_que_cambio_con_contexto(db):
    c = Cambio(tipo="cuerpo", diff=[
        ["=", "la representación de"],
        ["-", "los trabajadores,"],
        ["+", "las empresas,"],
        ["=", "según el escrutinio de la Corte Electoral"],
    ])
    assert c.extracto() == [{
        "antes": "la representación de",
        "quitado": "los trabajadores,",
        "agregado": "las empresas,",
        "despues": "según el escrutinio de",
    }]


def test_notas_editadas_muestran_titular_y_cambio(client, historia):
    f = historia.fuentes.first()
    snap = f.snapshots.first()
    Cambio.objects.create(
        fuente=f, antes=snap, despues=snap, tipo="cuerpo", cambia_sentido=0.9,
        resumen="Cuerpo editado: 17 caracteres quitados, 13 agregados.",
        diff=[["=", "en nombre de"], ["-", "los trabajadores,"], ["+", "las empresas,"], ["=", "dijo"]],
    )
    for url in (reverse("archivo:cambios"), reverse("archivo:home")):
        html = client.get(url).content.decode()
        assert "caracteres quitados" not in html, url
        assert "los trabajadores," in html and "las empresas," in html, url
        assert "Sánchez desmiente reunión por Praxis" in html, url


def test_home_separa_hoy_y_ayer(client, historia):
    from datetime import timedelta

    vieja = Historia.objects.create(
        titulo="Historia de ayer", slug="historia-de-ayer", procesada_en=timezone.now(),
        n_medios=5, ultima_fuente_en=timezone.now() - timedelta(days=1),
        primera_fuente_en=timezone.now() - timedelta(days=1),
    )
    r = client.get(reverse("archivo:home"))
    assert historia in r.context["hoy"] and vieja not in r.context["hoy"]
    assert vieja in r.context["ayer"]
    html = r.content.decode()
    assert html.index(historia.titulo) < html.index("Ayer") < html.index("Historia de ayer")
