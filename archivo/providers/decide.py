"""
Decisiones tipadas (sí/no y score) sobre un registro.

- JevDecider: TypeSafe (Jev). Env: TYPESAFE_API_KEY, opcional TYPESAFE_BASE_URL
  (p.ej. OpenRouter) y TYPESAFE_DEFAULT_MODEL.
- LLMDecider: LLM barato vía LiteLLM en modo JSON (fallback).
- FakeDecider: tests.

Todas las decisiones devuelven un float en [0, 1] y se registran en
`archivo.Decision` (con caché por pregunta + hash de entrada).

Env: DECIDER=jev|llm|fake
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


# Catálogo de preguntas. `tipo`: "noul" (probabilidad de sí) o "score"
# (niveles 0..n-1, normalizado a 0..1).
PREGUNTAS = {
    "interes_publico": {
        "tipo": "noul",
        "instrucciones": (
            "Esta nota es de un medio uruguayo. ¿Es relevante para el debate "
            "público uruguayo?"
        ),
        "criterios": {
            "true": (
                "Política, gobierno, Parlamento, partidos, economía y finanzas "
                "públicas, impuestos, trabajo y sindicatos, justicia y Fiscalía, "
                "políticas de seguridad, salud y educación públicas, ambiente, "
                "empresas públicas, relaciones internacionales de Uruguay. Asumí "
                "que 'Gobierno', 'Senado', 'ministerio' refieren a Uruguay."
            ),
            "false": (
                "Deportes, espectáculos, celebridades, cultura y ciencia de "
                "divulgación, estilo de vida, recetas, eventos y agenda, crímenes "
                "individuales (rapiñas, accidentes) sin dimensión política, "
                "noticias de otros países sin vínculo con Uruguay."
            ),
        },
    },
    "vale_historia": {
        "tipo": "score",
        "instrucciones": (
            "¿Qué tan importante es este hecho para el debate público uruguayo "
            "y para un archivo de lo que pasó en el país?"
        ),
        "niveles": [
            "Irrelevante o efímero",
            "Menor, de interés local o sectorial",
            "Relevante, parte de la agenda del día",
            "Muy relevante, va a ser recordado o discutido por semanas",
        ],
    },
    "mismo_hecho": {
        "tipo": "noul",
        "instrucciones": (
            "Estas dos notas (A y B), ¿cubren el mismo hecho o acontecimiento "
            "concreto? Responder no si solo comparten tema general."
        ),
    },
    "fuente_respalda": {
        "tipo": "noul",
        "instrucciones": (
            "¿El texto de la fuente respalda explícitamente la afirmación? "
            "Responder no si la afirmación agrega datos que la fuente no dice."
        ),
    },
    "cambia_sentido": {
        "tipo": "noul",
        "instrucciones": (
            "Comparando la versión anterior y la nueva de esta nota, ¿el cambio "
            "altera el sentido o lo que el lector entendería del hecho? "
            "Responder no si son correcciones de estilo, erratas o agregados menores."
        ),
    },
    "divisividad": {
        "tipo": "score",
        "instrucciones": (
            "¿Qué tan dividida estaría la opinión pública uruguaya frente a "
            "esta proposición?"
        ),
        "niveles": [
            "Casi todos de acuerdo (o casi todos en contra)",
            "Mayoría clara con minoría significativa",
            "Bastante dividida",
            "Dividida en mitades, típico tema de grieta",
        ],
    },
    "calidad_proposicion": {
        "tipo": "score",
        "instrucciones": (
            "Evaluar la proposición para una votación de acuerdo/desacuerdo: "
            "¿es clara, breve, opinable (no un hecho verificable), sin lenguaje "
            "cargado, y no refiere a personas privadas?"
        ),
        "niveles": [
            "Inutilizable",
            "Confusa o sesgada",
            "Aceptable",
            "Clara, neutral y opinable",
        ],
    },
}


class Decider:
    nombre = "base"

    def decidir(self, pregunta: str, estado: dict) -> float:
        raise NotImplementedError


class JevDecider(Decider):
    nombre = "jev"

    def __init__(self):
        from typesafe_sdk import TypeSafeClient

        self.client = TypeSafeClient()
        self.modelo = os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-latest")
        self.nombre = f"jev:{self.modelo}"

    def decidir(self, pregunta, estado):
        from typesafe_sdk import Noul, Score

        p = PREGUNTAS[pregunta]
        if p["tipo"] == "noul":
            q = Noul(instructions=p["instrucciones"], criteria=p.get("criterios"))
        else:
            q = Score(instructions=p["instrucciones"], criteria=p["niveles"])
        resp = self.client.system_one(state=estado, questions={"q": q})
        ans = resp.answers["q"]
        if p["tipo"] == "noul":
            return float(ans.noul)
        return float(ans.score) / (len(p["niveles"]) - 1)


class LLMDecider(Decider):
    nombre = "llm"

    def __init__(self, modelo=None):
        self.modelo = modelo or os.environ.get(
            "DECIDER_LLM_MODEL", "openrouter/openai/gpt-5-nano"
        )
        self.nombre = f"llm:{self.modelo}"

    def decidir(self, pregunta, estado):
        from litellm import completion

        p = PREGUNTAS[pregunta]
        if p["tipo"] == "noul":
            formato = 'Respondé solo JSON: {"p": <probabilidad de sí entre 0 y 1>}'
            if p.get("criterios"):
                formato = (
                    f"Sí: {p['criterios']['true']}\nNo: {p['criterios']['false']}\n"
                    + formato
                )
        else:
            niveles = "\n".join(f"{i}: {n}" for i, n in enumerate(p["niveles"]))
            formato = f'Niveles:\n{niveles}\nRespondé solo JSON: {{"nivel": <entero>}}'
        resp = completion(
            model=self.modelo,
            messages=[
                {"role": "system", "content": p["instrucciones"] + "\n" + formato},
                {"role": "user", "content": json.dumps(estado, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            extra_body={"reasoning": {"effort": "low"}},
        )
        data = json.loads(resp.choices[0].message.content)
        if p["tipo"] == "noul":
            return max(0.0, min(1.0, float(data["p"])))
        return max(0, min(len(p["niveles"]) - 1, int(data["nivel"]))) / (
            len(p["niveles"]) - 1
        )


class FakeDecider(Decider):
    """Devuelve `respuestas[pregunta]` (valor o callable(estado)), default 0.9."""

    nombre = "fake"

    def __init__(self, respuestas=None, default=0.9):
        self.respuestas = respuestas or {}
        self.default = default
        self.llamadas = []

    def decidir(self, pregunta, estado):
        self.llamadas.append((pregunta, estado))
        r = self.respuestas.get(pregunta, self.default)
        return float(r(estado) if callable(r) else r)


_override = None


def set_decider(decider):
    global _override
    _override = decider


def get_decider(nombre: str | None = None) -> Decider:
    if _override is not None and nombre is None:
        return _override
    nombre = nombre or os.environ.get("DECIDER", "jev")
    return {"jev": JevDecider, "llm": LLMDecider, "fake": FakeDecider}[nombre]()


def decidir(pregunta: str, estado: dict, usar_cache: bool = True) -> float:
    """Decide y registra. Cachea por (pregunta, hash del estado)."""
    from archivo.models import Decision, sha256

    entrada_hash = sha256(json.dumps(estado, sort_keys=True, ensure_ascii=False))
    if usar_cache:
        previa = Decision.objects.filter(
            pregunta=pregunta, entrada_hash=entrada_hash
        ).first()
        if previa:
            return previa.valor
    decider = get_decider()
    valor = decider.decidir(pregunta, estado)
    Decision.objects.create(
        pregunta=pregunta, entrada_hash=entrada_hash, valor=valor, modelo=decider.nombre
    )
    return valor
