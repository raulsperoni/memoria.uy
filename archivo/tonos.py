"""
Tono de los medios hacia las personas: ¿cómo deja esta nota a esta persona?

Una llamada al LLM por nota, con todas las personas de su historia que la nota
nombra. Cada tono trae una cita literal; Jev verifica que la cita respalde la
valencia y si no, se descarta. Ver docs/decisiones/0013-tono-de-los-medios.md.

    tonos_de_fuente(fuente)   # calcula los que falten para una nota
    tonos_pendientes(limite)  # notas que necesitan tono (nuevas primero)

Proveedor intercambiable: LLMTonador (Haiku vía OpenRouter) o FakeTonador.
"""

from __future__ import annotations

import json
import logging
import os

from django.db.models import F, Q
from django.utils import timezone
from pydantic import BaseModel, Field, ValidationError

from core.models import Entidad, normalize_entity_name

from .llm import DEFAULT_MODELS
from .models import Fuente, Tono, UsoProveedor
from .providers.decide import decidir

logger = logging.getLogger(__name__)

MAX_CHARS = 6000
MAX_TONOS_DIA = lambda: int(os.environ.get("MAX_TONOS_DIA", 500))  # noqa: E731
UMBRAL_TONO = lambda: float(os.environ.get("UMBRAL_TONO", 0.5))  # noqa: E731

ETIQUETAS = dict(Tono.VALENCIAS)


class TonoOut(BaseModel):
    persona: str
    valencia: int = Field(ge=-2, le=2)
    cita: str = ""
    razon: str = ""


class TonosOut(BaseModel):
    tonos: list[TonoOut] = Field(default_factory=list)


SYSTEM = """Leés una nota de un medio uruguayo y, para cada persona de la lista,
decís cómo la deja parada la nota. Devolvés SOLO JSON:

{"tonos": [{"persona": str, "valencia": int, "cita": str, "razon": str}]}

- persona: el nombre exactamente como aparece en la lista.
- valencia: -2 muy mal parada, -1 mal parada, 0 neutra o mixta, 1 bien parada, 2 muy bien parada.
- cita: frase literal de la nota (≤ 200 caracteres) que mejor justifica la valencia.
- razon: por qué, en una oración (≤ 160 caracteres).

Reglas:
- Contá todo lo que la nota le hace a la persona: los hechos que relata, lo que
  dicen otros de ella y el tono. Una noticia mala para la persona (una
  imputación, una derrota, una crítica fuerte) es negativa aunque la nota esté
  contada con neutralidad.
- Si la nota solo la nombra al pasar, valencia 0.
- Omití a las personas que la nota no menciona.
- La cita tiene que estar textual en la nota.
"""


def construir_entrada(fuente, personas):
    lista = "\n".join(f"- {p.nombre}" for p in personas)
    return (
        f"Personas:\n{lista}\n\nNota de {fuente.medio.nombre} — {fuente.titulo}\n\n"
        + (fuente.texto or fuente.bajada)[:MAX_CHARS]
    )


class Tonador:
    nombre = "base"

    def tonos(self, fuente, personas) -> TonosOut:
        raise NotImplementedError


class LLMTonador(Tonador):
    def __init__(self, modelos=None):
        env = os.environ.get("TONOS_LLM_MODELS") or os.environ.get("ARCHIVO_LLM_MODELS")
        self.modelos = modelos or (env.split(",") if env else DEFAULT_MODELS)
        self.nombre = self.modelos[0]

    def tonos(self, fuente, personas):
        from litellm import completion

        entrada = construir_entrada(fuente, personas)
        ultimo_error = None
        for modelo in self.modelos:
            try:
                resp = completion(
                    model=modelo,
                    messages=[
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": entrada},
                    ],
                    response_format={"type": "json_object"},
                    extra_body={"reasoning": {"effort": "low"}},
                    timeout=90,
                )
                texto = resp.choices[0].message.content or ""
                data = json.loads(texto[texto.find("{") : texto.rfind("}") + 1])
                self.nombre = modelo
                return TonosOut.model_validate(data)
            except (ValidationError, json.JSONDecodeError, Exception) as e:  # noqa: B014
                logger.warning("Modelo %s falló calculando tonos: %s", modelo, e)
                ultimo_error = e
        raise RuntimeError(f"Todos los modelos fallaron: {ultimo_error}")


class FakeTonador(Tonador):
    """Devuelve `salida` o, por defecto, valencia 0 con la primera oración como cita."""

    nombre = "fake"

    def __init__(self, salida=None):
        self.salida = salida
        self.llamadas = []

    def tonos(self, fuente, personas):
        self.llamadas.append((fuente.pk, [p.nombre for p in personas]))
        if self.salida is not None:
            s = self.salida(fuente, personas) if callable(self.salida) else self.salida
            return TonosOut.model_validate(s) if isinstance(s, dict) else s
        cita = (fuente.texto or fuente.titulo)[:150]
        return TonosOut(tonos=[TonoOut(persona=p.nombre, valencia=0, cita=cita) for p in personas])


_override = None


def set_tonador(t):
    global _override
    _override = t


def get_tonador() -> Tonador:
    return _override or LLMTonador()


# ---------------------------------------------------------------------------


def _norm(texto):
    return " ".join(normalize_entity_name(texto).split())


def nombrada(persona, texto_norm):
    """¿La nota nombra a la persona? Nombre completo o apellido (≥ 4 letras)."""
    nombre = _norm(persona.nombre)
    if not nombre:
        return False
    if nombre in texto_norm:
        return True
    apellido = nombre.split()[-1]
    return len(nombre.split()) > 1 and len(apellido) >= 4 and f" {apellido} " in f" {texto_norm} "


def personas_de_fuente(fuente):
    """Personas de los hechos de la historia que esta nota nombra."""
    if not fuente.historia_id:
        return []
    personas = Entidad.objects.filter(
        tipo="persona", hechos__historia_id=fuente.historia_id
    ).distinct()
    texto = _norm(f"{fuente.titulo} {fuente.texto or fuente.bajada}")
    return [p for p in personas if nombrada(p, texto)]


def tonos_hoy():
    return sum(
        UsoProveedor.objects.filter(fecha=timezone.localdate(), operacion="tono").values_list(
            "cantidad", flat=True
        )
    )


def tonos_pendientes(desde=None):
    """Notas procesadas sin tono, o cuya historia se reprocesó después."""
    qs = Fuente.objects.filter(
        estado__in=["procesada", "despublicada"],
        historia__procesada_en__isnull=False,
    ).filter(Q(tonos_en__isnull=True) | Q(tonos_en__lt=F("historia__procesada_en")))
    if desde:
        qs = qs.filter(publicada_en__gte=desde)
    return qs.select_related("medio").order_by(F("publicada_en").desc(nulls_last=True))


def tonos_de_fuente(fuente) -> int:
    """Calcula los tonos que faltan para la nota. Devuelve cuántos guardó."""
    from .pipeline import registrar_uso

    ya = set(fuente.tonos.values_list("entidad_id", flat=True))
    personas = [p for p in personas_de_fuente(fuente) if p.pk not in ya]
    texto = fuente.texto or fuente.bajada
    if not personas or not texto:
        Fuente.objects.filter(pk=fuente.pk).update(tonos_en=timezone.now())
        return 0

    tonador = get_tonador()
    salida = tonador.tonos(fuente, personas)
    registrar_uso("llm", "tono")

    por_nombre = {_norm(p.nombre): p for p in personas}
    texto_norm = _norm(texto)
    guardados = 0
    for t in salida.tonos:
        persona = por_nombre.get(_norm(t.persona))
        cita = t.cita.strip().strip("«»\"“”")
        if not persona or not cita or _norm(cita) not in texto_norm:
            continue  # persona inventada o cita que no está en la nota
        verificado = decidir(
            "tono_respaldado",
            {
                "persona": persona.nombre,
                "valencia": ETIQUETAS[t.valencia],
                "cita": cita,
                "nota": texto[:4000],
            },
        )
        if verificado < UMBRAL_TONO():
            continue
        Tono.objects.update_or_create(
            fuente=fuente,
            entidad=persona,
            defaults={
                "valencia": t.valencia,
                "cita": cita[:400],
                "razon": t.razon[:300],
                "verificado": verificado,
                "modelo": tonador.nombre[:80],
            },
        )
        guardados += 1
    Fuente.objects.filter(pk=fuente.pk).update(tonos_en=timezone.now())
    return guardados


def calcular_tonos(limite=None, desde=None) -> str:
    """Procesa notas pendientes, nuevas primero, hasta el cupo diario
    (MAX_TONOS_DIA llamadas al LLM) o `limite` llamadas en esta corrida."""
    llamadas = guardados = 0
    for f in tonos_pendientes(desde).iterator():
        if tonos_hoy() >= MAX_TONOS_DIA() or (limite is not None and llamadas >= limite):
            break
        antes = tonos_hoy()
        try:
            guardados += tonos_de_fuente(f)
        except Exception:
            logger.exception("Tonos fallaron para %s", f.url)
            # No reintentar en cada tick: vuelve a la cola si la historia se reprocesa.
            Fuente.objects.filter(pk=f.pk).update(tonos_en=timezone.now())
        llamadas += max(tonos_hoy() - antes, 0)
    return f"llamadas={llamadas} tonos={guardados} hoy={tonos_hoy()}/{MAX_TONOS_DIA()}"


def resumen_por_medio(entidad, historias=None):
    """Tonos de una persona agrupados por medio, ordenados por cantidad."""
    qs = Tono.objects.filter(entidad=entidad).select_related("fuente__medio", "fuente__historia")
    if historias is not None:
        qs = qs.filter(fuente__historia__in=historias)
    medios = {}
    for t in qs:
        m = medios.setdefault(t.fuente.medio_id, {"medio": t.fuente.medio, "tonos": []})
        m["tonos"].append(t)
    filas = []
    for m in medios.values():
        vals = [t.valencia for t in m["tonos"]]
        prom = sum(vals) / len(vals)
        filas.append(
            {
                **m,
                "n": len(vals),
                "promedio": prom,
                "pos": (prom + 2) / 4 * 100,  # posición en la barra, 0–100 %
                "pocas": len(vals) < 3,
            }
        )
    filas.sort(key=lambda f: (-f["n"], f["medio"].nombre))
    return filas
