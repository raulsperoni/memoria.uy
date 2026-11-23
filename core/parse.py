from typing import Optional, Literal, Union
import os
from pydantic import BaseModel, Field
from litellm import completion
import logging
import litellm

litellm.set_verbose = False


# import litellm
# litellm._turn_on_debug()
logger = logging.getLogger(__name__)

# =============================================================================
# LLM Model Priority Configuration
# =============================================================================
# Models are tried in priority order (1 = highest). If a model fails, the next
# priority model is used as fallback. All models must support JSON output mode.

# Used by: generate_cluster_description()
# Purpose: Generate creative cluster names and descriptions in Spanish
# Requirements: JSON output mode, creative writing in Spanish (rioplatense)
MODELS_PRIORITY_CLUSTER = {
    "openrouter/anthropic/claude-haiku-5.5": 1,
    "openrouter/openai/gpt-6-luna": 2,
    "openrouter/openai/gpt-5-nano": 3,
}


def _get_extra_headers(model: str) -> Optional[dict]:
    if not model.startswith("openrouter/"):
        return None
    headers = {}
    app_name = os.getenv("OPENROUTER_APP_NAME") or os.getenv("OR_APP_NAME")
    app_url = os.getenv("OPENROUTER_APP_URL") or os.getenv("OR_SITE_URL")
    if app_name:
        headers["X-Title"] = app_name
    if app_url:
        headers["HTTP-Referer"] = app_url
    return headers or None


class ClusterDescription(BaseModel):
    """LLM-generated cluster name and description."""

    nombre: str = Field(
        description="Nombre corto y juguetón para el cluster (max 50 chars). "
        "Ej: 'Los Escépticos', 'Optimistas Urbanos', 'Críticos del Sistema'"
    )
    descripcion: str = Field(
        description="Descripción breve del perfil de opinión (max 200 chars). "
        "Describe qué tipo de noticias aprueban/rechazan y sus tendencias."
    )


def generate_cluster_description(
    top_noticias: list[dict],
    entities_positive: list[dict],
    entities_negative: list[dict],
    cluster_size: int,
    consensus_score: float,
    current_model: str = "openrouter/anthropic/claude-haiku-5.5",
) -> Union[ClusterDescription, None]:
    """
    Generate a playful name and description for a voter cluster using LLM.

    Args:
        top_noticias: List of dicts with keys: titulo, resumen, majority_opinion,
            consensus
        entities_positive: List of dicts: {"nombre": str, "tipo": str, "count": int}
        entities_negative: List of dicts: {"nombre": str, "tipo": str, "count": int}
        cluster_size: Number of voters in cluster
        consensus_score: Within-cluster agreement (0-1)
        current_model: LLM model to use

    Returns:
        ClusterDescription or None if generation fails
    """
    try:
        # Build context for the prompt
        noticias_text = "\n".join(
            [
                f"- {n['titulo']} (opinión: {n['majority_opinion']}, "
                f"consenso: {n['consensus']:.0%})"
                for n in top_noticias[:7]
            ]
        )

        entities_pos_text = (
            ", ".join([f"{e['nombre']} ({e['tipo']})" for e in entities_positive[:5]])
            or "ninguna identificada"
        )

        entities_neg_text = (
            ", ".join([f"{e['nombre']} ({e['tipo']})" for e in entities_negative[:5]])
            or "ninguna identificada"
        )

        prompt = f"""Analiza este grupo de votantes de un sitio de noticias uruguayo.

DATOS DEL CLUSTER:
- Tamaño: {cluster_size} votantes
- Consenso interno: {consensus_score:.0%}

NOTICIAS CON MAYOR CONSENSO EN EL GRUPO:
{noticias_text}

ENTIDADES VISTAS POSITIVAMENTE:
{entities_pos_text}

ENTIDADES VISTAS NEGATIVAMENTE:
{entities_neg_text}

Genera un nombre CORTO y JUGUETÓN para este grupo (máximo 50 caracteres).
El nombre debe capturar su "personalidad" de votante.
También genera una descripción breve (máximo 200 caracteres).

Ejemplos de buenos nombres: "Los Escépticos", "Optimistas del Interior",
"Críticos del Sistema", "Los Moderados", "Apasionados del Fútbol"
"""

        response = completion(
            model=current_model,
            caching=False,
            response_format=ClusterDescription,
            extra_headers=_get_extra_headers(current_model),
            messages=[
                {
                    "role": "system",
                    "content": "Eres un analista político uruguayo que crea "
                    "descripciones ingeniosas y concisas de grupos de opinión. "
                    "Responde siempre en español rioplatense.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        description_data = response.choices[0].message.content
        return ClusterDescription.model_validate_json(description_data)

    except Exception as e:
        logger.error(f"Error generating cluster description with {current_model}: {e}")
        # Try fallback models
        for model, priority in MODELS_PRIORITY_CLUSTER.items():
            if model != current_model and priority > MODELS_PRIORITY_CLUSTER.get(
                current_model, 0
            ):
                try:
                    return generate_cluster_description(
                        top_noticias=top_noticias,
                        entities_positive=entities_positive,
                        entities_negative=entities_negative,
                        cluster_size=cluster_size,
                        consensus_score=consensus_score,
                        current_model=model,
                    )
                except Exception as inner_e:
                    logger.error(f"Fallback to {model} also failed: {inner_e}")
                    continue

        logger.error("All models failed to generate cluster description")
        return None
