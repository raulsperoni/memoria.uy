from typing import Optional, Literal, Union
from pydantic import BaseModel, Field
from litellm import completion
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


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


def parse_noticia(html) -> Union[Articulo, None]:
    """
    Return the parsed article from the given HTML content.
    """
    try:
        clean_html = remove_unnecessary_tags(html)
        response = completion(
            model="gpt-4o-mini",
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
                The HTML content to parse is as follows:
                
                {clean_html}""",
                },
            ],
        )
        article_data = response.choices[0].message.content
        return Articulo.parse_raw(article_data)
    except Exception as e:
        logger.error(
            f"Error parsing the article: {e}\nOriginal HTML:{html}\nClean HTML: {clean_html}"
        )
        logger.error(f"Error parsing the article: {e}")
        return None
