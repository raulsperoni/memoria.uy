"""
Procesamiento LLM de una Historia: título, resumen, hechos con procedencia,
proposiciones opinables y entidades.

Usa LiteLLM en modo JSON con fallback de modelos (mismo patrón que core/parse.py).
Env: ARCHIVO_LLM_MODELS (lista separada por comas).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# Benchmark 2026-11-22 (4 historias reales, verificación con Jev): Haiku 5.5
# dio los hechos más completos y precisos y las proposiciones más claras
# (~US$0,0018/historia, ~10 s). Fallbacks baratos y rápidos.
DEFAULT_MODELS = [
    "openrouter/anthropic/claude-haiku-5.5",
    "openrouter/openai/gpt-6-luna",
    "openrouter/openai/gpt-5-nano",
]

MAX_CHARS_FUENTE = 6000
MAX_FUENTES = 6


class EntidadOut(BaseModel):
    nombre: str
    tipo: Literal["persona", "organizacion", "lugar", "otro"]


class HechoOut(BaseModel):
    texto: str = Field(max_length=400)
    fuentes: list[int]
    citas: list[str] = Field(default_factory=list)
    entidades: list[str] = Field(default_factory=list)
    disputado: bool = False


class ProposicionOut(BaseModel):
    texto: str = Field(max_length=250)
    hechos: list[int] = Field(default_factory=list)
    tema: str = ""
    entidades: list[str] = Field(default_factory=list)


class HistoriaOut(BaseModel):
    titulo: str = Field(max_length=300)
    resumen: str
    categoria: Literal[
        "politica",
        "economia",
        "seguridad",
        "salud",
        "educacion",
        "sociedad",
        "internacional",
        "otros",
    ]
    hechos: list[HechoOut]
    proposiciones: list[ProposicionOut] = Field(default_factory=list)
    entidades: list[EntidadOut] = Field(default_factory=list)


SYSTEM = """Sos editor de un archivo público de noticias uruguayas. Recibís
varias notas de distintos medios sobre un mismo hecho. Devolvés SOLO JSON con
este esquema:

{
  "titulo": str,            // neutral, informativo, sin adjetivos valorativos, ≤ 120 caracteres
  "resumen": str,           // 2–3 oraciones, ≤ 400 caracteres, solo lo que dicen las fuentes
  "categoria": "politica"|"economia"|"seguridad"|"salud"|"educacion"|"sociedad"|"internacional"|"otros",
  "hechos": [               // 2 a 6
    {
      "texto": str,         // afirmación fáctica breve en tus palabras (≤ 280 caracteres)
      "fuentes": [int],     // índices [n] de las notas que la respaldan explícitamente
      "citas": [str],       // por cada fuente, una cita literal breve (≤ 200 caracteres) que la respalda
      "entidades": [str],   // nombres de entidades mencionadas
      "disputado": bool     // true si las fuentes se contradicen sobre esto
    }
  ],
  "proposiciones": [        // 0 a 3
    {
      "texto": str,         // frase opinable, afirmativa, ≤ 160 caracteres
      "hechos": [int],      // índices (desde 0) de los hechos en que se apoya
      "tema": str,          // etiqueta corta y estable, reutilizá una de la lista si aplica
      "entidades": [str]
    }
  ],
  "entidades": [{"nombre": str, "tipo": "persona"|"organizacion"|"lugar"|"otro"}]
}

Reglas:
- Hechos: solo lo que dicen las notas. Nada de inferencias. Nunca un hecho sin fuente.
- Proposiciones: algo sobre lo que una persona razonable de cualquier lado
  político pueda estar de acuerdo o en desacuerdo. Nunca un hecho verificable.
  Nunca sobre personas privadas. Sin lenguaje cargado ni dobles negaciones.
  Si el hecho no da para opinar (p.ej. un accidente), no generes proposiciones.
- Entidades: nombres completos y canónicos ("Yamandú Orsi", no "Orsi").
- Español rioplatense neutro.
"""


def construir_entrada(fuentes, temas_existentes=()):
    partes = []
    for i, f in enumerate(fuentes[:MAX_FUENTES]):
        cabecera = f"[{i}] {f.medio.nombre} — {f.titulo}\n"
        if f.publicada_en:
            cabecera += f"Fecha: {f.publicada_en:%Y-%m-%d}\n"
        partes.append(cabecera + (f.texto or f.bajada)[:MAX_CHARS_FUENTE])
    temas = ", ".join(temas_existentes) or "(ninguno todavía)"
    return f"Temas existentes: {temas}\n\nNotas:\n\n" + "\n\n---\n\n".join(partes)


class Procesador:
    def procesar(self, fuentes, temas_existentes=()) -> HistoriaOut:
        raise NotImplementedError


class LLMProcesador(Procesador):
    def __init__(self, modelos=None):
        env = os.environ.get("ARCHIVO_LLM_MODELS")
        self.modelos = modelos or (env.split(",") if env else DEFAULT_MODELS)

    def procesar(self, fuentes, temas_existentes=()):
        from litellm import completion

        entrada = construir_entrada(fuentes, temas_existentes)
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
                    # Razonamiento bajo: suficiente para extracción y 3-5x más rápido.
                    extra_body={"reasoning": {"effort": "low"}},
                    timeout=120,
                )
                texto = resp.choices[0].message.content or ""
                # Algunos modelos envuelven el JSON en ```json ... ```
                data = json.loads(texto[texto.find("{") : texto.rfind("}") + 1])
                return HistoriaOut.model_validate(data)
            except (ValidationError, json.JSONDecodeError, Exception) as e:  # noqa: B014
                logger.warning("Modelo %s falló procesando historia: %s", modelo, e)
                ultimo_error = e
        raise RuntimeError(f"Todos los modelos fallaron: {ultimo_error}")


class FakeProcesador(Procesador):
    def __init__(self, salida: HistoriaOut | dict | None = None):
        self.salida = salida

    def procesar(self, fuentes, temas_existentes=()):
        if self.salida is not None:
            if isinstance(self.salida, dict):
                return HistoriaOut.model_validate(self.salida)
            return self.salida
        f0 = fuentes[0]
        return HistoriaOut(
            titulo=f0.titulo[:120] or "Sin título",
            resumen=(f0.texto or f0.bajada)[:300],
            categoria="politica",
            hechos=[
                HechoOut(
                    texto=f"Según {f.medio.nombre}: {f.titulo}"[:280],
                    fuentes=[i],
                    citas=[(f.texto or f.titulo)[:150]],
                )
                for i, f in enumerate(fuentes[:3])
            ],
            proposiciones=[
                ProposicionOut(texto=f"Lo ocurrido con «{f0.titulo[:80]}» es positivo para el país", hechos=[0], tema="general")
            ],
            entidades=[],
        )


_override = None


def set_procesador(p):
    global _override
    _override = p


def get_procesador() -> Procesador:
    return _override or LLMProcesador()
