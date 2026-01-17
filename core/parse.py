from typing import Optional, Literal, Union
import os
from pydantic import BaseModel, Field
from litellm import completion
from bs4 import BeautifulSoup
from core.url_requests import get
import logging

# import litellm
# litellm._turn_on_debug()
logger = logging.getLogger(__name__)

MODELS_PRIORITY_JSON = {
    "openrouter/mistralai/mistral-saba": 1,
    "openai/gpt-oss-20b:free": 2,
}

MODELS_PRIORITY_MD = {
    "openrouter/google/gemini-2.0-flash-lite-001": 1,
    "openai/gpt-oss-20b:free": 2,
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


def remove_unnecessary_tags(html):
    soup = BeautifulSoup(html, "html.parser")
    # remove all attrs except id
    for tag in soup(True):
        tag.attrs = {"id": tag.get("id", "")}

    # Only filter for CONTENT div if it exists (archive.ph format)
    # For extension-captured HTML, use the whole soup
    content_div = soup.find("div", id="CONTENT")
    if content_div is not None:
        soup = content_div

    for tag in soup(
        [
            "script",
            "style",
            "img",
            "video",
            "audio",
            "iframe",
            "noscript",
            "old-meta",
            "old-script",
            "link",
        ]
    ):
        tag.decompose()
    # remove all styles, classes, and empty tags
    for tag in soup(True):
        if tag.name == "style" or not tag.text.strip():
            tag.decompose()
        else:
            tag.attrs = {}

    return str(soup)


class EntidadNombrada(BaseModel):
    nombre: str = Field(alias="nombre")
    tipo: Literal["persona", "organizacion", "lugar", "otro"]
    sentimiento: Literal["positivo", "negativo", "neutral"]


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


class Articulo(BaseModel):
    titulo: str = Field(alias="titulo", description="The title of the article.")
    fuente: str = Field(alias="fuente", description="The name of the news source.")
    categoria: Optional[
        Literal["politica", "economia", "seguridad", "salud", "educacion", "otros"]
    ] = Field(None, description="The category of the article.")
    autor: Optional[str] = Field(None, description="The author of the article.")
    fecha: Optional[str] = Field(
        None,
        description="The date of the article in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    resumen: Optional[str] = Field(None, description="A brief summary of the article.")
    imagen: Optional[str] = Field(None, description="Image URL if found in HTML")
    descripcion: Optional[str] = Field(
        None, description="Article description if found"
    )
    entidades: Optional[list[EntidadNombrada]] = Field(None, alias="entidades")


def parse_noticia(
    markdown: str, current_model="openrouter/google/gemini-2.0-flash-lite-001"
) -> Union[Articulo, None]:
    """
    Return the parsed article from the given HTML content.
    """
    try:
        response = completion(
            model=current_model,
            caching=False,
            response_format=Articulo,
            extra_headers=_get_extra_headers(current_model),
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful markdown parser designed to output JSON.",
                },
                {
                    "role": "user",
                    "content": f"""From the crawled content, metadata about the news article should be extracted.
                    The metadata should include the title (titulo), source (fuente), category (categoria), author (autor), summary (resumen), date (fecha) and entities (entidades) mentioned in the article.
                    The entities should include the name (nombre), type (tipo), and sentiment (sentimiento) of each entity.
                    The Markdown content to parse is as follows:

                {markdown}""",
                },
            ],
        )
        article_data = response.choices[0].message.content
        return Articulo.model_validate_json(article_data)
    except Exception as e:
        # Choose the next model in the priority list, if not available raise
        # Use priority order, don't repeat models
        for model, priority in MODELS_PRIORITY_JSON.items():
            if (
                model != current_model
                and priority > MODELS_PRIORITY_JSON[current_model]
            ):
                try:
                    return parse_noticia(markdown, model)
                except Exception as e:
                    logger.error(f"Error parsing the article: {e}")
                    continue

        logger.error(f"Error parsing the article: {e}")
        return None


def parse_noticia_from_html(
    html: str,
    current_model: str = "openrouter/google/gemini-2.0-flash-lite-001",
) -> Union[Articulo, None]:
    """
    Extract structured article data directly from HTML in a single LLM call.
    This includes entities, metadata, and fixing any missing title/image/desc.
    """
    try:
        clean_html = remove_unnecessary_tags(html)
        response = completion(
            model=current_model,
            caching=False,
            response_format=Articulo,
            extra_headers=_get_extra_headers(current_model),
            messages=[
                {
                    "role": "system",
                    "content": """You are a helpful HTML parser that extracts
                    structured article metadata from news HTML.
                    Extract: title, source, category, author, date, summary,
                    entities, image URL, and description.
                    Focus only on the main article content, ignore ads and nav.
                    """,
                },
                {
                    "role": "user",
                    "content": f"""From the HTML below, extract all article
                    metadata including entities with sentiment.
                    If title, image, or description are missing or generic,
                    try to extract better values from the article content.

                    HTML content:
                    {clean_html}
                    """,
                },
            ],
        )
        article_data = response.choices[0].message.content
        return Articulo.model_validate_json(article_data)
    except Exception as e:
        for model, priority in MODELS_PRIORITY_JSON.items():
            if (
                model != current_model
                and priority > MODELS_PRIORITY_JSON.get(current_model, 0)
            ):
                try:
                    return parse_noticia_from_html(html, model)
                except Exception as inner_e:
                    logger.error(f"Error parsing article with {model}: {inner_e}")
                    continue
        logger.error(f"Error parsing article from HTML: {e}")
        return None


def parse_noticia_markdown(
    html: str,
    title: str,
    current_model: str = "openrouter/google/gemini-2.0-flash-lite-001",
) -> Union[str, None]:
    """
    DEPRECATED: Use parse_noticia_from_html instead.
    Return the parsed article from the given HTML content.
    """
    try:
        clean_html = remove_unnecessary_tags(html)
        response = completion(
            model=current_model,
            extra_headers=_get_extra_headers(current_model),
            messages=[
                {
                    "role": "system",
                    "content": """
                    You are a helpful html parser designed to output a markdown version of the news article.
                    There could be other content in the creawled HTML, but you should only output the main article.
                    The markdown should include the title, source, author, date and main content of the article.
                    Everything else should be ignored.
                    Markdown subtitles should be in spanish, article language should be respected.
                    No html tags should be present in the markdown output.
                    """,
                },
                {
                    "role": "user",
                    "content": f"""
                    The HTML content to parse is as follows:

                    {clean_html}

                    The title of the article we are interested in is:
                    {title}

                    The markdown version of the article is:
                    """,
                },
            ],
        )
        article_md = response.choices[0].message.content

        return article_md
    except Exception as e:
        # Choose the next model in the priority list, if not available raise
        # Use priority order, don't repeat models
        for model, priority in MODELS_PRIORITY_MD.items():
            if model != current_model and priority > MODELS_PRIORITY_MD[current_model]:
                try:
                    return parse_noticia_markdown(html, title, model)
                except Exception as e:
                    logger.error(f"Error parsing the article: {e}")
                    continue
        logger.error(f"Error parsing the article: {e}")
        return None


BAD_TITLES = ["la diaria"]

BAD_URLS = ["https://ladiaria.com.uy/static/meta/la-diaria-1000x1000.png"]


def parse_from_html_string(html, base_url=None):
    """
    Extract title, image, and description from HTML string.
    Similar to parse_from_meta_tags but works with captured HTML.
    Returns: (title, image, description) tuple
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Extract title with multiple fallbacks
        title = None
        og_title = soup.find("meta", property="og:title")
        twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
        html_title = soup.find("title")
        h1_title = soup.find("h1")

        if og_title and og_title.get("content"):
            title = og_title["content"]
        elif twitter_title and twitter_title.get("content"):
            title = twitter_title["content"]
        elif h1_title and h1_title.get_text().strip():
            title = h1_title.get_text().strip()
        elif html_title and html_title.string:
            title = html_title.string.strip()

        # Filter bad titles (too short or generic)
        if title and (
            title.lower() in [t.lower() for t in BAD_TITLES]
            or len(title) < 10
            or title.lower() in ["mostrar todos los tags", "tags"]
        ):
            # Fallback to H1 if meta title is bad
            if h1_title and h1_title.get_text().strip():
                title = h1_title.get_text().strip()
            else:
                title = None

        # Extract description
        description = None
        og_desc = soup.find("meta", property="og:description")
        twitter_desc = soup.find("meta", attrs={"name": "twitter:description"})
        meta_desc = soup.find("meta", attrs={"name": "description"})

        if og_desc and og_desc.get("content"):
            description = og_desc["content"]
        elif twitter_desc and twitter_desc.get("content"):
            description = twitter_desc["content"]
        elif meta_desc and meta_desc.get("content"):
            description = meta_desc["content"]

        # Extract image
        image_url = None
        og_image = soup.find("meta", property="og:image")
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})

        if og_image and og_image.get("content"):
            image_url = og_image["content"]
        elif twitter_image and twitter_image.get("content"):
            image_url = twitter_image["content"]

        # Make relative URLs absolute if base_url provided
        if image_url and base_url and not image_url.startswith(("http://", "https://")):
            from urllib.parse import urljoin

            image_url = urljoin(base_url, image_url)

        # Filter bad images
        if image_url and image_url in BAD_URLS:
            image_url = None

        logger.info(f"Parsed from HTML - Title: {title}, Image: {image_url}")
        return title, image_url, description

    except Exception as e:
        logger.error(f"Error parsing HTML string: {e}")
        return None, None, None


def parse_from_meta_tags(url):
    """
    Extract title, image, and description from URL meta tags.
    Returns: (title, image, description) tuple
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/92.0.4515.107 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }

        response = get(
            url, headers=headers, rotate_user_agent=True, retry_on_failure=True
        )
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title with multiple fallbacks
        title = None
        og_title = soup.find("meta", property="og:title")
        twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
        html_title = soup.find("title")

        if og_title and og_title.get("content"):
            title = og_title["content"]
        elif twitter_title and twitter_title.get("content"):
            title = twitter_title["content"]
        elif html_title and html_title.string:
            title = html_title.string.strip()

        # Filter bad titles
        if title and title.lower() in [t.lower() for t in BAD_TITLES]:
            title = None

        logger.info(f"Title: {title} from {url}")

        # Extract description
        description = None
        og_desc = soup.find("meta", property="og:description")
        twitter_desc = soup.find("meta", attrs={"name": "twitter:description"})
        meta_desc = soup.find("meta", attrs={"name": "description"})

        if og_desc and og_desc.get("content"):
            description = og_desc["content"]
        elif twitter_desc and twitter_desc.get("content"):
            description = twitter_desc["content"]
        elif meta_desc and meta_desc.get("content"):
            description = meta_desc["content"]

        logger.info(f"Description: {description[:100] if description else None}")

        # Extract image
        original_image = None
        og_image = soup.find("meta", property="og:image")
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})

        image_url = None
        if og_image and og_image.get("content"):
            image_url = og_image["content"]
        elif twitter_image and twitter_image.get("content"):
            image_url = twitter_image["content"]

        if image_url:
            # Check if it's an archive.org URL that contains an embedded original URL
            # Example formats:
            # 1. https://web.archive.org/web/20250304162934im_/https://media.elobservador.com.uy/...
            # 2. https://web.archive.org/web/20250304162934/https://media.elobservador.com.uy/...
            possible_urls = [image_url]

            # If it's an archive.org URL, extract the original URL
            if "web.archive.org" in image_url:
                # Handle /im_/ format (used for images)
                if "/im_/" in image_url:
                    parts = image_url.split("/im_/", 1)
                    if len(parts) > 1:
                        extracted_url = parts[1]
                        possible_urls.append(extracted_url)
                        logger.info(
                            f"Extracted original URL from archive.org im_ format: {extracted_url}"
                        )
                # Handle standard /web/ format
                elif "/web/" in image_url:
                    # Extract timestamp and URL
                    parts = image_url.split("/web/", 1)
                    if len(parts) > 1:
                        # The URL might be after a timestamp like 20250304162934/
                        timestamp_and_url = parts[1]
                        # Find the first occurrence of http or https after /web/
                        for protocol in ["http://", "https://"]:
                            if protocol in timestamp_and_url:
                                protocol_index = timestamp_and_url.find(protocol)
                                extracted_url = timestamp_and_url[protocol_index:]
                                possible_urls.append(extracted_url)
                                logger.info(
                                    f"Extracted original URL from archive.org web format: {extracted_url}"
                                )
                                break

            # Try each URL in order until one works
            for img_url in possible_urls:
                if img_url not in BAD_URLS:
                    try:
                        logger.info(f"Trying image URL: {img_url}")
                        image_response = get(
                            img_url, rotate_user_agent=True, retry_on_failure=True
                        )
                        if image_response.status_code == 200:
                            original_image = img_url
                            logger.info(f"Successfully retrieved image from: {img_url}")
                            break
                        else:
                            logger.warning(
                                f"Failed to retrieve image from: {img_url} (Status: {image_response.status_code})"
                            )
                    except Exception as e:
                        logger.warning(f"Error getting image from URL: {img_url} - {e}")

            if not original_image:
                logger.error(
                    f"Failed to retrieve any valid image from the possible URLs: {possible_urls}"
                )

        logger.info(f"Title: {title}")
        logger.info(f"Image: {original_image}")
        logger.info(f"Description: {description[:100] if description else None}...")
        return title, original_image, description

    except Exception as e:
        logger.error(f"Error getting title from meta tags: {e}")
    return None, None, None


MODELS_PRIORITY_CLUSTER = {
    "openrouter/google/gemini-2.0-flash-lite-001": 1,
    "openrouter/mistralai/mistral-saba": 2,
}


def generate_cluster_description(
    top_noticias: list[dict],
    entities_positive: list[dict],
    entities_negative: list[dict],
    cluster_size: int,
    consensus_score: float,
    current_model: str = "openrouter/google/gemini-2.0-flash-lite-001",
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
        noticias_text = "\n".join([
            f"- {n['titulo']} (opinión: {n['majority_opinion']}, "
            f"consenso: {n['consensus']:.0%})"
            for n in top_noticias[:7]
        ])

        entities_pos_text = ", ".join([
            f"{e['nombre']} ({e['tipo']})"
            for e in entities_positive[:5]
        ]) or "ninguna identificada"

        entities_neg_text = ", ".join([
            f"{e['nombre']} ({e['tipo']})"
            for e in entities_negative[:5]
        ]) or "ninguna identificada"

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
            if (
                model != current_model
                and priority > MODELS_PRIORITY_CLUSTER.get(current_model, 0)
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
