# api_views.py - API endpoints for browser extension

from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import IntegrityError
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
from django.core.exceptions import ValidationError
from core.models import Noticia, Voto
from core import parse
from core.views import get_voter_identifier
import json
import logging
import validators
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Blacklist de dominios conocidos por spam/malware
BLACKLISTED_DOMAINS = [
    'spam.com',
    'malware.net',
    'example-spam.org',
    # Añadir más según sea necesario
]

# TLDs sospechosos comunes en spam
SUSPICIOUS_TLDS = [
    '.ru', '.cn', '.tk', '.ml', '.ga', '.cf', '.gq',
]


def validate_noticia_url(url):
    """
    Valida que la URL sea legítima y segura.
    
    Raises:
        ValidationError: Si la URL no es válida
    
    Returns:
        bool: True si la URL es válida
    """
    # 1. Validar formato de URL
    if not validators.url(url):
        raise ValidationError("URL inválida. Por favor proporciona una URL válida.")
    
    # 2. Requiere HTTPS (seguridad)
    if not url.startswith('https://'):
        raise ValidationError("Solo se permiten URLs HTTPS. La URL debe comenzar con https://")
    
    # 3. Verificar dominio no está en blacklist
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        raise ValidationError("No se pudo extraer el dominio de la URL.")
    
    if any(blacklisted in domain for blacklisted in BLACKLISTED_DOMAINS):
        raise ValidationError("Este dominio no está permitido.")
    
    # 4. Verificar TLDs sospechosos
    if any(url.lower().endswith(tld) for tld in SUSPICIOUS_TLDS):
        logger.warning(f"Suspicious TLD detected in URL: {url}")
        # No bloquear automáticamente, solo loggear por ahora
        # En producción se podría enviar a moderación
    
    # 5. Validar longitud razonable
    if len(url) > 2000:
        raise ValidationError("La URL es demasiado larga.")
    
    return True


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ratelimit(key='ip', rate='10/h', method='POST'), name='dispatch')
@method_decorator(ratelimit(key='header:x-extension-session', rate='20/h', method='POST'), name='dispatch')
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
        logger.info("=" * 60)
        logger.info("[Extension API] Submit from extension called")

        try:
            # Parse JSON body
            data = json.loads(request.body)
            url = data.get("url")
            html = data.get("html")
            vote_opinion = data.get("vote")
            title = data.get("title", "")
            metadata = data.get("metadata", {})

            logger.info(f"[Extension API] URL: {url}")
            logger.info(f"[Extension API] Vote: {vote_opinion}")
            logger.info(f"[Extension API] HTML length: {len(html) if html else 0}")

            # Validate required fields
            if not url:
                return JsonResponse({"error": "URL es requerida"}, status=400)

            if not html:
                return JsonResponse({"error": "HTML es requerido"}, status=400)

            if vote_opinion not in ["buena", "mala", "neutral"]:
                return JsonResponse(
                    {"error": "Voto inválido. Usa: buena, mala o neutral"}, status=400
                )
            
            # Validate URL security and format
            try:
                validate_noticia_url(url)
            except ValidationError as e:
                logger.warning(f"[Extension API] Invalid URL rejected: {url} - {str(e)}")
                return JsonResponse({"error": str(e)}, status=400)

            # Get voter identifier (handles extension/Django session priority)
            voter_data, lookup_data = get_voter_identifier(request)
            logger.info(f"[Extension API] Voter data: {voter_data}")
            logger.info(f"[Extension API] Lookup data: {lookup_data}")

            if not lookup_data.get("session_key") and not voter_data.get("usuario"):
                logger.error("[Extension API] No session ID or user provided!")
                return JsonResponse(
                    {"error": "Session ID es requerido"}, status=400
                )

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
                    if len(meta_title) > 255:
                        logger.warning(
                            f"meta_title too long ({len(meta_title)}), "
                            f"skipping: {meta_title[:100]}..."
                        )
                    else:
                        noticia.meta_titulo = meta_title
                        updated = True

                if meta_image and not noticia.meta_imagen:
                    if len(meta_image) > 500:
                        logger.warning(
                            f"meta_image URL too long ({len(meta_image)}), "
                            f"skipping: {meta_image[:100]}..."
                        )
                    else:
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
                        if len(meta_title) <= 255:
                            noticia.meta_titulo = meta_title
                            updated = True

                    if meta_image and not noticia.meta_imagen:
                        if len(meta_image) <= 500:
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

            # Create or update vote (using centralized voter identifier)
            vote, vote_created = Voto.objects.update_or_create(
                noticia=noticia,
                **lookup_data,
                defaults={**voter_data, "opinion": vote_opinion}
            )

            logger.info(
                f"[Extension API] Vote {'created' if vote_created else 'updated'}: "
                f"{vote.id}"
            )

            # Trigger background task for LLM enrichment
            if noticia.captured_html and not noticia.entidades.exists():
                from core.tasks import enrich_from_captured_html

                enrich_from_captured_html.delay(noticia.id)
                logger.info(
                    f"[Extension API] Triggered LLM enrichment for noticia {noticia.id}"
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


@method_decorator(ratelimit(key='ip', rate='300/h', method='GET'), name='dispatch')
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

        # Get voter identifier (handles extension/Django session priority)
        voter_data, lookup_data = get_voter_identifier(request)

        # Check for vote using lookup_data
        vote = Voto.objects.filter(noticia=noticia, **lookup_data).first()

        if vote:
            return JsonResponse(
                {"voted": True, "opinion": vote.opinion, "noticia_id": noticia.id}
            )
        else:
            return JsonResponse({"voted": False, "noticia_id": noticia.id})
