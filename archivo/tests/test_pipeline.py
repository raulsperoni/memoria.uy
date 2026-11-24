from datetime import timedelta

import pytest
from django.utils import timezone

from archivo import pipeline
from archivo.llm import FakeProcesador, set_procesador
from archivo.models import Cambio, Decision, Fuente, Hecho, Historia, Medio, Proposicion, Snapshot
from archivo.providers.decide import FakeDecider, set_decider
from archivo.providers.embed import FakeEmbedder, set_embedder
from archivo.providers.extract import FakeExtractor, set_extractor

CUERPO = (
    "<html><head><title>{t}</title></head><body><article><h1>{t}</h1>"
    + "<p>{p}</p>" * 6
    + "</article></body></html>"
)


def html(titulo, parrafo):
    return CUERPO.format(t=titulo, p=parrafo)


@pytest.fixture
def fakes(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path))
    ext = FakeExtractor()
    dec = FakeDecider()
    set_extractor(ext)
    set_decider(dec)
    set_embedder(FakeEmbedder())
    set_procesador(FakeProcesador())
    monkeypatch.setattr(pipeline, "comprobar_publicada", lambda url: 200)
    yield ext, dec
    set_extractor(None)
    set_decider(None)
    set_embedder(None)
    set_procesador(None)


@pytest.fixture
def medios(db):
    a = Medio.objects.create(
        nombre="Diario A", slug="a", dominio="a.uy", secciones_excluidas=["/deportes"]
    )
    b = Medio.objects.create(nombre="Diario B", slug="b", dominio="b.uy")
    return a, b


TEXTO_PRAXIS = (
    "El secretario de Presidencia Alejandro Sánchez se reunió con ediles del "
    "Frente Amplio de Colonia por el acuerdo con la empresa Praxis y el "
    "desarrollo urbanístico en Colonia del Sacramento. "
)


def nueva(medio, path, titulo="Sánchez se reunió con ediles por Praxis en Colonia"):
    return Fuente.objects.create(
        medio=medio,
        url=f"https://{medio.dominio}{path}",
        titulo=titulo,
        publicada_en=timezone.now(),
    )


def test_filtro_descarta_seccion_y_antiguas(fakes, medios):
    a, _ = medios
    f1 = nueva(a, "/deportes/clasico")
    f2 = nueva(a, "/politica/vieja")
    f2.publicada_en = timezone.now() - timedelta(days=5)
    f2.save()
    assert pipeline.filtrar(f1) is False
    assert pipeline.filtrar(f2) is False
    f1.refresh_from_db()
    assert f1.estado == "descartada" and "sección" in f1.motivo_descarte


def test_filtro_usa_decision_tipada_y_cachea(fakes, medios):
    _, dec = fakes
    a, _ = medios
    dec.respuestas["interes_publico"] = 0.2
    f = nueva(a, "/politica/x")
    f.seccion = "Política"
    assert pipeline.filtrar(f) is False
    assert Decision.objects.filter(pregunta="interes_publico").count() == 1
    f2 = nueva(a, "/politica/y")  # mismo título/bajada/sección → cache
    f2.seccion = "Política"
    pipeline.filtrar(f2)
    assert len([c for c in dec.llamadas if c[0] == "interes_publico"]) == 1


def test_extraer_guarda_snapshot_y_respeta_cupo(fakes, medios, monkeypatch):
    ext, _ = fakes
    a, _ = medios
    f = nueva(a, "/politica/praxis")
    ext.paginas[f.url] = (200, html(f.titulo, TEXTO_PRAXIS))
    assert pipeline.extraer(f) is True
    f.refresh_from_db()
    assert f.estado == "extraida"
    assert "Praxis" in f.texto
    assert f.ultimo_snapshot and f.ultimo_snapshot.storage_key.startswith("snapshots/")

    monkeypatch.setenv("MAX_EXTRACCIONES_DIA", "1")
    f2 = nueva(a, "/politica/otra")
    ext.paginas[f2.url] = (200, html("Otra", TEXTO_PRAXIS))
    assert pipeline.extraer(f2) is False


def test_extraer_404_es_error_permanente(fakes, medios):
    a, _ = medios
    f = nueva(a, "/politica/no-existe")
    assert pipeline.extraer(f) is False
    f.refresh_from_db()
    assert f.estado == "error"


def _extraida(ext, medio, path, titulo, texto):
    f = nueva(medio, path, titulo)
    ext.paginas[f.url] = (200, html(titulo, texto))
    pipeline.extraer(f)
    f.refresh_from_db()
    return f


def test_agrupar_misma_historia_entre_medios(fakes, medios):
    ext, _ = fakes
    a, b = medios
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis en Colonia", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Sánchez y ediles de Colonia hablaron de Praxis", TEXTO_PRAXIS)
    f3 = _extraida(
        ext, b, "/p/3", "Lluvias récord en Rocha",
        "Las lluvias en la laguna de Rocha afectaron al sapito de Darwin según científicos. " * 3,
    )
    h1 = pipeline.agrupar(f1)
    h2 = pipeline.agrupar(f2)
    h3 = pipeline.agrupar(f3)
    assert h1.pk == h2.pk
    assert h3.pk != h1.pk
    h1.refresh_from_db()
    assert h1.n_medios == 2


def test_procesar_historia_crea_hechos_y_proposiciones(fakes, medios):
    ext, dec = fakes
    a, b = medios
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Sánchez y ediles hablaron de Praxis", TEXTO_PRAXIS)
    h = pipeline.agrupar(f1)
    pipeline.agrupar(f2)
    h.refresh_from_db()

    assert pipeline.procesar_historia(h) is True
    h.refresh_from_db()
    assert h.slug and h.titulo
    assert Hecho.objects.filter(historia=h).count() == 2
    assert Proposicion.objects.filter(historia=h, estado="publicada").count() == 1
    assert set(Fuente.objects.filter(historia=h).values_list("estado", flat=True)) == {"procesada"}


def test_verificacion_borra_hechos_sin_fuente_fiel(fakes, medios):
    ext, dec = fakes
    a, b = medios
    dec.respuestas["fuente_respalda"] = 0.1
    dec.respuestas["calidad_proposicion"] = 0.2
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Sánchez y ediles hablaron de Praxis", TEXTO_PRAXIS)
    h = pipeline.agrupar(f1)
    pipeline.agrupar(f2)
    h.refresh_from_db()
    pipeline.procesar_historia(h)
    assert Hecho.objects.filter(historia=h).count() == 0
    assert Proposicion.objects.get(historia=h).estado == "descartada"


def test_historia_de_un_medio_poco_relevante_no_se_procesa(fakes, medios):
    ext, dec = fakes
    a, _ = medios
    dec.respuestas["vale_historia"] = 0.0
    f = _extraida(ext, a, "/p/1", "Expo pesca este sábado", "La expo pesca se hace en el dique Mauá este sábado. " * 5)
    h = pipeline.agrupar(f)
    h.refresh_from_db()
    assert pipeline.procesar_historia(h) is False
    assert not Hecho.objects.filter(historia=h).exists()


def test_recrawl_detecta_cambio_de_titulo(fakes, medios):
    ext, dec = fakes
    a, b = medios
    f = _extraida(ext, a, "/p/1", "Ministro renuncia tras escándalo", TEXTO_PRAXIS)
    ext.paginas[f.url] = (200, html("Ministro analiza su continuidad", TEXTO_PRAXIS))
    dec.respuestas["cambia_sentido"] = 0.95
    cambio = pipeline.recrawl(f)
    assert cambio is not None
    assert cambio.tipo == "titulo"
    assert cambio.cambia_sentido == 0.95
    assert "Ministro analiza" in cambio.resumen
    f.refresh_from_db()
    assert f.snapshots.count() == 2


def test_recrawl_sin_cambios_no_crea_cambio(fakes, medios):
    ext, _ = fakes
    a, _ = medios
    f = _extraida(ext, a, "/p/1", "Sin cambios", TEXTO_PRAXIS)
    assert pipeline.recrawl(f) is None
    assert not Cambio.objects.exists()


def test_recrawl_detecta_despublicada(fakes, medios, monkeypatch):
    ext, _ = fakes
    a, _ = medios
    f = _extraida(ext, a, "/p/1", "Nota borrada", TEXTO_PRAXIS)
    monkeypatch.setattr(pipeline, "comprobar_publicada", lambda url: 404)
    cambio = pipeline.recrawl(f)
    assert cambio.tipo == "despublicada"
    f.refresh_from_db()
    assert f.estado == "despublicada"


def test_programar_recrawls_top(fakes, medios):
    ext, _ = fakes
    a, b = medios
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Sánchez y ediles hablaron de Praxis", TEXTO_PRAXIS)
    h = pipeline.agrupar(f1)
    pipeline.agrupar(f2)
    h.refresh_from_db()
    pipeline.procesar_historia(h)
    assert pipeline.programar_recrawls() == 2
    assert Fuente.objects.filter(proximo_recrawl__isnull=False).count() == 2


def test_cerrar_historias(db):
    h = Historia.objects.create()
    Historia.objects.filter(pk=h.pk).update(ultima_fuente_en=timezone.now() - timedelta(days=4))
    assert pipeline.cerrar_historias() == 1


def test_verificacion_agrega_otras_fuentes_que_respaldan(fakes, medios):
    ext, dec = fakes
    a, b = medios
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Sánchez y ediles hablaron de Praxis", TEXTO_PRAXIS)
    h = pipeline.agrupar(f1)
    pipeline.agrupar(f2)
    h.refresh_from_db()
    # FakeProcesador atribuye cada hecho a una sola fuente.
    pipeline.procesar_historia(h)
    for hecho in Hecho.objects.filter(historia=h):
        assert hecho.fuentes.count() == 2


def test_resumen_no_fiel_se_rearma_con_hechos(fakes, medios):
    ext, dec = fakes
    a, b = medios
    dec.respuestas["resumen_fiel"] = 0.1
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Sánchez y ediles hablaron de Praxis", TEXTO_PRAXIS)
    h = pipeline.agrupar(f1)
    pipeline.agrupar(f2)
    h.refresh_from_db()
    pipeline.procesar_historia(h)
    h.refresh_from_db()
    primer = Hecho.objects.filter(historia=h).order_by("orden").first()
    assert h.resumen.startswith(primer.texto)


def test_fusionar_duplicadas(fakes, medios):
    ext, dec = fakes
    a, b = medios
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Lluvias récord en Rocha", "Las lluvias en Rocha afectaron al sapito de Darwin. " * 5)
    h1 = pipeline.agrupar(f1)
    h2 = pipeline.agrupar(f2)
    assert h1.pk != h2.pk
    # Simulamos que en realidad son el mismo hecho y que los centroides están en zona de duda.
    Historia.objects.filter(pk=h2.pk).update(centroide=h1.centroide)
    dec.respuestas["mismo_hecho"] = 0.9
    assert pipeline.fusionar_duplicadas() == 1
    assert not Historia.objects.filter(pk=h2.pk).exists()
    h1.refresh_from_db()
    assert h1.n_medios == 2 and h1.fuentes.count() == 2


def test_no_fusiona_si_hay_votos(fakes, medios):
    from juego.models import VotoProposicion

    ext, dec = fakes
    a, b = medios
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Lluvias récord en Rocha", "Las lluvias en Rocha afectaron al sapito de Darwin. " * 5)
    h1 = pipeline.agrupar(f1)
    h2 = pipeline.agrupar(f2)
    h2.refresh_from_db()
    pipeline.procesar_historia(h2)
    VotoProposicion.objects.create(proposicion=h2.proposiciones.first(), opinion="acuerdo", session_key="x")
    Historia.objects.filter(pk=h2.pk).update(centroide=h1.centroide)
    dec.respuestas["mismo_hecho"] = 0.9
    assert pipeline.fusionar_duplicadas() == 0


def _historia_procesada(ext, medios):
    a, b = medios
    f1 = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles por Praxis", TEXTO_PRAXIS)
    f2 = _extraida(ext, b, "/p/2", "Sánchez y ediles hablaron de Praxis", TEXTO_PRAXIS)
    h = pipeline.agrupar(f1)
    pipeline.agrupar(f2)
    h.refresh_from_db()
    assert pipeline.procesar_historia(h)
    return h


def test_reprocesar_no_acumula_proposiciones(fakes, medios):
    ext, dec = fakes
    h = _historia_procesada(ext, medios)
    for _ in range(3):
        h.fuentes.update(estado="extraida")
        pipeline.procesar_historia(h)
    assert h.proposiciones.count() == 1


def test_reprocesar_conserva_proposiciones_votadas_y_las_pasa_al_llm(fakes, medios):
    from juego.models import VotoProposicion

    ext, dec = fakes
    h = _historia_procesada(ext, medios)
    votada = h.proposiciones.get()
    VotoProposicion.objects.create(proposicion=votada, opinion="acuerdo", session_key="x")
    dec.respuestas["misma_proposicion"] = 0.1
    h.fuentes.update(estado="extraida")
    pipeline.procesar_historia(h)
    assert Proposicion.objects.filter(pk=votada.pk, estado="publicada").exists()
    assert h.proposiciones.count() == 2
    from archivo.llm import get_procesador

    assert get_procesador().proposiciones_existentes == [votada.texto]


def test_jev_descarta_proposicion_repetida(fakes, medios):
    from juego.models import VotoProposicion

    ext, dec = fakes
    h = _historia_procesada(ext, medios)
    VotoProposicion.objects.create(proposicion=h.proposiciones.get(), opinion="acuerdo", session_key="x")
    dec.respuestas["misma_proposicion"] = 0.9
    h.fuentes.update(estado="extraida")
    pipeline.procesar_historia(h)
    assert h.proposiciones.filter(estado="publicada").count() == 1
    assert h.proposiciones.filter(estado="descartada").count() == 1


def test_limpiar_proposiciones(fakes, medios):
    from django.core.management import call_command
    from juego.models import VotoProposicion

    ext, dec = fakes
    h = _historia_procesada(ext, medios)
    votada = h.proposiciones.get()
    viejas = [
        Proposicion.objects.create(historia=h, texto=f"Variante {i}", estado="publicada")
        for i in range(2)
    ]
    VotoProposicion.objects.create(proposicion=votada, opinion="acuerdo", session_key="x")
    dec.respuestas["misma_proposicion"] = 0.9
    call_command("limpiar_proposiciones")
    assert h.proposiciones.filter(estado="publicada").count() == 3
    call_command("limpiar_proposiciones", "--aplicar")
    assert list(h.proposiciones.filter(estado="publicada")) == [votada]
    assert all(Proposicion.objects.get(pk=p.pk).estado == "descartada" for p in viejas)


TEXTO_LARGO = " ".join(
    f"Párrafo {i}: el Ministerio de Ambiente recibió el informe técnico sobre el aeropuerto de Rocha." for i in range(30)
)


def test_recrawl_recortado_por_muro_de_pago_no_es_cambio(fakes, medios):
    ext, _ = fakes
    a, _ = medios
    f = _extraida(ext, a, "/p/1", "Advertencias sobre el aeropuerto en Rocha", TEXTO_LARGO)
    texto = f.texto
    ext.paginas[f.url] = (200, html("Advertencias sobre el aeropuerto en Rocha", TEXTO_LARGO[:300] + "…"))
    assert pipeline.recrawl(f) is None
    assert not Cambio.objects.exists()
    f.refresh_from_db()
    assert f.texto == texto and f.snapshots.count() == 1


def test_recrawl_que_completa_una_captura_recortada_no_es_cambio(fakes, medios):
    ext, _ = fakes
    a, _ = medios
    f = _extraida(ext, a, "/p/1", "Advertencias sobre el aeropuerto en Rocha", TEXTO_LARGO[:400])
    ext.paginas[f.url] = (200, html("Advertencias sobre el aeropuerto en Rocha", TEXTO_LARGO))
    assert pipeline.recrawl(f) is None
    f.refresh_from_db()
    assert len(f.texto) > 1000 and f.snapshots.count() == 2


def test_recrawl_que_solo_cambia_titulares_de_otras_notas_no_es_cambio(fakes, medios):
    ext, _ = fakes
    a, _ = medios
    otra1 = "El PIT-CNT reconoce la derrota en el BPS y la enmarca en una campaña de deslegitimación"
    otra2 = "Intendente de Montevideo defendió decisión de mantener el valor de patentes"
    for i, t in enumerate((otra1, otra2)):
        Fuente.objects.create(medio=a, url=f"https://a.uy/otra/{i}", titulo=t)
    f = _extraida(ext, a, "/p/1", "Ministro de Turismo destacó la conectividad aérea", TEXTO_PRAXIS + " " + otra1[:60])
    ext.paginas[f.url] = (200, html("Ministro de Turismo destacó la conectividad aérea", TEXTO_PRAXIS + " " + otra2))
    assert pipeline.recrawl(f) is None
    assert not Cambio.objects.exists()


def test_recrawl_detecta_edicion_real_del_cuerpo(fakes, medios):
    ext, dec = fakes
    a, _ = medios
    f = _extraida(ext, a, "/p/1", "Sánchez se reunió con ediles", TEXTO_PRAXIS)
    ext.paginas[f.url] = (200, html("Sánchez se reunió con ediles", TEXTO_PRAXIS.replace("Colonia del Sacramento", "Nueva Helvecia y Carmelo")))
    cambio = pipeline.recrawl(f)
    assert cambio is not None and cambio.tipo == "cuerpo"


def test_revisar_cambios_borra_recortes_y_restaura_el_texto(fakes, medios):
    from django.core.management import call_command

    ext, _ = fakes
    a, _ = medios
    f = _extraida(ext, a, "/p/1", "Advertencias sobre el aeropuerto en Rocha", TEXTO_LARGO)
    antes = f.ultimo_snapshot
    despues = Snapshot.objects.create(fuente=f, storage_key="x", contenido_hash="x", proveedor="fake")
    corto = TEXTO_LARGO[:300] + "…"
    c = Cambio.objects.create(
        fuente=f, antes=antes, despues=despues, tipo="cuerpo", diff=pipeline._diff(TEXTO_LARGO, corto)
    )
    Fuente.objects.filter(pk=f.pk).update(texto=corto, ultimo_snapshot=despues)
    call_command("revisar_cambios")
    assert Cambio.objects.filter(pk=c.pk).exists()
    call_command("revisar_cambios", "--aplicar")
    assert not Cambio.objects.filter(pk=c.pk).exists()
    f.refresh_from_db()
    assert f.ultimo_snapshot_id == antes.pk and len(f.texto) > 1000


def test_recrawl_cortado_con_puntos_suspensivos_es_recorte(fakes, medios):
    ext, _ = fakes
    a, _ = medios
    f = _extraida(ext, a, "/p/1", "Advertencias sobre el aeropuerto en Rocha", TEXTO_LARGO)
    ext.paginas[f.url] = (200, html("Advertencias sobre el aeropuerto en Rocha", TEXTO_LARGO[: int(len(TEXTO_LARGO) * 0.7)] + "…"))
    assert pipeline.recrawl(f) is None
    assert not Cambio.objects.exists()
