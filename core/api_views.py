# api_views.py - API endpoints for browser extension

from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import IntegrityError
from core.models import Noticia, Voto
from core import parse
import json
import logging

logger = logging.getLogger(__name__)


def get_extension_session_id(request):
    """Extract session ID from extension header."""
    return request.headers.get("X-Extension-Session")


@method_decorator(csrf_exempt, name="dispatch")
class SubmitFromExtensionView(View):
    """
    API endpoint to receive article HTML and vote from browser extension.

    Expected JSON payload:
    {
        "url": "https://example.com/article",
        "title": "Article Title",
        "html": "<html>...</html>",
        "vote": "buena|mala|neutral"
    }
    """

    def post(self, request):
        try:
            # Parse JSON body
            data = json.loads(request.body)
            url = data.get("url")
            html = data.get("html")
            vote_opinion = data.get("vote")
            title = data.get("title", "")
            metadata = data.get("metadata", {})

            # Validate required fields
            if not url:
                return JsonResponse({"error": "URL es requerida"}, status=400)

            if not html:
                return JsonResponse({"error": "HTML es requerido"}, status=400)

            if vote_opinion not in ["buena", "mala", "neutral"]:
                return JsonResponse(
                    {"error": "Voto inválido. Usa: buena, mala o neutral"}, status=400
                )

            # Get session ID from extension
            session_id = get_extension_session_id(request)
            if not session_id:
                return JsonResponse({"error": "Session ID es requerido"}, status=400)

            # Get or create Noticia
            noticia, created = Noticia.objects.get_or_create(
                enlace=url,
                defaults={"captured_html": html, "meta_titulo": title or None},
            )

            # If noticia already exists but doesn't have HTML, update it
            if not created and not noticia.captured_html:
                noticia.captured_html = html
                noticia.save()

            # Extract metadata from extension
            updated = False

            # Use metadata from extension if available
            if metadata:
                og = metadata.get("og", {})
                twitter = metadata.get("twitter", {})

                # Extract from og: tags first, then twitter
                meta_title = (
                    og.get("title") or twitter.get("title") or metadata.get("title")
                )
                meta_image = og.get("image") or twitter.get("image")
                meta_desc = og.get("description") or twitter.get("description")

                if meta_title and (not noticia.meta_titulo or created):
                    noticia.meta_titulo = meta_title
                    updated = True

                if meta_image and not noticia.meta_imagen:
                    noticia.meta_imagen = meta_image
                    updated = True

                if meta_desc and (not noticia.meta_descripcion or created):
                    noticia.meta_descripcion = meta_desc
                    updated = True

            # Fallback: Try to extract from captured HTML
            if html and (not noticia.meta_titulo or not noticia.meta_imagen):
                try:
                    meta_title, meta_image, meta_desc = (
                        parse.parse_from_html_string(html, url)
                    )

                    if meta_title and not noticia.meta_titulo:
                        noticia.meta_titulo = meta_title
                        updated = True

                    if meta_image and not noticia.meta_imagen:
                        noticia.meta_imagen = meta_image
                        updated = True

                    if meta_desc and not noticia.meta_descripcion:
                        noticia.meta_descripcion = meta_desc
                        updated = True

                except Exception as e:
                    logger.warning(f"Failed to extract meta from HTML: {e}")

            if updated:
                noticia.save()
                logger.info(
                    f"Updated metadata for noticia {noticia.id}"
                )

            # Fallback: fetch from URL if still missing critical data
            if not noticia.meta_titulo and not noticia.meta_imagen:
                try:
                    noticia.update_meta_from_url()
                except Exception as e:
                    logger.warning(f"Failed to fetch meta from URL: {e}")

            # Create or update vote
            vote_data = {"session_key": session_id}

            # Check if user is authenticated (via cookie/token)
            if request.user.is_authenticated:
                vote_data = {"usuario": request.user}

            # Try to update existing vote or create new one
            vote, vote_created = Voto.objects.update_or_create(
                noticia=noticia, **vote_data, defaults={"opinion": vote_opinion}
            )

            # Trigger background task for LLM enrichment
            if noticia.captured_html and not noticia.markdown:
                from core.tasks import enrich_from_captured_html

                enrich_from_captured_html.delay(noticia.id)
                logger.info(
                    f"Triggered LLM enrichment for noticia {noticia.id}"
                )

            return JsonResponse(
                {
                    "success": True,
                    "noticia_id": noticia.id,
                    "vote_created": vote_created,
                    "message": (
                        "Voto actualizado" if not vote_created else "Voto registrado"
                    ),
                },
                status=201 if created else 200,
            )

        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido"}, status=400)
        except IntegrityError as e:
            logger.error(f"Database integrity error: {e}")
            return JsonResponse(
                {"error": "Error al guardar en base de datos"}, status=500
            )
        except Exception as e:
            logger.exception(f"Unexpected error in submit endpoint: {e}")
            return JsonResponse({"error": "Error interno del servidor"}, status=500)


class CheckVoteView(View):
    """
    API endpoint to check if user has already voted on a URL.

    GET /api/check-vote/?url=https://example.com/article

    Returns:
    {
        "voted": true,
        "opinion": "buena",
        "noticia_id": 123
    }
    """

    def get(self, request):
        url = request.GET.get("url")

        if not url:
            return JsonResponse({"error": "URL es requerida"}, status=400)

        # Check if noticia exists
        try:
            noticia = Noticia.objects.get(enlace=url)
        except Noticia.DoesNotExist:
            return JsonResponse({"voted": False})

        # Check for vote
        session_id = get_extension_session_id(request)

        if request.user.is_authenticated:
            # Check for authenticated user vote
            vote = Voto.objects.filter(noticia=noticia, usuario=request.user).first()
        elif session_id:
            # Check for session-based vote
            vote = Voto.objects.filter(noticia=noticia, session_key=session_id).first()
        else:
            return JsonResponse({"voted": False})

        if vote:
            return JsonResponse(
                {"voted": True, "opinion": vote.opinion, "noticia_id": noticia.id}
            )
        else:
            return JsonResponse({"voted": False, "noticia_id": noticia.id})
