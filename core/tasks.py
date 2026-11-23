"""Tareas compartidas: el lock que usan archivo y juego, y el resumen diario para staff."""

from datetime import timedelta
from functools import wraps

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import get_connection, send_mail
from django.utils import timezone

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

            lock_key = (
                f"task_lock:{task_name}:{':'.join(lock_args)}:{':'.join(lock_kwargs)}"
            )

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
                logger.info(
                    f"Task {task_name} with args {args} and kwargs {kwargs} is already running. Skipping."
                )
                return None

        return wrapper

    return decorator


@shared_task
@task_lock(timeout=60 * 30)
def send_daily_staff_summary():
    """Email diario a staff: usuarios nuevos, votos del día y métricas del archivo."""
    from juego.models import VotoProposicion

    now = timezone.now()
    yesterday = now - timedelta(days=1)

    User = get_user_model()
    new_users = User.objects.filter(date_joined__gte=yesterday).order_by("-date_joined")
    new_users_count = new_users.count()
    new_votes_count = VotoProposicion.objects.filter(creado_en__gte=yesterday).count()

    staff_emails = list(
        User.objects.filter(is_active=True, is_staff=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not staff_emails:
        logger.info("No staff emails found for daily summary")
        return {"sent": False, "reason": "no_staff_emails"}

    site_url = getattr(settings, "SITE_URL", "https://memoria.uy")
    subject = f"Resumen diario - {now.strftime('%d/%m/%Y')}"

    lines = [
        f"Resumen diario de memoria.uy - {now.strftime('%d/%m/%Y %H:%M')}",
        "",
        f"Usuarios nuevos: {new_users_count}",
    ]
    for user in new_users[:10]:
        lines.append(f"  • {user.get_full_name().strip() or user.email} ({user.email})")
    if new_users_count > 10:
        lines.append(f"  ... y {new_users_count - 10} más")
    lines += ["", f"Votos nuevos: {new_votes_count}"]

    html_lines = [
        f"<h2>Resumen diario de memoria.uy - {now.strftime('%d/%m/%Y %H:%M')}</h2>",
        f"<h3>Usuarios nuevos: {new_users_count}</h3>",
    ]
    if new_users_count:
        html_lines.append("<ul>")
        for user in new_users[:10]:
            html_lines.append(f"<li>{user.get_full_name().strip() or user.email} ({user.email})</li>")
        html_lines.append("</ul>")
    html_lines.append(f"<h3>Votos nuevos: {new_votes_count}</h3>")

    try:
        from archivo.metricas import lineas_html, lineas_texto, resumen_ingesta

        resumen_archivo = resumen_ingesta()
        lines.extend(lineas_texto(resumen_archivo))
        html_lines.extend(lineas_html(resumen_archivo))
    except Exception as exc:  # el resumen no debe fallar por el archivo
        logger.error(f"Resumen de archivo falló: {exc}")

    lines += ["", f"Ver más en: {site_url}"]
    html_lines.append(f'<hr><p><a href="{site_url}">Ver más en memoria.uy</a></p>')

    try:
        send_mail(
            subject=subject,
            message="\n".join(lines),
            html_message="".join(html_lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=staff_emails,
            connection=get_connection(),
        )
        logger.info(f"Daily staff summary sent. Usuarios={new_users_count}, Votos={new_votes_count}")
        return {"sent": True, "usuarios_count": new_users_count, "votos_count": new_votes_count}
    except Exception as exc:
        logger.error(f"Failed to send daily staff summary email: {exc}")
        return {"sent": False, "error": str(exc)}
