"""El admin carga: changelist y pantalla de cambio de cada ModelAdmin, el
índice agrupado y las acciones masivas, sin N+1 en las listas."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from archivo.models import (
    Cambio, Decision, Fuente, Hecho, HechoFuente, Historia, Medio, Proposicion,
    Snapshot, Tono, UsoProveedor,
)
from core.models import Entidad
from juego.models import (
    Burbuja, BurbujaMiembro, BurbujaPatron, BurbujaRun, Jornada, JornadaItem,
    VotoProposicion,
)

pytestmark = pytest.mark.django_db

SCOPE = {"archivo", "juego", "core"}


def crear_datos(n=1, sufijo=""):
    """n historias completas: medio → fuente → historia → hecho → proposición, etc."""
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=f"votante{sufijo}", defaults={"email": f"v{sufijo}@x.uy"})
    medio, _ = Medio.objects.get_or_create(
        slug=f"medio{sufijo}", defaults={"nombre": f"Medio {sufijo}", "dominio": f"medio{sufijo}.uy",
                                         "rss_urls": ["https://x.uy/rss"]},
    )
    for i in range(n):
        k = f"{sufijo}{i}"
        historia = Historia.objects.create(
            titulo=f"Historia {k}", slug=f"historia-{k}", procesada_en=timezone.now(), n_medios=1,
        )
        fuente = Fuente.objects.create(
            medio=medio, url=f"https://medio.uy/nota-{k}", titulo=f"Nota {k}", estado="procesada",
            historia=historia, interes=0.8, publicada_en=timezone.now(), texto="texto",
        )
        antes = Snapshot.objects.create(fuente=fuente, storage_key=f"a{k}", contenido_hash="a", proveedor="fake")
        despues = Snapshot.objects.create(fuente=fuente, storage_key=f"b{k}", contenido_hash="b", proveedor="fake")
        fuente.ultimo_snapshot = despues
        fuente.save()
        Cambio.objects.create(
            fuente=fuente, antes=antes, despues=despues, tipo="cuerpo", cambia_sentido=0.7,
            diff=[["=", "hola"], ["-", "viejo"], ["+", "nuevo"]],
        )
        ent = Entidad.objects.create(nombre=f"Persona {k}", tipo="persona")
        hecho = Hecho.objects.create(historia=historia, texto=f"Hecho {k}")
        hecho.entidades.add(ent)
        HechoFuente.objects.create(hecho=hecho, fuente=fuente, fiel=0.9)
        prop = Proposicion.objects.create(historia=historia, texto=f"Prop {k}", estado="publicada", calidad=0.8)
        prop.hechos.add(hecho)
        Tono.objects.create(fuente=fuente, entidad=ent, valencia=-1, cita="cita", verificado=0.7)
        jornada = Jornada.objects.get_or_create(fecha=timezone.localdate() - timezone.timedelta(days=i))[0]
        JornadaItem.objects.create(jornada=jornada, proposicion=prop)
        VotoProposicion.objects.create(proposicion=prop, usuario=user if i == 0 else None,
                                       session_key=None if i == 0 else f"s{k}", opinion="acuerdo",
                                       prediccion=2, jornada=jornada)
        Decision.objects.create(pregunta="interes", entrada_hash=k, valor=0.5, modelo="jev")
        UsoProveedor.objects.get_or_create(proveedor=f"p{k}", operacion="x", defaults={"costo_usd": 0.1})
        run = BurbujaRun.objects.create(k=1, n_votantes=3)
        b = Burbuja.objects.create(run=run, numero=0, nombre=f"B{k}")
        BurbujaPatron.objects.create(run=run, burbuja=b, proposicion=prop, acuerdo=2)
        BurbujaMiembro.objects.create(run=run, burbuja=b, usuario=user, x=0, y=0)


@pytest.fixture
def staff(client, django_user_model):
    u = django_user_model.objects.create_superuser("admin", "a@x.uy", "pw")
    client.force_login(u)
    return u


def modelos_registrados():
    return sorted(
        (m for m in admin.site._registry if m._meta.app_label in SCOPE),
        key=lambda m: m._meta.label,
    )


def nombre(m, vista):
    return f"admin:{m._meta.app_label}_{m._meta.model_name}_{vista}"


def test_todos_los_modelos_del_proyecto_estan_registrados():
    from django.apps import apps

    faltan = [m._meta.label for a in SCOPE for m in apps.get_app_config(a).get_models()
              if m not in admin.site._registry]
    # JornadaItem, HechoFuente se editan dentro de su padre
    assert set(faltan) <= {"archivo.HechoFuente", "juego.JornadaItem"}, faltan


def test_changelist_y_cambio_de_cada_modelo(client, staff):
    crear_datos(2)
    for m in modelos_registrados():
        r = client.get(reverse(nombre(m, "changelist")))
        assert r.status_code == 200, m
        obj = m.objects.first()
        assert obj is not None, f"el dataset de test no cubre {m._meta.label}"
        r = client.get(reverse(nombre(m, "change"), args=[obj.pk]))
        assert r.status_code == 200, m
        r = client.get(reverse(nombre(m, "add"))) if admin.site._registry[m].has_add_permission(r.wsgi_request) else r
        assert r.status_code == 200, m


def test_buscar_y_filtrar_no_rompe(client, staff):
    crear_datos(1)
    for m in modelos_registrados():
        ma = admin.site._registry[m]
        url = reverse(nombre(m, "changelist"))
        if ma.search_fields:
            assert client.get(url, {"q": "x"}).status_code == 200, m
        for f in ma.list_filter:
            campo = f if isinstance(f, str) else f[0]
            assert client.get(url, {f"{campo}__isnull": "False"}).status_code in (200, 302), (m, campo)


@pytest.mark.parametrize("modelo", ["fuente", "historia", "hecho", "proposicion", "tono", "cambio",
                                    "medio", "snapshot"])
def test_changelist_sin_n_mas_uno(client, staff, modelo, django_assert_max_num_queries):
    """Pocas filas y muchas filas hacen las mismas consultas."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    url = reverse(f"admin:archivo_{modelo}_changelist")
    crear_datos(2, "a")
    client.get(url)  # calienta caches (content types, sesión)
    with CaptureQueriesContext(connection) as pocas:
        assert client.get(url).status_code == 200
    crear_datos(8, "b")
    with CaptureQueriesContext(connection) as muchas:
        assert client.get(url).status_code == 200
    assert len(muchas) <= len(pocas) + 1, [q["sql"] for q in muchas.captured_queries]


@pytest.mark.parametrize("modelo", ["jornada", "votoproposicion", "burbuja", "burbujapatron"])
def test_changelist_juego_sin_n_mas_uno(client, staff, modelo):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    url = reverse(f"admin:juego_{modelo}_changelist")
    crear_datos(2, "a")
    client.get(url)
    with CaptureQueriesContext(connection) as pocas:
        client.get(url)
    crear_datos(8, "b")
    with CaptureQueriesContext(connection) as muchas:
        assert client.get(url).status_code == 200
    assert len(muchas) <= len(pocas) + 1


def test_indice_agrupado_y_pulso(client, staff):
    crear_datos(1)
    r = client.get(reverse("admin:index"))
    assert r.status_code == 200
    html = r.content.decode()
    for titulo in ["Medios y fuentes", "Historias", "Tono y notas editadas", "Pipeline", "Juego y burbujas", "Cuentas"]:
        assert titulo in html
    assert "Fuentes en 24 h" in html and "Jornada de hoy" in html
    # la pantalla de una app real sigue andando
    assert client.get(reverse("admin:app_list", args=["archivo"])).status_code == 200


def test_ver_en_el_sitio_de_una_historia(client, staff):
    crear_datos(1)
    h = Historia.objects.first()
    r = client.get(reverse("admin:archivo_historia_change", args=[h.pk]))
    assert f"/h/{h.slug}/" in r.content.decode()  # botón «Ver en el sitio»


def post_accion(client, m, accion, objs):
    return client.post(
        reverse(nombre(m, "changelist")),
        {"action": accion, "_selected_action": [o.pk for o in objs]},
        follow=True,
    )


def test_acciones_masivas(client, staff):
    crear_datos(2)
    fuentes = list(Fuente.objects.all())
    r = post_accion(client, Fuente, "volver_a_extraer", fuentes)
    assert r.status_code == 200 and Fuente.objects.filter(estado="descubierta").count() == 2
    post_accion(client, Fuente, "recrawl_ahora", fuentes)
    assert Fuente.objects.filter(proximo_recrawl__isnull=False).count() == 2
    post_accion(client, Fuente, "recalcular_tonos", fuentes)
    assert Fuente.objects.filter(tonos_en__isnull=True).count() == 2

    historias = list(Historia.objects.all())
    post_accion(client, Historia, "cerrar", historias)
    assert Historia.objects.filter(estado="cerrada").count() == 2
    post_accion(client, Historia, "reabrir", historias)
    assert Historia.objects.filter(estado="abierta").count() == 2

    hechos = list(Hecho.objects.all())
    post_accion(client, Hecho, "ocultar", hechos)
    assert Hecho.objects.filter(oculto=True).count() == 2
    post_accion(client, Hecho, "mostrar", hechos)
    assert not Hecho.objects.filter(oculto=True).exists()

    props = list(Proposicion.objects.all())
    post_accion(client, Proposicion, "descartar", props)
    assert Proposicion.objects.filter(estado="descartada").count() == 2
    post_accion(client, Proposicion, "volver_candidata", props)
    post_accion(client, Proposicion, "publicar", props)
    assert Proposicion.objects.filter(estado="publicada").count() == 2

    medios = list(Medio.objects.all())
    post_accion(client, Medio, "desactivar", medios)
    assert not Medio.objects.filter(activo=True).exists()
    post_accion(client, Medio, "activar", medios)
    assert Medio.objects.filter(activo=True).exists()

    jornadas = list(Jornada.objects.all())
    post_accion(client, Jornada, "publicar", jornadas)
    assert Jornada.objects.filter(publicada=True).count() == len(jornadas)
    post_accion(client, Jornada, "despublicar", jornadas)
    assert not Jornada.objects.filter(publicada=True).exists()


def test_acciones_que_llaman_al_pipeline(client, staff, monkeypatch):
    crear_datos(1)
    from archivo import pipeline

    llamadas = []
    monkeypatch.setattr(pipeline, "procesar_historia", lambda h: llamadas.append(h.pk) or True)
    monkeypatch.setattr(pipeline, "descubrir", lambda m: llamadas.append(m.pk) or [1, 2])
    post_accion(client, Historia, "reprocesar", list(Historia.objects.all()))
    post_accion(client, Medio, "buscar_notas", list(Medio.objects.all()))
    assert len(llamadas) == 2


def test_sin_login_redirige(client):
    assert client.get(reverse("admin:index")).status_code == 302
