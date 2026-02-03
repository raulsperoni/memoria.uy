import pytest
from django.urls import reverse

from core.models import Noticia, Voto


@pytest.mark.django_db
class TestViews:
    """Test cases for views."""

    def test_homepage_authenticated(self, authenticated_client):
        """Test that authenticated users can access the homepage."""
        url = reverse('timeline')
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


@pytest.mark.django_db
class TestTimelineFeeds:
    """Test timeline feed modes: confort, puente, avanzado."""

    def test_timeline_no_feed_defaults_to_recientes(self, client):
        """Without feed param, timeline uses recientes (chronological unvoted)."""
        response = client.get(reverse('timeline'))
        assert response.status_code == 200
        assert 'feed_mode' in response.context
        assert response.context['feed_mode'] == 'recientes'

    def test_timeline_feed_recientes_returns_200(self, client):
        """feed=recientes returns 200 (chronological unvoted)."""
        response = client.get(reverse('timeline'), {'feed': 'recientes'})
        assert response.status_code == 200
        assert response.context['feed_mode'] == 'recientes'
        assert 'feed_algorithm_description' in response.context

    def test_timeline_feed_confort_returns_200(self, client):
        """feed=confort returns 200 (comfort/afín: cluster + entities)."""
        response = client.get(reverse('timeline'), {'feed': 'confort'})
        assert response.status_code == 200
        assert response.context['feed_mode'] == 'confort'
        assert 'feed_algorithm_description' in response.context

    def test_timeline_feed_recientes_excludes_voted(self, client, user):
        """Recientes feed excludes noticias the user has already voted on."""
        noticia = Noticia.objects.create(
            enlace='https://example.com/feed-recientes-test',
            meta_titulo='Test',
        )
        client.force_login(user)
        Voto.objects.create(noticia=noticia, usuario=user, opinion='buena')
        response = client.get(reverse('timeline'), {'feed': 'recientes'})
        assert response.status_code == 200
        object_list = list(response.context['noticias'])
        assert noticia not in object_list

    def test_timeline_feed_puente_returns_200(self, client):
        """feed=puente returns 200 (may be empty if no cluster run)."""
        response = client.get(reverse('timeline'), {'feed': 'puente'})
        assert response.status_code == 200
        assert response.context['feed_mode'] == 'puente'
        assert 'feed_algorithm_description' in response.context

    def test_timeline_feed_avanzado_returns_200(self, client):
        """feed=avanzado with filter returns 200."""
        response = client.get(
            reverse('timeline'),
            {'feed': 'avanzado', 'filter': 'nuevas'},
        )
        assert response.status_code == 200
        assert response.context['feed_mode'] == 'avanzado'
        assert response.context['current_filter'] == 'nuevas'

    def test_timeline_feed_avanzado_filter_todas(self, client):
        """feed=avanzado&filter=todas shows all news."""
        Noticia.objects.create(
            enlace='https://example.com/feed-avanzado-todas-test',
            meta_titulo='All news',
        )
        response = client.get(
            reverse('timeline'),
            {'feed': 'avanzado', 'filter': 'todas'},
        )
        assert response.status_code == 200
        assert response.context['current_filter'] == 'todas'
        assert len(response.context['noticias']) >= 1

    def test_timeline_invalid_feed_falls_back_to_recientes(self, client):
        """Unknown feed param is treated as default (recientes)."""
        response = client.get(reverse('timeline'), {'feed': 'invalid'})
        assert response.status_code == 200
        assert response.context['feed_mode'] == 'recientes'
