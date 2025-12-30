from celery import shared_task
from celery.utils.log import get_task_logger
from core.models import Noticia, Entidad, NoticiaEntidad
from core import parse
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
    Extract entities and metadata directly from captured HTML using LLM.
    Single-step enrichment that replaces the old 2-phase approach.

    Flow:
    1. Get Noticia with captured_html
    2. Extract entities, metadata, and fix missing title/image/desc in one call
    3. Save entities and update metadata if needed

    Args:
        noticia_id: ID of the Noticia to enrich
    """
    try:
        noticia = Noticia.objects.get(id=noticia_id)

        if not noticia.captured_html:
            logger.warning(f"No captured HTML for noticia {noticia_id}")
            return None

        # Check if already processed
        if noticia.entidades.exists():
            logger.info(
                f"Noticia {noticia_id} already has entities, skipping"
            )
            return noticia_id

        logger.info(
            f"Extracting entities and metadata from HTML for noticia {noticia_id}"
        )

        # Extract everything in one LLM call
        articulo = parse.parse_noticia_from_html(noticia.captured_html)

        if not articulo:
            logger.error(
                f"Failed to parse HTML for noticia {noticia_id}"
            )
            return None

        # Update metadata if LLM found better values
        updated = False
        if articulo.titulo and (
            not noticia.meta_titulo or len(noticia.meta_titulo) < 10
        ):
            noticia.meta_titulo = articulo.titulo
            updated = True
            logger.info(
                f"Updated title for noticia {noticia_id}: {articulo.titulo}"
            )

        if articulo.imagen and not noticia.meta_imagen:
            noticia.meta_imagen = articulo.imagen
            updated = True
            logger.info(
                f"Updated image for noticia {noticia_id}: {articulo.imagen}"
            )

        if articulo.descripcion and not noticia.meta_descripcion:
            noticia.meta_descripcion = articulo.descripcion
            updated = True
            logger.info(
                f"Updated description for noticia {noticia_id}"
            )

        if updated:
            noticia.save()

        # Save entities if found
        if articulo.entidades:
            for entidad_nombrada in articulo.entidades:
                logger.info(
                    f"Found entity: {entidad_nombrada.nombre} "
                    f"({entidad_nombrada.tipo}, "
                    f"{entidad_nombrada.sentimiento})"
                )

                entidad, _ = Entidad.objects.get_or_create(
                    nombre=entidad_nombrada.nombre,
                    tipo=entidad_nombrada.tipo
                )

                NoticiaEntidad.objects.get_or_create(
                    noticia=noticia,
                    entidad=entidad,
                    defaults={"sentimiento": entidad_nombrada.sentimiento}
                )

            logger.info(
                f"Saved {len(articulo.entidades)} entities for "
                f"noticia {noticia_id}"
            )
        else:
            logger.info(f"No entities found in noticia {noticia_id}")

        return noticia_id

    except Noticia.DoesNotExist:
        logger.error(f"Noticia {noticia_id} does not exist")
        return None
    except Exception as e:
        logger.exception(
            f"Unexpected error in enrich_from_captured_html for "
            f"noticia {noticia_id}: {e}"
        )
        return None


