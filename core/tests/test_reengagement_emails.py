import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from core.models import (
    Noticia,
    VoterCluster,
    VoterClusterMembership,
    VoterClusterRun,
    Voto,
)
from core.tasks import send_reengagement_emails


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_reengagement_emails_sends_to_inactive_user():
    user = User.objects.create_user(
        username="inactive",
        email="inactive@example.com",
        password="pass1234",
    )
    user.last_login = timezone.now() - timezone.timedelta(days=10)
    user.save()

    noticia_1 = Noticia.objects.create(enlace="https://example.com/1")
    noticia_2 = Noticia.objects.create(enlace="https://example.com/2")

    vote = Voto.objects.create(usuario=user, noticia=noticia_1, opinion="buena")
    Voto.objects.filter(pk=vote.pk).update(
        fecha_voto=timezone.now() - timezone.timedelta(days=10)
    )

    run = VoterClusterRun.objects.create(
        status="completed",
        completed_at=timezone.now() - timezone.timedelta(hours=1),
    )
    cluster = VoterCluster.objects.create(
        run=run,
        cluster_id=1,
        cluster_type="group",
        size=10,
        centroid_x=0.0,
        centroid_y=0.0,
        llm_name="La Pragmatica",
    )
    VoterClusterMembership.objects.create(
        cluster=cluster,
        voter_type="user",
        voter_id=str(user.id),
        distance_to_centroid=0.1,
    )

    staff_user = User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="pass1234",
        is_staff=True,
    )

    result = send_reengagement_emails(days_inactive=7)

    assert result["sent"] == 1
    assert result["skipped"] == 0
    assert result["staff_notified"] is True
    assert len(mail.outbox) == 2

    message = mail.outbox[0].body
    assert "Tenes 1 noticias para votar." in message
    assert "Las burbujas actuales son: La Pragmatica." in message
    assert "Tu burbuja actual es: La Pragmatica." in message
    assert mail.outbox[1].to == [staff_user.email]
    assert "inactive@example.com" in mail.outbox[1].body


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_reengagement_emails_skips_when_no_pending_news():
    user = User.objects.create_user(
        username="inactive2",
        email="inactive2@example.com",
        password="pass1234",
    )
    user.last_login = timezone.now() - timezone.timedelta(days=10)
    user.save()

    noticia = Noticia.objects.create(enlace="https://example.com/3")
    vote = Voto.objects.create(usuario=user, noticia=noticia, opinion="neutral")
    Voto.objects.filter(pk=vote.pk).update(
        fecha_voto=timezone.now() - timezone.timedelta(days=10)
    )

    result = send_reengagement_emails(days_inactive=7)

    assert result["sent"] == 0
    assert result["skipped"] == 1
    assert result["staff_notified"] is False
    assert len(mail.outbox) == 0
