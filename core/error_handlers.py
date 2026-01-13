"""
Custom error handlers for Django.
Generates pre-filled GitHub issue links for error reporting.
"""
import traceback
import logging
from urllib.parse import quote
from django.shortcuts import render
from django.conf import settings
import uuid

logger = logging.getLogger(__name__)


def get_github_issue_url(
    title, body, labels=None, repo="raulsperoni/memoria.uy"
):
    """
    Generate a GitHub issue URL with pre-filled content.

    Args:
        title: Issue title
        body: Issue body (markdown supported)
        labels: List of label names
        repo: GitHub repo in format 'owner/repo'

    Returns:
        Full GitHub URL with query parameters
    """
    base_url = f"https://github.com/{repo}/issues/new"
    params = [
        f"title={quote(title)}",
        f"body={quote(body)}",
    ]

    if labels:
        params.append(f"labels={quote(','.join(labels))}")

    return f"{base_url}?{'&'.join(params)}"


def server_error(request, *args, **kwargs):
    """
    Custom 500 error handler.
    Generates a unique error ID and GitHub issue link.
    """
    error_id = str(uuid.uuid4())[:8]

    try:
        # Get exception info if available
        exc_type, exc_value, exc_traceback = None, None, None
        if hasattr(request, "resolver_match"):
            import sys

            exc_type, exc_value, exc_traceback = sys.exc_info()

        # Log the error
        logger.error(
            f"[Error {error_id}] 500 error on {request.path}",
            exc_info=(exc_type, exc_value, exc_traceback),
            extra={
                "error_id": error_id,
                "path": request.path,
                "method": request.method,
                "user": (
                    request.user.username
                    if hasattr(request, "user")
                    and request.user.is_authenticated
                    else "anonymous"
                ),
            },
        )

        # Generate GitHub issue content
        title = f"[BUG] Error 500 en {request.path}"
        body_parts = [
            "## Error Automático desde memoria.uy",
            "",
            f"**Error ID:** `{error_id}`",
            f"**URL:** `{request.path}`",
            f"**Método:** `{request.method}`",
            "",
            "## Descripción del Usuario",
            "<!-- Por favor describí qué estabas haciendo cuando "
            "ocurrió el error -->",
            "",
            "",
            "## Información Técnica",
            "",
        ]

        if exc_type and exc_value:
            body_parts.extend(
                [
                    f"**Excepción:** `{exc_type.__name__}`",
                    f"**Mensaje:** `{exc_value}`",
                    "",
                ]
            )

            if exc_traceback and settings.DEBUG:
                tb_lines = traceback.format_tb(exc_traceback)
                body_parts.extend(
                    [
                        "**Stack Trace:**",
                        "```python",
                        "".join(tb_lines),
                        "```",
                    ]
                )

        body = "\n".join(body_parts)
        github_url = get_github_issue_url(
            title=title, body=body, labels=["bug", "auto-generated"]
        )

        # Debug info (only shown in DEBUG mode)
        debug_info = None
        if settings.DEBUG and exc_type:
            debug_parts = [
                f"Error Type: {exc_type.__name__}",
                f"Message: {exc_value}",
                "",
                "Traceback:",
            ]
            if exc_traceback:
                debug_parts.extend(traceback.format_tb(exc_traceback))
            debug_info = "\n".join(debug_parts)

        context = {
            "error_id": error_id,
            "github_issue_url": github_url,
            "debug_info": debug_info,
        }

        return render(request, "500.html", context, status=500)

    except Exception as e:
        # Fallback if error handler itself fails
        logger.error(f"Error handler failed: {e}", exc_info=True)
        return render(
            request,
            "500.html",
            {"error_id": error_id, "github_issue_url": None},
            status=500,
        )
