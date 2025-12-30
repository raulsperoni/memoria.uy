"""Tests for vote claiming functionality."""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from core.models import Noticia, Voto

User = get_user_model()


@pytest.mark.django_db
class TestVoteClaiming:
    """Test vote claiming from session to user account."""

    def test_claim_session_votes_success(self):
        """Successfully claim votes from a session."""
        # Create user and session data
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        session_key = "test_session_123"

        # Create news articles
        noticia1 = Noticia.objects.create(
            enlace="https://example.com/news1"
        )
        noticia2 = Noticia.objects.create(
            enlace="https://example.com/news2"
        )

        # Create session votes
        Voto.objects.create(
            noticia=noticia1, session_key=session_key, opinion="buena"
        )
        Voto.objects.create(
            noticia=noticia2, session_key=session_key, opinion="mala"
        )

        # Claim votes
        count = Voto.claim_session_votes(user, session_key)

        assert count == 2

        # Verify votes are now linked to user
        user_votes = Voto.objects.filter(usuario=user)
        assert user_votes.count() == 2
        assert all(v.session_key is None for v in user_votes)
        assert all(v.usuario == user for v in user_votes)

    def test_claim_session_votes_no_votes(self):
        """Claiming from session with no votes returns 0."""
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        count = Voto.claim_session_votes(user, "nonexistent_session")
        assert count == 0

    def test_claim_session_votes_conflict(self):
        """Cannot claim votes if user already voted on same articles."""
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        session_key = "test_session_123"

        # Create news article
        noticia = Noticia.objects.create(enlace="https://example.com/news1")

        # User already has a vote on this article
        Voto.objects.create(noticia=noticia, usuario=user, opinion="buena")

        # Session also has a vote on same article
        Voto.objects.create(
            noticia=noticia, session_key=session_key, opinion="mala"
        )

        # Should raise ValidationError
        with pytest.raises(ValidationError):
            Voto.claim_session_votes(user, session_key)

    def test_claim_session_votes_preserves_opinions(self):
        """Claimed votes preserve their original opinions."""
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        session_key = "test_session_123"

        noticia = Noticia.objects.create(enlace="https://example.com/news1")
        Voto.objects.create(
            noticia=noticia, session_key=session_key, opinion="neutral"
        )

        Voto.claim_session_votes(user, session_key)

        vote = Voto.objects.get(usuario=user, noticia=noticia)
        assert vote.opinion == "neutral"
