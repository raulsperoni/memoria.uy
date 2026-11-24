import pytest
from django.urls import reverse
from django.utils import timezone

from archivo import tonos
from archivo.models import Fuente, Hecho, Historia, Medio, Tono, UsoProveedor
from archivo.providers.decide import FakeDecider, set_decider
from archivo.tonos import FakeTonador, calcular_tonos, set_tonador, tonos_de_fuente
from core.models import Entidad

TEXTO = (
    "El secretario de Presidencia Alejandro Sánchez fue citado por la Fiscalía. "
    "La oposición dijo que Sánchez «mintió al Parlamento». "
    "El intendente Mario Bergara no hizo comentarios."
)


@pytest.fixture
def fakes():
    tonador = FakeTonador()
    dec = FakeDecider()
    set_tonador(tonador)
    set_decider(dec)
    yield tonador, dec
    set_tonador(None)
    set_decider(None)


@pytest.fixture
def nota(db):
    medio = Medio.objects.create(nombre="Diario A", slug="a", dominio="a.uy")
    h = Historia.objects.create(titulo="Sánchez citado", slug="sanchez-citado", procesada_en=timezone.now())
    f = Fuente.objects.create(
        medio=medio, url="https://a.uy/1", titulo="Citan a Sánchez", texto=TEXTO,
        estado="procesada", historia=h, publicada_en=timezone.now(),
    )
    hecho = Hecho.objects.create(historia=h, texto="Sánchez fue citado")
    sanchez = Entidad.objects.create(nombre="Alejandro Sánchez", tipo="persona")
    orsi = Entidad.objects.create(nombre="Yamandú Orsi", tipo="persona")
    fiscalia = Entidad.objects.create(nombre="Fiscalía", tipo="organizacion")
    hecho.entidades.set([sanchez, orsi, fiscalia])
    return f, sanchez, orsi


def test_solo_personas_que_la_nota_nombra(fakes, nota):
    tonador, _ = fakes
    f, sanchez, orsi = nota
    assert tonos_de_fuente(f) == 1
    assert tonador.llamadas == [(f.pk, ["Alejandro Sánchez"])]
    t = Tono.objects.get()
    assert t.entidad == sanchez and t.valencia == 0 and t.verificado == 0.9
    f.refresh_from_db()
    assert f.tonos_en is not None


def test_nombrada_por_apellido():
    e = Entidad(nombre="Alejandro Sánchez", tipo="persona")
    assert tonos.nombrada(e, tonos._norm("dijo que sanchez mintio"))
    assert not tonos.nombrada(Entidad(nombre="Ana Paz"), tonos._norm("hubo paz social"))


def test_descarta_cita_inventada_y_no_verificada(fakes, nota):
    tonador, dec = fakes
    f, sanchez, _ = nota
    tonador.salida = {"tonos": [{"persona": "Alejandro Sánchez", "valencia": -2, "cita": "renunció ayer"}]}
    assert tonos_de_fuente(f) == 0  # la cita no está en la nota
    assert dec.llamadas == []

    Fuente.objects.filter(pk=f.pk).update(tonos_en=None)
    tonador.salida = {"tonos": [{"persona": "Alejandro Sánchez", "valencia": 2, "cita": "«mintió al Parlamento»"}]}
    dec.respuestas["tono_respaldado"] = 0.1
    assert tonos_de_fuente(f) == 0
    assert dec.llamadas[0][0] == "tono_respaldado"
    assert dec.llamadas[0][1]["valencia"] == "Muy bien parada"


def test_pendientes_y_cupo(fakes, nota, monkeypatch):
    f, *_ = nota
    monkeypatch.setenv("MAX_TONOS_DIA", "0")
    assert "llamadas=0" in calcular_tonos()
    monkeypatch.setenv("MAX_TONOS_DIA", "500")
    assert "llamadas=1 tonos=1" in calcular_tonos()
    assert UsoProveedor.objects.get(operacion="tono").cantidad == 1
    assert "llamadas=0" in calcular_tonos()  # ya no está pendiente
    # Reprocesar la historia la vuelve a poner en la cola, pero no repite pares.
    Historia.objects.filter(pk=f.historia_id).update(procesada_en=timezone.now())
    assert "llamadas=0 tonos=0" in calcular_tonos()
    assert Tono.objects.count() == 1


def test_pagina_de_persona_muestra_tono(client, fakes, nota):
    f, sanchez, _ = nota
    tonos_de_fuente(f)
    Tono.objects.update(valencia=-1, razon="La Fiscalía lo cita")
    html = client.get(reverse("archivo:entidad-slug", args=[sanchez.pk, "alejandro-sanchez"])).content.decode()
    assert "Cómo la deja cada medio" in html
    assert "Diario A" in html and ("-1,0" in html or "-1.0" in html)
    assert "(pocas)" in html and "La Fiscalía lo cita" in html


def test_nombrada_con_puntuacion_y_apellido_compuesto():
    sanchez = Entidad(nombre="Alejandro Sánchez", tipo="persona")
    assert tonos.nombrada(sanchez, tonos._norm("La oposición criticó a Sánchez, que no respondió."))
    assert tonos.nombrada(sanchez, tonos._norm("(Sánchez)"))
    lacalle = Entidad(nombre="Luis Lacalle Pou", tipo="persona")
    assert tonos.nombrada(lacalle, tonos._norm("Lacalle Pou, en cambio, habló."))


def test_cita_del_titulo_vale_y_cita_corta_no(fakes, nota):
    tonador, dec = fakes
    f, sanchez, _ = nota
    tonador.salida = {"tonos": [{"persona": "Alejandro Sánchez", "valencia": -1, "cita": "Sánchez"}]}
    assert tonos_de_fuente(f) == 0  # una sola palabra no justifica nada
    assert dec.llamadas == []

    Fuente.objects.filter(pk=f.pk).update(tonos_en=None)
    tonador.salida = {"tonos": [{"persona": "Alejandro Sánchez", "valencia": -1, "cita": "Citan a Sánchez"}]}
    assert tonos_de_fuente(f) == 1
    assert dec.llamadas[0][1]["nota"].startswith("Citan a Sánchez")


def test_un_tono_mal_formado_no_tira_los_demas(fakes, nota):
    tonador, _ = fakes
    f, *_ = nota
    tonador.salida = {
        "tonos": [
            {"persona": "Yamandú Orsi", "valencia": 3, "cita": "x"},
            {"persona": "Alejandro Sánchez", "valencia": -2, "cita": "«mintió al Parlamento»"},
        ]
    }
    assert tonos_de_fuente(f) == 1
    assert Tono.objects.get().valencia == -2


def test_llamadas_fallidas_cuentan_para_el_cupo(fakes, nota):
    tonador, _ = fakes
    f, *_ = nota

    def falla(fuente, personas):
        tonador.intentos = 3
        raise RuntimeError("todos los modelos fallaron")

    tonador.salida = falla
    assert "llamadas=3 tonos=0" in calcular_tonos()
    assert UsoProveedor.objects.get(operacion="tono").cantidad == 3


def test_no_toma_una_nota_que_ya_tomo_otra_corrida(fakes, nota):
    tonador, _ = fakes
    f, *_ = nota
    assert tonos.tomar(f)
    assert not tonos.tomar(f)  # el objeto en memoria quedó viejo: otra corrida ya la tomó
    f.refresh_from_db()
    assert "llamadas=0" in calcular_tonos()  # ya no figura como pendiente
    assert tonador.llamadas == []


def test_corrida_del_tick_limitada(fakes, nota, monkeypatch):
    f, *_ = nota
    f2 = Fuente.objects.create(
        medio=f.medio, url="https://a.uy/2", titulo="Otra sobre Sánchez", texto=TEXTO,
        estado="procesada", historia=f.historia, publicada_en=timezone.now(),
    )
    monkeypatch.setenv("TONOS_POR_CORRIDA", "1")
    from archivo.tasks import tonos_pendientes

    assert "llamadas=1" in tonos_pendientes()
    assert Fuente.objects.filter(pk__in=[f.pk, f2.pk], tonos_en__isnull=True).count() == 1
