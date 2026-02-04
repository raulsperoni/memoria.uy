import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from core.models import (
    Noticia,
    ReengagementEmailLog,
    UserProfile,
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


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_reengagement_emails_skips_recent_recipients():
    """
    Test that users who received a reengagement email recently
    are not sent another one within min_days_between_emails.
    """
    # Create an inactive user with pending news
    user = User.objects.create_user(
        username="inactive3",
        email="inactive3@example.com",
        password="pass1234",
    )
    user.last_login = timezone.now() - timezone.timedelta(days=10)
    user.save()

    # Create a pending noticia
    noticia = Noticia.objects.create(enlace="https://example.com/4")
    
    # User has an old vote (inactive)
    vote = Voto.objects.create(usuario=user, noticia=noticia, opinion="buena")
    Voto.objects.filter(pk=vote.pk).update(
        fecha_voto=timezone.now() - timezone.timedelta(days=10)
    )
    
    # Create another noticia the user hasn't voted on
    Noticia.objects.create(enlace="https://example.com/5")

    # Log that this user received an email 3 days ago (less than 7 days)
    ReengagementEmailLog.objects.create(
        user=user,
        email_type="reengagement"
    )
    # Backdate the log to 3 days ago
    ReengagementEmailLog.objects.filter(user=user).update(
        sent_at=timezone.now() - timezone.timedelta(days=3)
    )

    # Try to send reengagement emails (should skip this user)
    result = send_reengagement_emails(days_inactive=7, min_days_between_emails=7)

    assert result["sent"] == 0
    assert result["skipped"] == 0  # User is filtered out before email sending
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_reengagement_emails_sends_after_threshold():
    """
    Test that users who received a reengagement email more than
    min_days_between_emails ago CAN receive another one.
    """
    # Create an inactive user with pending news
    user = User.objects.create_user(
        username="inactive4",
        email="inactive4@example.com",
        password="pass1234",
    )
    user.last_login = timezone.now() - timezone.timedelta(days=10)
    user.save()

    # Create a pending noticia
    noticia = Noticia.objects.create(enlace="https://example.com/6")
    
    # User has an old vote (inactive)
    vote = Voto.objects.create(usuario=user, noticia=noticia, opinion="buena")
    Voto.objects.filter(pk=vote.pk).update(
        fecha_voto=timezone.now() - timezone.timedelta(days=10)
    )
    
    # Create another noticia the user hasn't voted on
    Noticia.objects.create(enlace="https://example.com/7")

    # Log that this user received an email 8 days ago (more than 7 days)
    ReengagementEmailLog.objects.create(
        user=user,
        email_type="reengagement"
    )
    # Backdate the log to 8 days ago
    ReengagementEmailLog.objects.filter(user=user).update(
        sent_at=timezone.now() - timezone.timedelta(days=8)
    )

    # Try to send reengagement emails (should send to this user)
    result = send_reengagement_emails(days_inactive=7, min_days_between_emails=7, notify_staff=False)

    assert result["sent"] == 1
    assert result["skipped"] == 0
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["inactive4@example.com"]
    
    # Verify that a new log entry was created
    assert ReengagementEmailLog.objects.filter(user=user).count() == 2


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_reengagement_emails_skips_when_reengagement_disabled():
    """Users with reengagement_email_enabled=False are not sent the email."""
    user = User.objects.create_user(
        username="optedout",
        email="optedout@example.com",
        password="pass1234",
    )
    user.last_login = timezone.now() - timezone.timedelta(days=10)
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"reengagement_email_enabled": True})
    profile.reengagement_email_enabled = False
    profile.save()

    Noticia.objects.create(enlace="https://example.com/8")

    result = send_reengagement_emails(days_inactive=7, notify_staff=False)

    assert result["sent"] == 0
    assert result["skipped"] == 0
    assert len(mail.outbox) == 0
