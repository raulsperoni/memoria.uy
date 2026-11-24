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
import re
import time

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
# Por corrida del tick: pocas notas y poco tiempo, para no frenar al resto de las tareas.
TONOS_POR_CORRIDA = lambda: int(os.environ.get("TONOS_POR_CORRIDA", 30))  # noqa: E731
SEGUNDOS_POR_CORRIDA = lambda: int(os.environ.get("TONOS_SEGUNDOS_POR_CORRIDA", 600))  # noqa: E731
MIN_PALABRAS_CITA = 3

ETIQUETAS = dict(Tono.VALENCIAS)


class TonoOut(BaseModel):
    persona: str
    valencia: int = Field(ge=-2, le=2)
    cita: str = ""
    razon: str = ""


class TonosOut(BaseModel):
    tonos: list[TonoOut] = Field(default_factory=list)

    @classmethod
    def desde(cls, data):
        """Valida ítem por ítem: un tono mal formado no tira los demás."""
        items = data.get("tonos") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ValueError("falta la lista 'tonos'")
        tonos = []
        for item in items:
            try:
                tonos.append(TonoOut.model_validate(item))
            except ValidationError as e:
                logger.warning("Tono descartado por formato: %s", e)
        return cls(tonos=tonos)


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
        self.intentos = 0

    def tonos(self, fuente, personas):
        from litellm import completion

        entrada = construir_entrada(fuente, personas)
        ultimo_error = None
        self.intentos = 0
        for modelo in self.modelos:
            self.intentos += 1
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
                return TonosOut.desde(data)
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
            return TonosOut.desde(s) if isinstance(s, dict) else s
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
    """Minúsculas, sin tildes ni puntuación, espacios simples."""
    return " ".join(re.sub(r"[^\w\s]", " ", normalize_entity_name(texto)).split())


def nombrada(persona, texto_norm):
    """¿La nota nombra a la persona? Nombre completo o apellido: el último
    (≥ 4 letras) o los dos últimos si es compuesto («Lacalle Pou»)."""
    nombre = _norm(persona.nombre)
    if not nombre:
        return False
    texto = f" {texto_norm} "
    if f" {nombre} " in texto:
        return True
    partes = nombre.split()
    apellidos = []
    if len(partes) >= 3:
        apellidos.append(" ".join(partes[-2:]))
    if len(partes) >= 2 and len(partes[-1]) >= 4:
        apellidos.append(partes[-1])
    return any(f" {a} " in texto for a in apellidos)


def texto_de_referencia(fuente):
    """Lo que el LLM ve de la nota: título y cuerpo recortado. Las citas se buscan acá."""
    return f"{fuente.titulo}\n\n{(fuente.texto or fuente.bajada)[:MAX_CHARS]}"


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
    try:
        salida = tonador.tonos(fuente, personas)
    finally:
        # Cada modelo intentado es una llamada paga, aunque falle.
        registrar_uso("llm", "tono", cantidad=getattr(tonador, "intentos", 0) or 1)

    por_nombre = {_norm(p.nombre): p for p in personas}
    referencia = texto_de_referencia(fuente)
    texto_norm = _norm(referencia)
    guardados = 0
    for t in salida.tonos:
        persona = por_nombre.get(_norm(t.persona))
        cita = t.cita.strip().strip("«»\"“”")
        cita_norm = _norm(cita)
        if not persona or len(cita_norm.split()) < MIN_PALABRAS_CITA or cita_norm not in texto_norm:
            continue  # persona inventada, cita muy corta o que no está en la nota
        verificado = decidir(
            "tono_respaldado",
            {
                "persona": persona.nombre,
                "valencia": ETIQUETAS[t.valencia],
                "cita": cita,
                "nota": referencia,
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


def tomar(fuente) -> bool:
    """Marca la nota como en curso si nadie la tomó desde que se leyó la cola.
    Evita que dos corridas superpuestas paguen dos veces la misma nota."""
    qs = Fuente.objects.filter(pk=fuente.pk)
    qs = qs.filter(tonos_en__isnull=True) if fuente.tonos_en is None else qs.filter(tonos_en=fuente.tonos_en)
    return qs.update(tonos_en=timezone.now()) == 1


def calcular_tonos(limite=None, desde=None, segundos=None) -> str:
    """Procesa notas pendientes, nuevas primero, hasta el cupo diario
    (MAX_TONOS_DIA llamadas al LLM), `limite` llamadas o `segundos` en esta corrida."""
    llamadas = guardados = 0
    fin = time.monotonic() + segundos if segundos else None
    for f in tonos_pendientes(desde).iterator():
        if tonos_hoy() >= MAX_TONOS_DIA() or (limite is not None and llamadas >= limite):
            break
        if fin is not None and time.monotonic() >= fin:
            break
        if not tomar(f):
            continue
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
