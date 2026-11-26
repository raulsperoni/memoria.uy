"""SEO y acceso para agentes: robots, llms.txt, feeds, .md/.json, JSON-LD, h1, noindex."""

import json
import re
from xml.etree import ElementTree

import pytest
from django.urls import reverse

from archivo.models import Cambio, Hecho, Historia, slug_corto
from core.models import Entidad

from .test_views import historia  # noqa: F401
from .test_pipeline import fakes, medios  # noqa: F401


def _jsonld(html):
    bloques = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert bloques, "sin JSON-LD"
    return [json.loads(b) for b in bloques]


def _nodos(html):
    out = []
    for d in _jsonld(html):
        out += d.get("@graph", [d])
    return out


def _tipos(html):
    return {n["@type"] for n in _nodos(html)}


# --- robots, llms, sitemap ---------------------------------------------------


def test_robots_declara_ia_y_bloquea_lo_personal(client):
    t = client.get("/robots.txt").content.decode()
    for bot in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot"]:
        assert f"User-agent: {bot}" in t
    assert t.count("Disallow: /buscar/") == 2 and t.count("Disallow: /admin/") == 2
    assert "Sitemap: https://memoria.uy/sitemap.xml" in t
    assert "Disallow: /\n" not in t  # nunca se bloquea todo
    assert "/og/" not in t
    # el Sitemap va al final, fuera de los grupos
    assert t.strip().splitlines()[-1].startswith("Sitemap:")


def test_llms_txt(client):
    r = client.get("/llms.txt")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/plain")
    t = r.content.decode()
    assert t.startswith("# memoria.uy")
    for pieza in ["CC BY 4.0", "/feed.xml", ".md", ".json", "/datos/", "Retry-After", "no entran en la licencia"]:
        assert pieza in t


def test_sitemap_todo_https(client, historia):  # noqa: F811
    t = client.get("/sitemap.xml").content.decode()
    locs = re.findall(r"<loc>(.*?)</loc>", t)
    assert locs and all(u.startswith("https://") for u in locs)
    assert f"https://testserver/h/{historia.slug}/" in locs


# --- Una sola URL, slugs, noindex ---------------------------------------------


def test_archivo_redirige_a_la_raiz(client, db):
    r = client.get("/archivo/")
    assert r.status_code == 301 and r["Location"] == "/"


def test_dia_sigue_andando(client, db):
    from django.utils import timezone

    h = timezone.localdate()
    assert client.get(f"/archivo/{h.year}/{h.month}/{h.day}/").status_code == 200


def test_slug_se_corta_entre_palabras():
    titulo = "Gobierno anuncia congelamiento de patentes " * 4
    s = slug_corto(titulo)
    assert len(s) <= 100 and not s.endswith("-")
    assert s.split("-")[-1] in {"gobierno", "anuncia", "congelamiento", "de", "patentes"}
    assert slug_corto("corto") == "corto"
    assert slug_corto("a" * 120) == "a" * 100  # sin guiones: no hay dónde cortar


def test_historia_nueva_usa_slug_corto(db):
    h = Historia(titulo="Palabra " * 30)
    h.asignar_slug()
    assert len(h.slug) <= 100 and h.slug.endswith("palabra")


def test_busqueda_noindex_con_y_sin_query(client, historia):  # noqa: F811
    for url in ["/buscar/?q=Praxis", "/buscar/"]:
        html = client.get(url).content.decode()
        assert '<meta name="robots" content="noindex,follow">' in html
        assert '<link rel="canonical" href="https://memoria.uy/buscar/">' in html


def test_404_sin_canonical_y_con_noindex(client, db):
    r = client.get("/h/no-existe/")
    html = r.content.decode()
    assert r.status_code == 404
    assert 'rel="canonical"' not in html and 'content="noindex"' in html


def test_paginas_normales_se_indexan(client, historia):  # noqa: F811
    html = client.get(f"/h/{historia.slug}/").content.decode()
    assert "noindex" not in html


# --- h1 y semántica -----------------------------------------------------------


@pytest.mark.parametrize("url", ["/", "/cambios/", "/datos/", "/acerca-de/", "/privacidad/", "/burbujas/", "/buscar/", "/hoy/", "/tema/politica/"])
def test_un_solo_h1_y_no_es_el_logo(client, db, url):
    html = client.get(url).content.decode()
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    assert len(h1s) == 1, (url, h1s)
    assert re.sub(r"<[^>]+>|\s+", "", h1s[0]) != "memoria.uy"


def test_historia_h1_es_el_titulo_y_hay_article_time_cite(client, historia):  # noqa: F811
    html = client.get(f"/h/{historia.slug}/").content.decode()
    assert re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S) == [historia.titulo]
    assert "<article" in html and html.count("<time datetime=") >= 3
    assert "<cite>" in html and "<details" in html and " hidden" not in html.split("<main")[1].split("</main>")[0]
    for x in Hecho.objects.filter(historia=historia, oculto=False):
        assert f'id="hecho-{x.pk}"' in html
    # fuentes y citas en el DOM sin JS, no en paneles ocultos
    assert "Diario A" in html and "Diario B" in html


# --- Datos estructurados ------------------------------------------------------


def test_jsonld_historia_valido_con_hechos_y_migas(client, historia):  # noqa: F811
    html = client.get(f"/h/{historia.slug}/").content.decode()
    nodos = {n["@type"]: n for n in _nodos(html)}
    art = nodos["NewsArticle"]
    assert art["headline"] and art["datePublished"] and art["dateModified"]
    assert art["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert art["author"] == {"@id": "https://memoria.uy/#organizacion"}
    claims = art["hasPart"]
    assert claims and all(c["@type"] == "Claim" and c["appearance"] for c in claims)
    assert all(c["@id"].startswith(f"https://memoria.uy/h/{historia.slug}/#hecho-") for c in claims)
    assert art["citation"]
    assert "BreadcrumbList" in nodos and "Organization" in nodos


def test_jsonld_escapa_script_en_titulos(client, historia):  # noqa: F811
    Historia.objects.filter(pk=historia.pk).update(titulo="Hola </script><b>x</b>")
    html = client.get(f"/h/{historia.slug}/").content.decode()
    assert "</script><b>" not in html
    assert any(n.get("name") == "Hola </script><b>x</b>" for n in _nodos(html))


def test_jsonld_home_website_con_busqueda(client, db):
    nodos = {n["@type"]: n for n in _nodos(client.get("/").content.decode())}
    assert nodos["WebSite"]["potentialAction"]["@type"] == "SearchAction"
    assert "{search_term_string}" in nodos["WebSite"]["potentialAction"]["target"]["urlTemplate"]
    assert nodos["Organization"]["sameAs"]


def test_jsonld_entidad_persona_con_punto_de_extension(client, historia, monkeypatch):  # noqa: F811
    from archivo import estructurados

    e = Entidad.objects.filter(tipo="persona", hechos__historia=historia).first()
    if not e:
        e = Entidad.objects.create(nombre="Ana Pérez", normalized_name="ana perez", tipo="persona")
        Hecho.objects.filter(historia=historia).first().entidades.add(e)
    from django.utils.text import slugify

    url = reverse("archivo:entidad-slug", args=[e.pk, slugify(e.nombre)])
    nodos = {n["@type"]: n for n in _nodos(client.get(url).content.decode())}
    assert nodos["Person"]["name"] == e.nombre and "BreadcrumbList" in nodos
    monkeypatch.setattr(estructurados, "datos_entidad_extra", lambda ent: {"sameAs": ["https://www.wikidata.org/wiki/Q1"]})
    nodos = {n["@type"]: n for n in _nodos(client.get(url).content.decode())}
    assert nodos["Person"]["sameAs"] == ["https://www.wikidata.org/wiki/Q1"]


def test_jsonld_organizacion_y_lugar(db):
    from archivo import estructurados

    assert estructurados.entidad_ref(Entidad(pk=1, nombre="BPS", tipo="organizacion"))["@type"] == "Organization"
    assert estructurados.entidad_ref(Entidad(pk=2, nombre="Salto", tipo="lugar"))["@type"] == "Place"


def test_jsonld_cambio_y_dataset(client, historia):  # noqa: F811
    c = Cambio.objects.first()
    n = {x["@type"]: x for x in _nodos(client.get(reverse("archivo:cambio", args=[c.pk])).content.decode())}
    assert n["NewsArticle"]["dateModified"] and n["NewsArticle"]["isBasedOn"]["url"] == c.fuente.url
    d = {x["@type"]: x for x in _nodos(client.get("/datos/").content.decode())}["Dataset"]
    assert d["license"].endswith("by/4.0/") and len(d["distribution"]) >= 5 and "/" in d["temporalCoverage"]


def test_jsonld_dia_y_tema_con_migas(client, historia):  # noqa: F811
    from django.utils import timezone

    h = timezone.localdate()
    assert "BreadcrumbList" in _tipos(client.get(f"/archivo/{h.year}/{h.month}/{h.day}/").content.decode())
    assert "BreadcrumbList" in _tipos(client.get("/tema/politica/").content.decode())


# --- Feeds y .md/.json ---------------------------------------------------------


def test_feed_atom_historias(client, historia):  # noqa: F811
    r = client.get("/feed.xml")
    assert r.status_code == 200 and "atom+xml" in r["Content-Type"]
    ns = {"a": "http://www.w3.org/2005/Atom"}
    raiz = ElementTree.fromstring(r.content)
    entradas = raiz.findall("a:entry", ns)
    assert entradas
    e = entradas[0]
    assert e.find("a:title", ns).text == historia.titulo
    assert e.find("a:link", ns).attrib["href"] == f"https://memoria.uy/h/{historia.slug}/"
    assert e.find("a:updated", ns) is not None and e.find("a:summary", ns).text == historia.resumen
    assert "CC BY 4.0" in raiz.find("a:rights", ns).text


def test_feed_atom_cambios(client, historia):  # noqa: F811
    r = client.get("/cambios/feed.xml")
    assert r.status_code == 200
    ns = {"a": "http://www.w3.org/2005/Atom"}
    assert ElementTree.fromstring(r.content).findall("a:entry", ns)


def test_feeds_declarados_en_el_head(client, db):
    html = client.get("/").content.decode()
    assert 'type="application/atom+xml"' in html and 'href="/feed.xml"' in html


def test_historia_json(client, historia):  # noqa: F811
    r = client.get(f"/h/{historia.slug}.json")
    assert r.status_code == 200 and r["Content-Type"].startswith("application/json")
    d = r.json()
    assert d["url"] == f"https://memoria.uy/h/{historia.slug}/" and d["titulo"] == historia.titulo
    assert d["licencia"]["nombre"] == "CC BY 4.0"
    h = d["hechos"][0]
    assert h["url"].startswith(d["url"] + "#hecho-") and h["fuentes"]
    f = h["fuentes"][0]
    assert set(f) == {"medio", "url", "titulo", "cita", "capturado_en", "sha256"}
    assert f["sha256"] and f["capturado_en"]


def test_json_y_md_no_traen_el_cuerpo_de_las_notas(client, historia):  # noqa: F811
    from archivo.models import Fuente

    Fuente.objects.filter(historia=historia).update(texto="CUERPO-SECRETO-DE-LA-NOTA " * 10)
    for ext in ("json", "md"):
        assert "CUERPO-SECRETO" not in client.get(f"/h/{historia.slug}.{ext}").content.decode()
        assert "CUERPO-SECRETO" not in client.get(f"/h/{historia.slug}/").content.decode()
    assert "CUERPO-SECRETO" not in client.get("/feed.xml").content.decode()


def test_historia_md(client, historia):  # noqa: F811
    r = client.get(f"/h/{historia.slug}.md")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/markdown")
    t = r.content.decode()
    assert t.startswith(f"# {historia.titulo}")
    assert "## Hechos" in t and "](https://" in t and "CC BY 4.0" in t and f"Fuente: https://memoria.uy/h/{historia.slug}/" in t


def test_md_y_json_404(client, db):
    assert client.get("/h/nada.md").status_code == 404
    assert client.get("/h/nada.json").status_code == 404


def test_historia_declara_alternates(client, historia):  # noqa: F811
    html = client.get(f"/h/{historia.slug}/").content.decode()
    assert f'href="/h/{historia.slug}.md"' in html and f'href="/h/{historia.slug}.json"' in html


# --- Datos abiertos ------------------------------------------------------------


def test_csv_con_procedencia_y_licencia(client, historia):  # noqa: F811
    t = b"".join(client.get("/datos/fuentes.csv").streaming_content).decode("utf-8-sig")
    cab = t.splitlines()[0]
    assert "cita" in cab and "capturado_en" in cab and "sha256" in cab and "licencia" in cab and "url_hecho" in cab
    assert "CC BY 4.0" in t and "#hecho-" in t
    h = b"".join(client.get("/datos/hechos.csv").streaming_content).decode("utf-8-sig")
    assert "url_hecho" in h.splitlines()[0] and "#hecho-" in h


def test_hechos_jsonl(client, historia):  # noqa: F811
    lineas = b"".join(client.get("/datos/hechos.jsonl").streaming_content).decode().strip().splitlines()
    assert lineas
    d = json.loads(lineas[0])
    assert d["fuentes"][0]["url"] and d["licencia"].startswith("CC BY 4.0")


# --- 429 -----------------------------------------------------------------------


def test_429_con_retry_after(client, db):
    from django.test import RequestFactory

    from core.error_handlers import ratelimited_error

    for accept in ("text/html", "application/json, text/plain, */*"):
        r = ratelimited_error(RequestFactory().post("/p/1/votar/", HTTP_ACCEPT=accept), Exception())
        assert r.status_code == 429 and r["Retry-After"] == "60"
    assert json.loads(r.content)["retry_after"] == 60


def test_licencia_en_acerca_y_privacidad(client, db):
    a = client.get("/acerca-de/").content.decode()
    assert 'id="licencia"' in a and "CC BY 4.0" in a and "llms.txt" in a
    assert "Licencia de lo que publicamos" in client.get("/privacidad/").content.decode()


def test_jsonld_entidad_con_ficha_de_wikidata(client, historia):  # noqa: F811
    from django.utils.text import slugify

    from archivo.models import FichaEntidad

    e = Entidad.objects.create(nombre="Ana Pérez", normalized_name="ana perez", tipo="persona")
    Hecho.objects.filter(historia=historia).first().entidades.add(e)
    url = reverse("archivo:entidad-slug", args=[e.pk, slugify(e.nombre)])
    persona = {n["@type"]: n for n in _nodos(client.get(url).content.decode())}["Person"]
    assert "sameAs" not in persona
    FichaEntidad.objects.create(
        entidad=e, qid="Q42", descripcion="Política", wikipedia_url="https://es.wikipedia.org/wiki/Ana", foto_url="https://commons.wikimedia.org/x.jpg"
    )
    persona = {n["@type"]: n for n in _nodos(client.get(url).content.decode())}["Person"]
    assert persona["sameAs"] == ["https://www.wikidata.org/wiki/Q42", "https://es.wikipedia.org/wiki/Ana"]
    assert persona["image"].endswith("x.jpg") and persona["description"] == "Política"
    FichaEntidad.objects.filter(entidad=e).update(qid="")
    persona = {n["@type"]: n for n in _nodos(client.get(url).content.decode())}["Person"]
    assert "sameAs" not in persona
