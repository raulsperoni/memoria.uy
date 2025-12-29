from celery import shared_task
from celery.utils.log import get_task_logger
from core.models import Noticia, Entidad, NoticiaEntidad
from core import parse
from core import archive_ph as archive
from datetime import datetime
from django.core.cache import cache
from functools import wraps
from core import url_requests

logger = get_task_logger(__name__)


def task_lock(timeout=60 * 10):
    """
    Decorator that prevents a task from being executed concurrently.
    Uses Django's cache to create a lock based on the task name and arguments.
    
    Args:
        timeout: Lock timeout in seconds (default: 10 minutes)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a unique lock key based on the task name and arguments
            task_name = func.__name__
            # For tasks with an ID parameter, use it as part of the lock key
            lock_args = []
            for arg in args:
                if isinstance(arg, (int, str)):
                    lock_args.append(str(arg))
            
            lock_kwargs = []
            for key, value in kwargs.items():
                if isinstance(value, (int, str)):
                    lock_kwargs.append(f"{key}:{value}")
            
            lock_key = f"task_lock:{task_name}:{':'.join(lock_args)}:{':'.join(lock_kwargs)}"
            
            # Try to acquire the lock
            acquired = cache.add(lock_key, "locked", timeout)
            
            if acquired:
                try:
                    # Execute the task
                    return func(*args, **kwargs)
                finally:
                    # Release the lock
                    cache.delete(lock_key)
            else:
                logger.info(f"Task {task_name} with args {args} and kwargs {kwargs} is already running. Skipping.")
                return None
        return wrapper
    return decorator


@shared_task
@task_lock()
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
@task_lock()
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
@task_lock()
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
    except archive.ArchiveNotFound as e:
        # If no snapshot found, try to save the URL
        logger.info(f"No snapshot found for noticia {noticia_id}, attempting to save URL")
        save_to_archive_org.delay(noticia_id)
        return None
    except Exception as e:
        logger.error(f"Error in find_archived task for noticia {noticia_id}: {e}")
        return None


@shared_task(bind=True, max_retries=3)
@task_lock()
def save_to_archive_org(self, noticia_id):
    """Async task to save a URL to the Internet Archive (archive.org).
    This task is called when no snapshot is found and we need to save the URL.
    """
    try:
        noticia = Noticia.objects.get(id=noticia_id)
        logger.info(f"Saving URL to archive.org: {noticia.enlace}")
        
        # Attempt to save the URL to archive.org
        noticia.archivo_url, html = archive.save_url(noticia.enlace)
        noticia.archivo_fecha = datetime.now()
        noticia.save()
        
        # Process the saved content
        if not noticia.markdown:
            enrich_markdown.delay(noticia.id, html)
        elif not noticia.resumen:
            enrich_content.delay(noticia.id)
        
        noticia.update_title_image_from_archive()
        logger.info(f"Successfully saved URL to archive.org for noticia {noticia_id}")
        return noticia.archivo_url
    except archive.ArchiveInProgress as e:
        retry_count = self.request.retries
        if retry_count < 2:  # We'll do a total of 3 attempts (0, 1, 2)
            logger.info(
                f"Archive save still in progress for noticia {noticia_id}, retry {retry_count+1}/3 in 5 minutes"
            )
            # Retry in 5 minutes (300 seconds)
            raise self.retry(exc=e, countdown=300)
        else:
            logger.warning(
                f"Archive save still in progress after 3 attempts for noticia {noticia_id}, giving up"
            )
            return None
    except Exception as e:
        logger.error(f"Error in save_to_archive_org task for noticia {noticia_id}: {e}")
        return None


@shared_task
@task_lock(timeout=60 * 30)  # 30 minutes lock to avoid concurrent runs
def refresh_proxy_list(max_proxies: int = 20, test_url: str = "https://www.google.com"):
    """
    Periodically refresh and validate the proxy list.
    This task should be scheduled to run at regular intervals.
    
    Args:
        max_proxies: Maximum number of proxies to validate and store
        test_url: URL to test the proxies against
        
    Returns:
        Number of working proxies found
    """
    logger.info("Starting proxy list refresh task")
    
    # First, clear the existing proxy cache to fetch fresh proxies
    url_requests.clear_proxy_cache()
    
    # Get and validate proxies
    working_proxies = url_requests.get_validated_proxies(max_proxies=max_proxies, test_url=test_url)
    
    # Update the proxy list in the url_requests module
    url_requests.update_proxy_list(working_proxies)
    
    logger.info(f"Proxy list refresh completed. Found {len(working_proxies)} working proxies")
    return len(working_proxies)


@shared_task
@task_lock()
def enrich_from_captured_html(noticia_id):
    """
    Convert captured HTML to markdown using LLM.
    This is the entry point for browser extension submissions.

    Flow:
    1. Get Noticia with captured_html
    2. Convert HTML → Markdown using LLM
    3. Save markdown to noticia

    Args:
        noticia_id: ID of the Noticia to enrich
    """
    try:
        noticia = Noticia.objects.get(id=noticia_id)

        if not noticia.captured_html:
            logger.warning(
                f"No captured HTML for noticia {noticia_id}"
            )
            return None

        if noticia.markdown:
            logger.info(
                f"Noticia {noticia_id} already has markdown, skipping"
            )
            return noticia_id

        logger.info(
            f"Converting captured HTML to markdown for noticia {noticia_id}"
        )

        # Use meta_titulo as hint for LLM
        title_hint = noticia.meta_titulo or "Article"

        # Convert HTML to markdown
        markdown = parse.parse_noticia_markdown(
            noticia.captured_html,
            title_hint
        )

        if markdown:
            noticia.markdown = markdown
            noticia.save()
            logger.info(
                f"Successfully converted HTML to markdown for "
                f"noticia {noticia_id}"
            )
            return noticia_id
        else:
            logger.error(
                f"Failed to convert HTML to markdown for noticia {noticia_id}"
            )
            return None

    except Noticia.DoesNotExist:
        logger.error(f"Noticia {noticia_id} does not exist")
        return None
    except Exception as e:
        logger.exception(
            f"Unexpected error in enrich_from_captured_html for "
            f"noticia {noticia_id}: {e}"
        )
        return None
