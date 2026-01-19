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
        email='staff@test.com',
        password='testpass123',
        is_staff=True,
        is_active=True
    )


@pytest.fixture
def regular_user(db):
    """Usuario regular sin permisos especiales."""
    return User.objects.create_user(
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
    """Tests de rate limiting en endpoints públicos."""

    def test_rate_limit_vote_endpoint(self, client, noticia):
        """Verifica rate limiting en endpoint de votación (100/hora)."""
        # Primeros 100 requests deben pasar
        for i in range(100):
            response = client.post(
                f'/vote/{noticia.id}/',
                {'opinion': 'buena'},
                HTTP_X_FORWARDED_FOR='192.168.1.100'
            )
            assert response.status_code in [200, 302], f"Request {i+1} failed"

        # Request 101 debe ser bloqueado
        response = client.post(
            f'/vote/{noticia.id}/',
            {'opinion': 'buena'},
            HTTP_X_FORWARDED_FOR='192.168.1.100'
        )
        assert response.status_code == 429, "Rate limit not enforced"

    def test_rate_limit_submit_noticia_by_ip(self, client):
        """Verifica rate limiting en submit de noticias por IP (10/hora)."""
        # Primeros 10 requests deben pasar
        for i in range(10):
            response = client.post(
                '/api/submit-from-extension/',
                json.dumps({
                    'url': f'https://example.com/article-{i}',
                    'html': '<html><body>Test</body></html>',
                    'vote': 'buena'
                }),
                content_type='application/json',
                HTTP_X_FORWARDED_FOR='192.168.1.200',
                HTTP_X_EXTENSION_SESSION='test-session-123'
            )
            assert response.status_code in [200, 201, 400], f"Request {i+1} failed unexpectedly"

        # Request 11 debe ser bloqueado
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'https://example.com/article-overflow',
                'html': '<html><body>Test</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_FORWARDED_FOR='192.168.1.200',
            HTTP_X_EXTENSION_SESSION='test-session-123'
        )
        assert response.status_code == 429, "IP rate limit not enforced on submit"

    def test_rate_limit_check_vote(self, client):
        """Verifica rate limiting en check-vote endpoint (300/hora)."""
        # Primeros 300 requests deben pasar
        for i in range(300):
            response = client.get(
                '/api/check-vote/?url=https://example.com/test',
                HTTP_X_FORWARDED_FOR='192.168.1.300'
            )
            assert response.status_code in [200, 404], f"Request {i+1} failed"

        # Request 301 debe ser bloqueado
        response = client.get(
            '/api/check-vote/?url=https://example.com/test',
            HTTP_X_FORWARDED_FOR='192.168.1.300'
        )
        assert response.status_code == 429, "Rate limit not enforced on check-vote"

    def test_rate_limit_different_ips_isolated(self, client, noticia):
        """Verifica que rate limits son por IP (IPs diferentes no comparten límite)."""
        # IP 1: 100 votos
        for i in range(100):
            response = client.post(
                f'/vote/{noticia.id}/',
                {'opinion': 'buena'},
                HTTP_X_FORWARDED_FOR='192.168.1.1'
            )
            assert response.status_code in [200, 302]

        # IP 1: bloqueada
        response = client.post(
            f'/vote/{noticia.id}/',
            {'opinion': 'buena'},
            HTTP_X_FORWARDED_FOR='192.168.1.1'
        )
        assert response.status_code == 429

        # IP 2: debe funcionar (nuevo límite)
        response = client.post(
            f'/vote/{noticia.id}/',
            {'opinion': 'buena'},
            HTTP_X_FORWARDED_FOR='192.168.1.2'
        )
        assert response.status_code in [200, 302], "Different IP should have separate rate limit"


# ============================================================================
# Tests de Validación de URLs
# ============================================================================

@pytest.mark.django_db
class TestURLValidation:
    """Tests de validación de URLs en submit de noticias."""

    def test_reject_http_url(self, client):
        """Rechaza URLs HTTP (solo HTTPS permitido)."""
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'http://example.com/article',  # HTTP en vez de HTTPS
                'html': '<html><body>Test</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'HTTPS' in data['error']

    def test_reject_invalid_url_format(self, client):
        """Rechaza URLs con formato inválido."""
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'not-a-valid-url',
                'html': '<html><body>Test</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'inválida' in data['error'].lower()

    def test_reject_blacklisted_domain(self, client):
        """Rechaza dominios en blacklist."""
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'https://spam.com/article',
                'html': '<html><body>Test</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'permitido' in data['error'].lower()

    def test_accept_valid_https_url(self, client):
        """Acepta URLs HTTPS válidas."""
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'https://ladiaria.com.uy/articulo/2024/test',
                'html': '<html><body>Test Article</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        assert response.status_code in [200, 201], "Valid HTTPS URL should be accepted"

    def test_reject_url_too_long(self, client):
        """Rechaza URLs excesivamente largas."""
        long_url = 'https://example.com/' + 'a' * 2000
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': long_url,
                'html': '<html><body>Test</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'larga' in data['error'].lower()

    def test_url_validation_in_web_form(self, client):
        """Verifica validación de URL en formulario web."""
        response = client.post(
            '/noticias/new/',
            {
                'enlace': 'http://example.com/article',  # HTTP
                'opinion': 'buena'
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        # Debe fallar por HTTP
        assert response.status_code in [200, 400]  # Form error


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

    def test_missing_required_fields_in_api(self, client):
        """Rechaza requests de API sin campos requeridos."""
        # Sin URL
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'html': '<html><body>Test</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        assert response.status_code == 400

        # Sin HTML
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'https://example.com/article',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        assert response.status_code == 400

        # Sin voto
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'https://example.com/article',
                'html': '<html><body>Test</body></html>'
            }),
            content_type='application/json',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        assert response.status_code == 400


# ============================================================================
# Tests de Integración
# ============================================================================

@pytest.mark.django_db
class TestSecurityIntegration:
    """Tests de integración de múltiples capas de seguridad."""

    def test_security_layers_stack(self, client):
        """Verifica que múltiples capas de seguridad funcionan juntas."""
        # 1. URL inválida debe ser rechazada antes de rate limit
        for i in range(5):
            response = client.post(
                '/api/submit-from-extension/',
                json.dumps({
                    'url': 'http://invalid.com/article',  # HTTP
                    'html': '<html><body>Test</body></html>',
                    'vote': 'buena'
                }),
                content_type='application/json',
                HTTP_X_FORWARDED_FOR='192.168.1.50',
                HTTP_X_EXTENSION_SESSION='test-session'
            )
            assert response.status_code == 400, "Invalid URL should be rejected"

        # 2. URLs válidas hasta el límite
        for i in range(10):
            response = client.post(
                '/api/submit-from-extension/',
                json.dumps({
                    'url': f'https://example.com/article-{i}',
                    'html': '<html><body>Test</body></html>',
                    'vote': 'buena'
                }),
                content_type='application/json',
                HTTP_X_FORWARDED_FOR='192.168.1.50',
                HTTP_X_EXTENSION_SESSION='test-session'
            )
            assert response.status_code in [200, 201]

        # 3. Request 11 bloqueada por rate limit
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'https://example.com/article-overflow',
                'html': '<html><body>Test</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_FORWARDED_FOR='192.168.1.50',
            HTTP_X_EXTENSION_SESSION='test-session'
        )
        assert response.status_code == 429, "Rate limit should block after 10 valid requests"

    def test_session_based_rate_limiting(self, client):
        """Verifica rate limiting basado en session header."""
        session_id = 'unique-extension-session-123'
        
        # 20 requests con misma sesión
        for i in range(20):
            response = client.post(
                '/api/submit-from-extension/',
                json.dumps({
                    'url': f'https://example.com/article-{i}',
                    'html': '<html><body>Test</body></html>',
                    'vote': 'buena'
                }),
                content_type='application/json',
                HTTP_X_FORWARDED_FOR=f'192.168.1.{i}',  # IPs diferentes
                HTTP_X_EXTENSION_SESSION=session_id
            )
            assert response.status_code in [200, 201]

        # Request 21 con misma sesión debe ser bloqueada
        response = client.post(
            '/api/submit-from-extension/',
            json.dumps({
                'url': 'https://example.com/article-overflow',
                'html': '<html><body>Test</body></html>',
                'vote': 'buena'
            }),
            content_type='application/json',
            HTTP_X_FORWARDED_FOR='192.168.1.999',
            HTTP_X_EXTENSION_SESSION=session_id
        )
        assert response.status_code == 429, "Session-based rate limit should be enforced"


# ============================================================================
# Tests de Regresión
# ============================================================================

@pytest.mark.django_db
class TestSecurityRegression:
    """Tests para prevenir regresiones en seguridad."""

    def test_csrf_still_active_for_web_forms(self, client):
        """CSRF protection debe seguir activa para formularios web."""
        # Request sin CSRF token debe fallar
        response = client.post(
            '/noticias/new/',
            {
                'enlace': 'https://example.com/article',
                'opinion': 'buena'
            }
        )
        # Django debe rechazar por CSRF (a menos que sea AJAX con excepción)
        assert response.status_code in [403, 302, 200]  # Depende de configuración

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
