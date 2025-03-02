import pytest
from django.contrib.auth.models import User
from django.urls import reverse

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
        login_url = reverse('admin:login')
        response = client.post(
            login_url,
            {'username': 'testuser', 'password': 'testpassword123'},
            follow=True
        )
        assert response.status_code == 200
        assert '_auth_user_id' in client.session
        assert int(client.session['_auth_user_id']) == user.pk
