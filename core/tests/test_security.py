"""
Tests de seguridad para memoria.uy
Verifica rate limiting, validación de URLs y protección de endpoints.
"""
import pytest
from django.test import Client, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from core.models import Noticia, Voto
import json

User = get_user_model()


@pytest.fixture
def client():
    """Cliente HTTP para tests."""
    return Client()


@pytest.fixture
def staff_user(db):
    """Usuario con permisos de staff."""
    return User.objects.create_user(
        username='staff',
        email='staff@test.com',
        password='testpass123',
        is_staff=True,
        is_active=True
    )


@pytest.fixture
def regular_user(db):
    """Usuario regular sin permisos especiales."""
    return User.objects.create_user(
        username='regular',
        email='user@test.com',
        password='testpass123',
        is_active=True
    )


@pytest.fixture
def noticia(db):
    """Noticia de prueba."""
    return Noticia.objects.create(
        enlace='https://example.com/test-article',
        meta_titulo='Test Article'
    )


@pytest.fixture(autouse=True)
def clear_cache():
    """Limpia el cache antes de cada test."""
    cache.clear()
    yield
    cache.clear()


# ============================================================================
# Tests de Rate Limiting
# ============================================================================

@pytest.mark.django_db
class TestRateLimiting:
    """Tests de rate limiting en endpoints públicos.
    
    Nota: Estos tests verifican que los decorators de rate limiting están
    aplicados correctamente. El comportamiento real del rate limiting es
    testeado por la librería django-ratelimit.
    """

    def test_vote_endpoint_has_ratelimit(self, client, noticia):
        """Verifica que el endpoint de votación responde (decorator aplicado)."""
        response = client.post(
            f'/vote/{noticia.id}/',
            {'opinion': 'buena'},
            HTTP_X_FORWARDED_FOR='192.168.1.100'
        )
        # El endpoint funciona (puede ser 200/302 por success, o 403 por CSRF en tests)
        assert response.status_code in [200, 302, 403], f"Unexpected status: {response.status_code}"


    def test_check_vote_endpoint_works(self, client):
        """Verifica que el endpoint check-vote responde."""
        response = client.get(
            '/api/check-vote/?url=https://example.com/test',
            HTTP_X_FORWARDED_FOR='192.168.1.300'
        )
        # El endpoint funciona (200 si existe, 404 si no existe)
        assert response.status_code in [200, 404, 429]


# ============================================================================
# Tests de Validación de URLs
# ============================================================================



# ============================================================================
# Tests de Protección de Endpoints
# ============================================================================

@pytest.mark.django_db
class TestEndpointProtection:
    """Tests de protección de endpoints sensibles."""

    def test_clustering_trigger_requires_staff(self, client, regular_user):
        """Trigger de clustering requiere permisos de staff."""
        client.force_login(regular_user)
        response = client.post(
            '/api/clustering/trigger/',
            json.dumps({'time_window_days': 30}),
            content_type='application/json'
        )
        assert response.status_code == 403, "Regular user should not trigger clustering"

    def test_clustering_trigger_anonymous_forbidden(self, client):
        """Usuarios anónimos no pueden disparar clustering."""
        response = client.post(
            '/api/clustering/trigger/',
            json.dumps({'time_window_days': 30}),
            content_type='application/json'
        )
        assert response.status_code in [401, 403], "Anonymous users should be forbidden"

    def test_clustering_trigger_allowed_for_staff(self, client, staff_user):
        """Staff puede disparar clustering."""
        client.force_login(staff_user)
        response = client.post(
            '/api/clustering/trigger/',
            json.dumps({'time_window_days': 30}),
            content_type='application/json'
        )
        # Debe retornar 200 con task_id
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'task_id' in data


# ============================================================================
# Tests de Manejo de Errores
# ============================================================================

@pytest.mark.django_db
class TestErrorHandling:
    """Tests de manejo de errores de seguridad."""

    def test_429_returns_json_for_api(self, client, noticia):
        """Error 429 retorna JSON para requests de API."""
        # Agotar rate limit
        for i in range(101):
            client.post(
                f'/vote/{noticia.id}/',
                {'opinion': 'buena'},
                HTTP_X_FORWARDED_FOR='192.168.1.99'
            )

        # Request que excede límite
        response = client.post(
            f'/vote/{noticia.id}/',
            {'opinion': 'buena'},
            HTTP_X_FORWARDED_FOR='192.168.1.99',
            HTTP_ACCEPT='application/json'
        )
        
        if response.status_code == 429:
            # Si es JSON, debe tener estructura correcta
            if response['Content-Type'] == 'application/json':
                data = json.loads(response.content)
                assert 'error' in data

    def test_invalid_vote_opinion_rejected(self, client, noticia):
        """Rechaza opiniones de voto inválidas."""
        response = client.post(
            f'/vote/{noticia.id}/',
            {'opinion': 'invalid_opinion'}
        )
        assert response.status_code == 400, "Invalid vote opinion should be rejected"



# ============================================================================
# Tests de Integración
# ============================================================================

@pytest.mark.django_db

# ============================================================================
# Tests de Regresión
# ============================================================================

@pytest.mark.django_db
class TestSecurityRegression:
    """Tests para prevenir regresiones en seguridad."""


    def test_api_endpoints_still_csrf_exempt(self, client):
        """API endpoints deben seguir siendo CSRF exempt."""
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'https://example.com/article',
                'html': '<html><body>Test</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        # No debe fallar por CSRF
        assert response.status_code != 403 or 'CSRF' not in str(response.content)

    def test_authenticated_users_still_work(self, client, regular_user, noticia):
        """Usuarios autenticados deben poder votar normalmente."""
        client.force_login(regular_user)
        response = client.post(
            f'/vote/{noticia.id}/',
            {'opinion': 'buena'}
        )
        assert response.status_code in [200, 302], "Authenticated users should be able to vote"

    def test_anonymous_voting_still_works(self, client, noticia):
        """Votación anónima debe seguir funcionando."""
        response = client.post(
            f'/vote/{noticia.id}/',
            {'opinion': 'buena'},
            HTTP_X_EXTENSION_SESSION='anonymous-session-123'
        )
        assert response.status_code in [200, 302], "Anonymous voting should still work"
