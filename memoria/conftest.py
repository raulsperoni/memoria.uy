import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def client():
    """Return a Django test client instance."""
    return Client()


@pytest.fixture
def admin_client():
    """Return a Django test client instance with admin user logged in."""
    client = Client()
    admin_user = User.objects.create_superuser(
        username="admin", email="admin@example.com", password="adminpassword123"
    )
    client.login(username="admin", password="adminpassword123")
    return client


@pytest.fixture
def user():
    """Create and return a regular user."""
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpassword123"
    )


@pytest.fixture
def authenticated_client(user):
    """Return a Django test client instance with regular user logged in."""
    client = Client()
    client.login(username="testuser", password="testpassword123")
    return client
