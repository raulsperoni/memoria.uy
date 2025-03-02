import pytest
from django.urls import reverse
from django.test import Client

@pytest.fixture
def client():
    return Client()

def test_homepage_status(client):
    """Test that the homepage returns a 200 status code."""
    url = reverse('home')
    response = client.get(url)
    assert response.status_code == 200

def test_admin_login_page(client):
    """Test that the admin login page is accessible."""
    url = reverse('admin:login')
    response = client.get(url)
    assert response.status_code == 200
