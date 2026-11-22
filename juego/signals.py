"""Al iniciar sesión, los votos anónimos pasan a la cuenta (sin duplicar)."""

import logging

from allauth.account.signals import user_logged_in
from django.dispatch import receiver

from .models import VotoProposicion
from .votante import CLAVE

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def reclamar_votos_proposiciones(sender, request, user, **kwargs):
    vid = request.session.get(CLAVE) if request else None
    if not vid:
        return
    ya = set(VotoProposicion.objects.filter(usuario=user).values_list("proposicion_id", flat=True))
    anonimos = VotoProposicion.objects.filter(session_key=vid)
    anonimos.filter(proposicion_id__in=ya).delete()
    n = anonimos.update(usuario=user, session_key=None)
    logger.info("Reclamados %s votos de proposiciones para %s", n, user.pk)
