import pytest
from django.urls import reverse

@pytest.mark.django_db
class TestViews:
    """Test cases for views."""
    
    def test_homepage_authenticated(self, authenticated_client):
        """Test that authenticated users can access the homepage."""
        url = reverse('home')
        response = authenticated_client.get(url)
        assert response.status_code == 200
    
    def test_admin_access(self, admin_client):
        """Test that admin users can access the admin page."""
        url = reverse('admin:index')
        response = admin_client.get(url)
        assert response.status_code == 200
    
    def test_admin_access_denied(self, authenticated_client):
        """Test that regular users cannot access the admin page."""
        url = reverse('admin:index')
        response = authenticated_client.get(url)
        assert response.status_code == 302  # Redirect to login page
