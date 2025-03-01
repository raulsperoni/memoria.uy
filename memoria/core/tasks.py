from celery import shared_task
from celery.utils.log import get_task_logger
from core.models import Noticia, Entidad, NoticiaEntidad
from core import parse
from core import archive_ph as archive
from datetime import datetime

logger = get_task_logger(__name__)


@shared_task
def enrich_markdown(noticia_id, html):
    noticia = Noticia.objects.get(id=noticia_id)
    if noticia.archivo_url:
        logger.info(f"Fetching archived URL for {noticia.enlace}")
        markdown = parse.parse_noticia_markdown(html, noticia.titulo)
        if markdown:
            noticia.markdown = markdown
            noticia.save()
            logger.info(f"Enriched {noticia.enlace} with markdown")
            enrich_content.delay(noticia_id)
            return noticia_id
        logger.error(f"Failed to enrich {noticia.enlace} with markdown")
    else:
        logger.error(f"No archived URL for {noticia.enlace}")
    return noticia_id


@shared_task
def enrich_content(noticia_id):
    noticia = Noticia.objects.get(id=noticia_id)
    if noticia.markdown:
        articulo = parse.parse_noticia(noticia.markdown)
        if articulo:
            noticia.titulo = articulo.titulo
            noticia.fuente = articulo.fuente
            noticia.categoria = articulo.categoria if articulo.categoria else "otros"
            noticia.resumen = articulo.resumen
            if articulo.fecha:
                try:
                    noticia.fecha_noticia = datetime.fromisoformat(articulo.fecha)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not parse date {articulo.fecha} for {noticia.enlace}"
                    )
            noticia.save()
            logger.info(f"Enriched {noticia.enlace} with content")
            if articulo.entidades:
                for entidad_nombrada in articulo.entidades:
                    logger.info(f"Found entity {entidad_nombrada}")
                    entidad, _ = Entidad.objects.get_or_create(
                        nombre=entidad_nombrada.nombre, tipo=entidad_nombrada.tipo
                    )
                    NoticiaEntidad.objects.get_or_create(
                        noticia=noticia,
                        entidad=entidad,
                        defaults={"sentimiento": entidad_nombrada.sentimiento},
                    )
                logger.info(f"Entities saved for {noticia.enlace}")
            return noticia_id
        logger.error(f"Failed to enrich {noticia.enlace} with content")
    else:
        logger.error(f"No markdown content for {noticia.enlace}")
    return noticia_id


@shared_task(bind=True, max_retries=3)
def find_archived(self, noticia_id):
    """Async task to retry finding archived URL when archive is in progress.
    This task is called after the first synchronous attempt fails with ArchiveInProgress.
    """
    try:
        noticia = Noticia.objects.get(id=noticia_id)
        noticia.archivo_url, html = archive.get_latest_snapshot(noticia.enlace)
        noticia.archivo_fecha = datetime.now()
        noticia.save()
        if not noticia.markdown:
            enrich_markdown.delay(noticia.id, html)
        elif not noticia.resumen:
            enrich_content.delay(noticia.id)
        noticia.update_title_image_from_archive()
        logger.info(
            f"Successfully archived URL for noticia {noticia_id} on retry #{self.request.retries+1}"
        )
        return noticia.archivo_url
    except archive.ArchiveInProgress as e:
        retry_count = self.request.retries
        if retry_count < 2:  # We'll do a total of 3 attempts (0, 1, 2)
            logger.info(
                f"Archive still in progress for noticia {noticia_id}, retry {retry_count+1}/3 in 3 minutes"
            )
            # Retry in 3 minutes (180 seconds)
            raise self.retry(exc=e, countdown=180)
        else:
            logger.warning(
                f"Archive still in progress after 3 attempts for noticia {noticia_id}, giving up"
            )
            return None
    except Exception as e:
        logger.error(f"Error in find_archived task for noticia {noticia_id}: {e}")
        return None
