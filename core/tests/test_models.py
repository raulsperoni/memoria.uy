import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse

from core.models import Entidad, normalize_entity_name

@pytest.mark.django_db
class TestUserModel:
    """Test cases for the User model."""
    
    @pytest.fixture
    def user(self):
        """Create and return a test user."""
        return User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
    
    def test_user_creation(self, user):
        """Test that a user can be created."""
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.check_password('testpassword123')
        assert user.is_active
        assert not user.is_staff
        assert not user.is_superuser
    
    def test_user_str(self, user):
        """Test the string representation of a user."""
        assert str(user) == 'testuser'

@pytest.mark.django_db
class TestAuthentication:
    """Test cases for authentication functionality."""
    
    @pytest.fixture
    def user(self):
        """Create and return a test user."""
        return User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
    
    def test_login(self, client, user):
        """Test that a user can log in."""
        logged_in = client.login(username='testuser', password='testpassword123')
        assert logged_in
        
        # Visit a page that requires authentication
        response = client.get(reverse('timeline'))
        assert response.status_code == 200
        assert '_auth_user_id' in client.session
        assert int(client.session['_auth_user_id']) == user.pk


@pytest.mark.django_db
class TestEntidadNormalization:
    """Test entity name normalization and deduplication."""

    def test_normalize_entity_name_lowercase(self):
        assert normalize_entity_name("LACALLE POU") == "lacalle pou"

    def test_normalize_entity_name_removes_accents(self):
        assert normalize_entity_name("José Mujica") == "jose mujica"
        assert normalize_entity_name("María García") == "maria garcia"

    def test_normalize_entity_name_strips_whitespace(self):
        assert normalize_entity_name("  Luis  ") == "luis"

    def test_entidad_saves_normalized_name(self):
        e = Entidad.objects.create(nombre="José Mujica", tipo="persona")
        assert e.normalized_name == "jose mujica"

    def test_entidad_unique_constraint_blocks_duplicates(self):
        Entidad.objects.create(nombre="José Mujica", tipo="persona")
        with pytest.raises(IntegrityError):
            Entidad.objects.create(nombre="JOSE MUJICA", tipo="persona")

    def test_entidad_allows_same_name_different_type(self):
        e1 = Entidad.objects.create(nombre="Montevideo", tipo="lugar")
        e2 = Entidad.objects.create(nombre="Montevideo", tipo="organizacion")
        assert e1.pk != e2.pk
