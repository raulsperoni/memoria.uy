from celery import shared_task
from typing import Optional, Literal
from celery.utils.log import get_task_logger
from pydantic import BaseModel, Field
from litellm import completion

logger = get_task_logger(__name__)


class EntidadNombrada(BaseModel):
    nombre: str = Field(alias="nombre")
    tipo: Literal["persona", "organizacion", "lugar", "otro"]
    sentimiento: Literal["positivo", "negativo", "neutral"]


class Articulo(BaseModel):
    titulo: str = Field(alias="titulo", description="The title of the article.")
    fuente: str = Field(alias="fuente", description="The name of the news source.")
    categoria: Optional[str] = Field(None, description="The category of the article.")
    autor: Optional[str] = Field(None, description="The author of the article.")
    resumen: Optional[str] = Field(None, description="A brief summary of the article.")
    entidades: Optional[list[EntidadNombrada]] = Field(None, alias="entidades")


@shared_task
def parse_noticia(html):
    response = completion(
        model="gpt-4o-mini",
        response_format=Articulo,
        messages=[
            ***REMOVED***
                "role": "system",
                "content": "You are a helpful html parser designed to output JSON.",
          ***REMOVED***
            ***REMOVED***
                "role": "user",
                "content": f"""From the crawled content, metadata about the news article should be extracted.
            The metadata should include the title, source, category, author, and entities mentioned in the article.
            The entities should include the name, type, and sentiment of each entity.
            The HTML content to parse is as follows:
            
            ***REMOVED***html***REMOVED***""",
          ***REMOVED***
     ***REMOVED***,
    )
    print(response.choices[0].message.content)
