"""
Signal handlers for the core app.
Handles vote reclaim when users login.
"""
import logging
from django.dispatch import receiver
from allauth.account.signals import user_logged_in
from core.models import Voto

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def reclaim_session_votes(sender, request, user, **kwargs):
    """
    When a user logs in, reclaim any votes they made while anonymous.
    This maintains vote continuity across anonymous and authenticated states.

    Priority: Authenticated user votes take precedence over session votes.
    """
    logger.info("=" * 60)
    logger.info(f"[Vote Reclaim] User logged in: {user.username}")

    # Get session key from extension or Django session
    extension_session = request.headers.get("X-Extension-Session")
    if not extension_session:
        extension_session = request.COOKIES.get("memoria_extension_session")

    session_key = extension_session or request.session.session_key

    if not session_key:
        logger.info("[Vote Reclaim] No session key found, nothing to reclaim")
        return

    logger.info(f"[Vote Reclaim] Session key: {session_key}")

    # Find all votes made with this session
    session_votes = Voto.objects.filter(session_key=session_key)
    total_votes = session_votes.count()

    logger.info(f"[Vote Reclaim] Found {total_votes} session votes to process")

    reclaimed = 0
    skipped = 0

    for vote in session_votes:
        # Check if user already has a vote on this noticia
        existing_vote = Voto.objects.filter(
            usuario=user, noticia=vote.noticia
        ).first()

        if existing_vote:
            # User already voted on this article - keep user vote, delete session vote
            logger.info(
                f"[Vote Reclaim] Skipping noticia {vote.noticia.id} "
                f"(user already voted)"
            )
            vote.delete()
            skipped += 1
        else:
            # Reclaim the session vote by assigning it to the user
            vote.usuario = user
            vote.session_key = None
            vote.save()
            logger.info(
                f"[Vote Reclaim] Reclaimed vote on noticia {vote.noticia.id}"
            )
            reclaimed += 1

    logger.info(
        f"[Vote Reclaim] Complete: {reclaimed} reclaimed, "
        f"{skipped} skipped (user already voted)"
    )
    logger.info("=" * 60)
