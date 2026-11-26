from io import StringIO

from django.core.management import call_command

from archivo import pipeline
from archivo.limpieza import detectar, limpiar
from archivo.models import Cambio, Decision, Fuente, Historia

from .test_pipeline import fakes, medios, nueva  # noqa: F401

AVISO = (
    "En Búsqueda y Galería nos estamos renovando. Para mejorar tu experiencia te pedimos "
    "que actualices tus datos. Una vez que completes los datos, tu plan tendrá un precio promocional:"
)
NOTAS = [
    ("Montecon reunió a clientes y socios en el puerto",
     "La empresa Montecon celebró su encuentro anual con clientes portuarios y operadores logísticos en Carrasco."),
    ("UTE emitirá títulos para financiar Baygorria",
     "La empresa eléctrica estatal colocará obligaciones negociables en la bolsa para la represa hidroeléctrica."),
    ("Radios públicas no renuevan contratos",
     "El sindicato de trabajadores de medios públicos convocó una asamblea tras la baja de programas radiales."),
]


def _pagina(titulo, cuerpo, aviso=True):
    parrafos = "".join(f"<p>{cuerpo} Párrafo número {k} de la nota.</p>" for k in range(6))
    return (
        f"<html><head><title>{titulo}</title></head><body><article>"
        + (f"<p>{AVISO}</p>" if aviso else "") + parrafos + "</article></body></html>"
    )


def _extraer(ext, medio, i):
    titulo, cuerpo = NOTAS[i]
    f = nueva(medio, f"/n/{i}", titulo=titulo)
    ext.paginas[f.url] = (200, _pagina(titulo, cuerpo))
    assert pipeline.extraer(f, respetar_cupo=False)
    f.refresh_from_db()
    return f


def test_detecta_lineas_de_historias_distintas(medios):
    a, _ = medios
    for i in range(3):
        h = Historia.objects.create(titulo=f"h{i}")
        Fuente.objects.create(medio=a, url=f"https://a.uy/{i}", historia=h, texto=f"{AVISO}\nNota número {i} con su propio texto largo.")
    assert detectar(a) == [AVISO]


def test_no_saca_lo_que_se_repite_dentro_de_una_historia(medios):
    a, _ = medios
    h = Historia.objects.create(titulo="h")
    frase = "La ministra dijo que el plan empieza en marzo en todo el país."
    for i in range(3):
        Fuente.objects.create(medio=a, url=f"https://a.uy/{i}", historia=h, texto=f"{frase}\nSeguimiento {i}.")
    assert detectar(a) == []
    assert limpiar(f"{frase}\notra", set()) == f"{frase}\notra"


def test_notas_sin_relacion_con_el_mismo_aviso_no_se_agrupan(fakes, medios):
    ext, _ = fakes
    a, _ = medios
    # Se extraen antes de agrupar: las dos primeras se guardan con el aviso
    # (todavía no se repetía) y se limpian al agrupar.
    fuentes = [_extraer(ext, a, i) for i in range(3)]
    for f in Fuente.objects.filter(pk__in=[f.pk for f in fuentes]).order_by("pk"):
        pipeline.agrupar(f)
    assert len({f.historia_id for f in Fuente.objects.filter(pk__in=[f.pk for f in fuentes])}) == 3
    a.refresh_from_db()
    assert AVISO in a.lineas_repetidas
    assert all(AVISO not in f.texto for f in Fuente.objects.filter(medio=a))


def test_texto_para_embedding_saltea_lineas_cortas(medios):
    a, _ = medios
    f = Fuente(medio=a, titulo="T", texto="¡Hola\nEl texto de verdad de la nota, con más de cuarenta letras.")
    assert pipeline._texto_para_embedding(f) == "T\nEl texto de verdad de la nota, con más de cuarenta letras."


def test_recrawl_no_toma_el_aviso_como_edicion(fakes, medios):
    ext, _ = fakes
    a, _ = medios
    a.lineas_repetidas = [AVISO]
    a.save()
    titulo, cuerpo = NOTAS[0]
    f = nueva(a, "/n/0", titulo=titulo)
    ext.paginas[f.url] = (200, _pagina(titulo, cuerpo, aviso=False))
    assert pipeline.extraer(f, respetar_cupo=False)
    f.refresh_from_db()
    # Texto guardado antes de este arreglo: con el aviso adentro.
    Fuente.objects.filter(pk=f.pk).update(texto=f"{AVISO}\n{f.texto}")
    f.refresh_from_db()
    ext.paginas[f.url] = (200, _pagina(titulo, cuerpo))
    assert pipeline.recrawl(f) is None
    assert not Cambio.objects.exists()
    f.refresh_from_db()
    assert AVISO not in f.texto


def test_limpiar_textos_reagrupa(fakes, medios):
    _, dec = fakes
    # Jev: solo la nota de IA es el mismo hecho que la de la historia.
    dec.respuestas["mismo_hecho"] = lambda e: 0.9 if "inteligencia" in e["B"]["titulo"] else 0.1
    a, b = medios
    h = Historia.objects.create(titulo="Curso de inteligencia artificial", estado="abierta")
    emb = pipeline.get_embedder()
    buena = Fuente.objects.create(
        medio=b, url="https://b.uy/ia", historia=h, estado="procesada", titulo="Curso de inteligencia artificial",
        texto="La vicepresidenta propuso un curso de operador de inteligencia artificial para toda la población.",
        publicada_en=pipeline.timezone.now(),
    )
    pegadas = []
    # Cinco notas sin relación pegadas por el aviso (como en producción).
    for i, (titulo, cuerpo) in enumerate(NOTAS + NOTAS[:2]):
        f = Fuente.objects.create(
            medio=a, url=f"https://a.uy/{i}", historia=h, estado="procesada", titulo=titulo,
            texto=f"{AVISO}\n{cuerpo}", publicada_en=pipeline.timezone.now(),
        )
        pegadas.append(f)
    for f in [buena, *pegadas]:
        f.embedding = emb.embed([pipeline._texto_para_embedding(f)])[0]
        f.save(update_fields=["embedding"])

    out = StringIO()
    call_command("limpiar_textos", stdout=out)
    assert "5 notas con ellas" in out.getvalue() and "no se guardó nada" in out.getvalue()
    # La vista previa no deja nada: ni textos, ni líneas del medio, ni caché de Jev.
    assert all(AVISO in x.texto for x in Fuente.objects.filter(medio=a))
    a.refresh_from_db()
    assert a.lineas_repetidas == [] and not Decision.objects.exists()

    call_command("limpiar_textos", "--aplicar", stdout=StringIO())
    assert all(AVISO not in x.texto for x in Fuente.objects.filter(medio=a))
    assert list(h.fuentes.all()) == [buena]
    h.refresh_from_db()
    assert h.n_embeddings == 1
    assert Fuente.objects.get(pk=buena.pk).estado == "extraida"  # se reprocesa
