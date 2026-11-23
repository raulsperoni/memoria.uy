from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from archivo.models import Historia, Proposicion
from juego import logica
from juego.models import Jornada, JornadaItem, VotoProposicion, bucket_de


def _prop(i, categoria="politica", div=0.6, calidad=0.9, n_medios=2, tema=""):
    h = Historia.objects.create(
        titulo=f"Historia {i}", slug=f"historia-{i}", resumen="r", categoria=categoria,
        n_medios=n_medios, procesada_en=timezone.now(),
    )
    return Proposicion.objects.create(
        historia=h, texto=f"Proposición {i}", estado="publicada", calidad=calidad, divisividad=div, tema=tema
    )


@pytest.fixture
def props(db):
    return [
        _prop(1, "politica", 0.9, n_medios=5),
        _prop(2, "politica", 0.8, n_medios=4),
        _prop(3, "politica", 0.7, n_medios=4),  # 3ra de política: debería quedar afuera por diversidad
        _prop(4, "economia", 0.6, n_medios=3),
        _prop(5, "sociedad", 0.1, n_medios=1),  # consenso
        _prop(6, "salud", 0.5, n_medios=2),
        _prop(7, "seguridad", 0.9, calidad=0.3),  # baja calidad
    ]


def test_bucket():
    assert [bucket_de(x) for x in (0, 19.9, 20, 55, 80, 100)] == [0, 0, 1, 2, 4, 4]


def test_armar_jornada_diversidad_y_consenso(props):
    j = logica.armar_jornada()
    textos = [it.proposicion.texto for it in j.items_ordenados()]
    assert len(textos) == 5
    assert "Proposición 5" in textos  # consenso incluido
    assert "Proposición 7" not in textos  # calidad baja
    cats = [it.proposicion.historia.categoria for it in j.items_ordenados()]
    assert cats.count("politica") <= 2
    assert j.publicada
    # idempotente
    assert logica.armar_jornada().pk == j.pk


def test_armar_jornada_sin_candidatas(db):
    assert logica.armar_jornada() is None


def test_recurrente(props):
    vieja = _prop(99, "economia", 0.8, tema="IRPF")
    Proposicion.objects.filter(pk=vieja.pk).update(creada_en=timezone.now() - timedelta(days=20))
    j = logica.armar_jornada()
    rec = [it for it in j.items_ordenados() if it.recurrente]
    assert len(rec) == 1 and rec[0].proposicion_id == vieja.pk


def _jugar(client, j, opinion="acuerdo", pred=4):
    for it in j.items_ordenados():
        r = client.post(reverse("juego:votar-item", args=[it.pk]), {"opinion": opinion, "prediccion": pred}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200


def test_flujo_completo(client, props):
    j = logica.armar_jornada()
    # Otros votantes: 100 % de acuerdo en todo
    for it in j.items_ordenados():
        VotoProposicion.objects.create(proposicion=it.proposicion, opinion="acuerdo", session_key="otro", jornada=j)
    r = client.get(reverse("juego:hoy"))
    assert r.status_code == 200 and "1/5" in r.content.decode()
    # resultado redirige si no terminó
    assert client.get(reverse("juego:resultado")).status_code == 302
    _jugar(client, j)
    assert VotoProposicion.objects.exclude(session_key='otro').count() == 5
    r = client.get(reverse("juego:hoy"))
    assert r.status_code == 302 and r.url == reverse("juego:resultado")
    r = client.get(reverse("juego:resultado"))
    html = r.content.decode()
    assert "Leí a Uruguay 5/5" in html  # 100 % de acuerdo, predijo 80–100
    assert "wa.me" in html


def test_no_se_puede_votar_dos_veces(client, props):
    j = logica.armar_jornada()
    it = j.items_ordenados()[0]
    url = reverse("juego:votar-item", args=[it.pk])
    client.post(url, {"opinion": "acuerdo", "prediccion": 1})
    client.post(url, {"opinion": "desacuerdo", "prediccion": 3})
    v = VotoProposicion.objects.get()
    assert v.opinion == "acuerdo" and v.prediccion == 1


def test_validacion(client, props):
    j = logica.armar_jornada()
    it = j.items_ordenados()[0]
    url = reverse("juego:votar-item", args=[it.pk])
    assert client.post(url, {"opinion": "x", "prediccion": 1}).status_code == 400
    assert client.post(url, {"opinion": "acuerdo", "prediccion": 9}).status_code == 400


def test_puntaje_contra_resultado(props):
    j = logica.armar_jornada()
    items = list(j.items_ordenados())
    p = items[0].proposicion
    # 3 de acuerdo, 1 en desacuerdo → 75 % → bucket 3
    for i, op in enumerate(["acuerdo", "acuerdo", "acuerdo", "desacuerdo"]):
        VotoProposicion.objects.create(proposicion=p, opinion=op, session_key=f"s{i}", jornada=j)
    yo = {"session_key": "yo"}
    VotoProposicion.objects.create(proposicion=p, opinion="nose", prediccion=3, session_key="yo", jornada=j)
    filas, aciertos = logica.puntaje(yo, j)
    assert aciertos == 1
    assert filas[0][2].pct_acuerdo == 75


def test_racha(props):
    yo = {"session_key": "yo"}
    hoy = timezone.localdate()
    for d in range(3):
        f = hoy - timedelta(days=d)
        j = Jornada.objects.create(fecha=f, publicada=True)
        p = _prop(100 + d)
        JornadaItem.objects.create(jornada=j, proposicion=p)
        VotoProposicion.objects.create(proposicion=p, opinion="acuerdo", session_key="yo", jornada=j)
    assert logica.racha(yo) == 3


def test_voto_desde_archivo(client, props):
    p = props[0]
    r = client.post(reverse("juego:votar-proposicion", args=[p.pk]), {"opinion": "desacuerdo"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert VotoProposicion.objects.get().jornada is None
    r = client.get(reverse("archivo:historia", args=[p.historia.slug]))
    assert "vos: en desacuerdo" in r.content.decode()


def test_reclamo_de_votos_al_login(client, props):
    j = logica.armar_jornada()
    _jugar(client, j)
    u = User.objects.create_user("ana", "ana@x.uy", "clave-segura-123")
    from allauth.account.models import EmailAddress

    EmailAddress.objects.create(user=u, email="ana@x.uy", verified=True, primary=True)
    r = client.post(reverse("account_login"), {"login": "ana@x.uy", "password": "clave-segura-123"})
    assert r.status_code in (200, 302)
    assert VotoProposicion.objects.filter(usuario=u).count() == 5


def test_home_muestra_jornada(client, props):
    logica.armar_jornada()
    r = client.get("/")
    assert "¿Qué piensa Uruguay?" in r.content.decode()
    assert "jugar la de hoy" in r.content.decode()


def test_voto_propio_no_cuenta_para_la_prediccion(client, props):
    j = logica.armar_jornada()
    _jugar(client, j, opinion="acuerdo", pred=4)  # único votante: no hay con qué comparar
    r = client.get(reverse("juego:resultado"))
    assert "Leí a Uruguay 0/5" in r.content.decode()


def test_nose_sin_opiniones_confirma_el_voto(client, props):
    p = props[0]
    r = client.post(reverse("juego:votar-proposicion", args=[p.pk]), {"opinion": "nose"}, HTTP_HX_REQUEST="true")
    html = r.content.decode()
    assert "vos: no sé" in html and "todavía no hay otras opiniones" in html


def test_plural_opiniones(client, props):
    p = props[0]
    for i in range(2):
        VotoProposicion.objects.create(proposicion=p, opinion="acuerdo", session_key=f"otro{i}")
    r = client.post(reverse("juego:votar-proposicion", args=[p.pk]), {"opinion": "acuerdo"}, HTTP_HX_REQUEST="true")
    html = r.content.decode()
    assert "3 opiniones" in html and "opiniónes" not in html


def test_cada_paso_del_juego_tiene_url(client, props):
    j = logica.armar_jornada()
    it = j.items_ordenados()[0]
    r = client.post(reverse("juego:votar-item", args=[it.pk]), {"opinion": "acuerdo", "prediccion": 2}, HTTP_HX_REQUEST="true")
    url = f"{reverse('juego:hoy')}?ver={it.pk}"
    assert r["HX-Push-Url"] == url
    assert "1/5" in r.content.decode()  # la cabecera viaja con el resultado
    # Recargar esa URL muestra el mismo resultado, no la siguiente frase
    html = client.get(url).content.decode()
    assert it.proposicion.texto in html and "siguiente" in html
    # Sin HTMX: POST → redirect a la misma URL
    it2 = j.items_ordenados()[1]
    r = client.post(reverse("juego:votar-item", args=[it2.pk]), {"opinion": "acuerdo", "prediccion": 2})
    assert r.status_code == 302 and r.url == f"{reverse('juego:hoy')}?ver={it2.pk}"


def test_ver_item_no_votado_muestra_la_pregunta(client, props):
    j = logica.armar_jornada()
    it = j.items_ordenados()[2]
    r = client.get(f"{reverse('juego:hoy')}?ver={it.pk}")
    assert "1/5" in r.content.decode() and "confirmar" in r.content.decode()


def test_sin_jornada(client, db):
    html = client.get(reverse("juego:hoy")).content.decode()
    assert "05:30" in html and "Vuelve" not in html
