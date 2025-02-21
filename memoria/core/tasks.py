from celery import shared_task
from core.models import Noticia
from celery.utils.log import get_task_logger
from core import archive

logger = get_task_logger(__name__)


@shared_task
def archive_url_async(noticia_id):
    try:
        noticia = Noticia.objects.get(pk=noticia_id)
        archive_url, archive_metadata = archive.capture(noticia.enlace)
        noticia.archivo_url = archive_url
        noticia.archivo_imagen = archive_metadata.get("screenshot_url")
        noticia.archivo_fecha = archive_metadata.get("archive_date")
        noticia.save(update_fields=["archivo_url", "archivo_imagen", "archivo_fecha"])
        logger.info(f"Archived ***REMOVED***noticia.enlace***REMOVED*** to ***REMOVED***archive_url***REMOVED***")
    except archive.ArchiveInProgress as e:
        logger.warning(e)
    except archive.ArchiveFailure as e:
        logger.error(e)
    except Exception as e:
        logger.error(
            f"Error archiving ***REMOVED***noticia.enlace if 'noticia' in locals() else ''***REMOVED***: ***REMOVED***e***REMOVED***"
        )
