from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from archivo.entidades_wikidata import (
    elegir_candidato,
    enriquecer,
    enriquecer_pendientes,
    entidades_pendientes,
    fijar,
    mismo_nombre,
)
from archivo.models import FichaEntidad, Hecho, Historia, UsoProveedor
from archivo.providers.decide import FakeDecider, set_decider
from archivo.providers.wikidata import Datos, FakeEnriquecedor, set_enriquecedor
from core.models import Entidad

ORSI = Datos(
    qid="Q1", etiqueta="Yamandú Orsi", nombres=["Yamandú Orsi", "Orsi"],
    descripcion="político uruguayo", cargo="Presidente de Uruguay", organizacion="Frente Amplio",
    wikipedia_url="https://es.wikipedia.org/wiki/Yamand%C3%BA_Orsi", resumen="Es el presidente.",
    foto_url="https://upload.wikimedia.org/x/320px-Orsi.jpg", foto_pagina="https://commons.wikimedia.org/wiki/File:Orsi.jpg",
    foto_autor="Fulano", foto_licencia="CC BY 2.0",
)
OTRO_ORSI = Datos(qid="Q2", etiqueta="Yamandú Orsi", nombres=["Yamandú Orsi"], descripcion="futbolista")


@pytest.fixture
def mundo():
    enr = FakeEnriquecedor([ORSI])
    dec = FakeDecider()
    set_enriquecedor(enr)
    set_decider(dec)
    yield enr, dec
    set_enriquecedor(None)
    set_decider(None)


def entidad(nombre="Yamandú Orsi", tipo="persona", hechos=2):
    e = Entidad.objects.create(nombre=nombre, tipo=tipo)
    h = Historia.objects.create(titulo=f"H {nombre}", slug=f"h-{e.pk}")
    for i in range(hechos):
        Hecho.objects.create(historia=h, texto=f"{nombre} hizo algo {i}").entidades.add(e)
    return e


@pytest.mark.django_db
def test_asocia_y_guarda_datos(mundo):
    e = entidad()
    assert enriquecer(e) == "asociada"
    f = e.ficha
    assert (f.qid, f.cargo, f.organizacion, f.foto_licencia) == ("Q1", "Presidente de Uruguay", "Frente Amplio", "CC BY 2.0")
    assert f.confianza == 0.9 and f.consultada_en


@pytest.mark.django_db
def test_decider_ve_los_hechos(mundo):
    _, dec = mundo
    e = entidad()
    elegir_candidato(e)
    pregunta, estado = dec.llamadas[0]
    assert pregunta == "misma_entidad"
    assert len(estado["hechos_donde_aparece"]) == 2 and estado["candidato"]["descripcion"] == "político uruguayo"


@pytest.mark.django_db
def test_sin_confianza_no_asocia(mundo):
    set_decider(FakeDecider(default=0.5))
    e = entidad()
    assert enriquecer(e) == "sin_candidato"
    assert e.ficha.qid == "" and e.ficha.confianza == 0.5


@pytest.mark.django_db
def test_homonimos_ambiguos_no_asocian(mundo):
    enr, _ = mundo
    enr.items["Q2"] = OTRO_ORSI
    e = entidad()
    assert enriquecer(e) == "sin_candidato"  # los dos con 0.9: sin ventaja


@pytest.mark.django_db
def test_homonimos_gana_el_que_encaja(mundo):
    enr, _ = mundo
    enr.items["Q2"] = OTRO_ORSI
    set_decider(FakeDecider({"misma_entidad": lambda s: 0.95 if "político" in s["candidato"]["descripcion"] else 0.1}))
    e = entidad()
    assert enriquecer(e) == "asociada" and e.ficha.qid == "Q1"


@pytest.mark.django_db
def test_nombre_distinto_no_es_candidato(mundo):
    e = Entidad.objects.create(nombre="Orsi Pérez Gómez", tipo="persona")
    assert not mismo_nombre(e, ORSI)
    assert elegir_candidato(e)[0] is None


def test_nombre_de_una_palabra_solo_exacto():
    # «Orsi» a secas es alias exacto; «Ana Orsi» no está en las palabras de la etiqueta
    assert mismo_nombre(Entidad(nombre="Orsi", tipo="persona"), ORSI)
    assert not mismo_nombre(Entidad(nombre="Ana Orsi", tipo="persona"), ORSI)
    assert mismo_nombre(Entidad(nombre="Yamandú Orsi", tipo="persona"), Datos(qid="Q9", nombres=["Yamandú Alberto Orsi"]))
    assert not mismo_nombre(Entidad(nombre="Orsi", tipo="organizacion"), Datos(qid="Q9", nombres=["Orsi y Cía"]))


@pytest.mark.django_db
def test_no_pisa_la_correccion_de_staff(mundo):
    enr, _ = mundo
    enr.items["Q7"] = Datos(qid="Q7", etiqueta="Otro", nombres=["Otro"], descripcion="otro")
    e = entidad()
    enriquecer(e)
    assert fijar(e, "q7") == "fijada"
    f = FichaEntidad.objects.get(entidad=e)
    assert (f.qid, f.fijada, f.confianza) == ("Q7", True, 1)
    FichaEntidad.objects.filter(pk=f.pk).update(consultada_en=timezone.now() - timedelta(days=60))
    assert enriquecer(e) == "refrescada"
    assert FichaEntidad.objects.get(entidad=e).qid == "Q7"
    assert ("buscar", "Yamandú Orsi") not in enr.llamadas[-3:]


@pytest.mark.django_db
def test_anulada_no_se_vuelve_a_buscar(mundo):
    enr, _ = mundo
    e = entidad()
    enriquecer(e)
    assert fijar(e, "") == "anulada"
    f = FichaEntidad.objects.get(entidad=e)
    assert f.qid == "" and f.fijada and not f.visible and f.cargo == ""
    enr.llamadas.clear()
    assert enriquecer(e) == "fijada_vacia" and enr.llamadas == []
    FichaEntidad.objects.filter(pk=f.pk).update(consultada_en=None)
    assert e not in list(entidades_pendientes())


@pytest.mark.django_db
def test_fijar_qid_inexistente(mundo):
    with pytest.raises(ValueError):
        fijar(entidad(), "Q999")


@pytest.mark.django_db
def test_item_que_ya_no_existe_limpia_la_ficha_automatica(mundo):
    enr, _ = mundo
    e = entidad()
    enriquecer(e)
    del enr.items["Q1"]
    assert enriquecer(e) == "perdida"
    f = FichaEntidad.objects.get(entidad=e)
    assert f.qid == "" and f.cargo == ""


@pytest.mark.django_db
def test_cola_ordena_por_hechos_y_nuevas_primero(mundo):
    poca = entidad("Ana Pocos", hechos=2)
    mucha = entidad("Beto Muchos", hechos=5)
    vieja = entidad("Carla Vieja", hechos=9)
    una = entidad("Dani Uno", hechos=1)  # bajo el mínimo
    entidad("Frente Amplio", "organizacion", hechos=3)
    FichaEntidad.objects.create(
        entidad=vieja, qid="Q5", consultada_en=timezone.now() - timedelta(days=31)
    )
    reciente = entidad("Eva Reciente", hechos=8)
    FichaEntidad.objects.create(entidad=reciente, qid="Q6", consultada_en=timezone.now())
    nombres = [e.nombre for e in entidades_pendientes()]
    assert nombres == ["Beto Muchos", "Frente Amplio", "Ana Pocos", "Carla Vieja"]
    assert una.nombre not in nombres and reciente.nombre not in nombres and poca.nombre in nombres and mucha


@pytest.mark.django_db
def test_sin_asociar_se_reintenta_a_los_90_dias(mundo):
    e = entidad()
    FichaEntidad.objects.create(entidad=e, consultada_en=timezone.now() - timedelta(days=60))
    assert e not in list(entidades_pendientes())
    FichaEntidad.objects.filter(entidad=e).update(consultada_en=timezone.now() - timedelta(days=91))
    assert e in list(entidades_pendientes())


@pytest.mark.django_db
def test_cupo_diario_y_por_corrida(mundo, monkeypatch):
    for i in range(4):
        entidad(f"Persona{i} Uno")
    monkeypatch.setenv("MAX_ENRIQUECIMIENTOS_DIA", "3")
    assert "entidades=2" in enriquecer_pendientes(limite=2)
    assert "entidades=1" in enriquecer_pendientes()  # queda 1 del cupo
    assert "entidades=0" in enriquecer_pendientes()
    assert UsoProveedor.objects.get(operacion="enriquecer").cantidad == 3


@pytest.mark.django_db
def test_errores_seguidos_cortan_la_corrida(mundo):
    enr, _ = mundo

    def falla(*a):
        raise RuntimeError("Wikidata caído")

    enr.buscar = falla
    for i in range(6):
        entidad(f"Persona{i} Uno")
    res = enriquecer_pendientes()
    assert "entidades=3" in res and "errores=3" in res
    assert FichaEntidad.objects.filter(consultada_en__isnull=False).count() == 0  # se reintenta en el próximo tick


@pytest.mark.django_db
def test_ficha_aparece_en_la_pagina(client, mundo):
    e = entidad()
    enriquecer(e)
    html = client.get(reverse("archivo:entidad-slug", args=[e.pk, "yamandu-orsi"])).content.decode()
    assert 'id="ficha"' in html and "Presidente de Uruguay" in html and "Frente Amplio" in html
    assert "CC BY 2.0" in html and "Fulano" in html and "https://www.wikidata.org/wiki/Q1" in html
    assert "es.wikipedia.org/wiki/Yamand" in html


@pytest.mark.django_db
def test_sin_ficha_o_sin_qid_no_muestra_nada(client, mundo):
    e = entidad()
    url = reverse("archivo:entidad-slug", args=[e.pk, "yamandu-orsi"])
    assert 'id="ficha"' not in client.get(url).content.decode()
    FichaEntidad.objects.create(entidad=e, descripcion="algo", consultada_en=timezone.now())
    assert 'id="ficha"' not in client.get(url).content.decode()


@pytest.mark.django_db
def test_ficha_sin_foto_ni_resumen(client, mundo):
    e = entidad("Frente Amplio", "organizacion")
    FichaEntidad.objects.create(entidad=e, qid="Q3", descripcion="partido político", consultada_en=timezone.now())
    html = client.get(reverse("archivo:entidad-slug", args=[e.pk, "frente-amplio"])).content.decode()
    assert "Partido político" in html and "<img" not in html.split('id="ficha"')[1].split("</aside>")[0]
