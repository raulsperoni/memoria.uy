from typing import Optional, Literal, Union
from pydantic import BaseModel, Field
from litellm import completion
from bs4 import BeautifulSoup
import logging

# litellm._turn_on_debug()
logger = logging.getLogger(__name__)

MODELS_PRIORITY_JSON = {"openrouter/mistralai/mistral-saba": 1, "openai/o3-mini": 2}

MODELS_PRIORITY_MD = {
    "openrouter/google/gemini-2.0-flash-lite-001": 1,
    "openai/o3-mini": 2,
}


def remove_unnecessary_tags(html):
    soup = BeautifulSoup(html, "html.parser")
    # remove all attrs except id
    for tag in soup(True):
        tag.attrs = {"id": tag.get("id", "")}
    soup = soup.find("div", id="CONTENT")

    if soup is None:
        return ""

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


class Articulo(BaseModel):
    titulo: str = Field(alias="titulo", description="The title of the article.")
    fuente: str = Field(alias="fuente", description="The name of the news source.")
    categoria: Optional[
        Literal["politica", "economia", "seguridad", "salud", "educacion", "otros"]
    ] = Field(None, description="The category of the article.")
    autor: Optional[str] = Field(None, description="The author of the article.")
    resumen: Optional[str] = Field(None, description="A brief summary of the article.")
    entidades: Optional[list[EntidadNombrada]] = Field(None, alias="entidades")

    def json_example(self):
        return """
            {
                "articulo": {
                    "titulo": "Gobierno electo le ofreció 34 cargos a la oposición y la coalición se reunirá para hacer una contrapropuesta",
                    "fuente": "La Diaria",
                    "categoria": "politica",
                    "autor": "Pedro Gonzalez",
                    "resumen": "El gobierno electo ha ofrecido 34 cargos a la oposición, con la expectativa de que hagan una contrapropuesta conjunta.",
                    "entidades": [
                        {
                            "nombre": "Gobierno electo",
                            "tipo": "organizacion",
                            "sentimiento": "neutral"
                        },
                        {
                            "nombre": "Coalición",
                            "tipo": "organizacion",
                            "sentimiento": "positivo"
                        }
                    ]
                }
            }
            """


def parse_noticia(
    markdown: str, current_model="openrouter/openai/o3-mini"
) -> Union[Articulo, None]:
    """
    Return the parsed article from the given HTML content.
    """
    try:
        response = completion(
            model=current_model,
            caching=True,
            response_format=Articulo,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful html parser designed to output JSON.",
                },
                {
                    "role": "user",
                    "content": f"""From the crawled content, metadata about the news article should be extracted.
                    The metadata should include the title, source, category, author, and entities mentioned in the article.
                    The entities should include the name, type, and sentiment of each entity.
                    The Markdown content to parse is as follows:
                
                {markdown}""",
                },
            ],
        )
        article_data = response.choices[0].message.content
        return Articulo.parse_raw(article_data)
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


def parse_noticia_markdown(
    html: str,
    title: str,
    current_model: str = "openrouter/google/gemini-2.0-flash-lite-001",
) -> Union[str, None]:
    """
    Return the parsed article from the given HTML content.
    """
    try:
        clean_html = remove_unnecessary_tags(html)
        response = completion(
            model=current_model,
            messages=[
                {
                    "role": "system",
                    "content": """
                    You are a helpful html parser designed to output a markdown version of the news article. 
                    There could be other content in the creawled HTML, but you should only output the main article.
                    The markdown should include the title, source, author, and main content of the article.
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
