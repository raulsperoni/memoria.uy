# test_url_normalization.py - Integration tests for URL normalization

import pytest
import json
from django.test import Client
from core.models import Noticia, Voto
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestURLNormalizationIntegration:
    """Test that URL normalization works end-to-end through the API."""
    
    def test_same_article_from_different_sources_deduplicates(self, client):
        """
        Submitting the same article with different tracking params
        should create only one Noticia record.
        """
        base_url = "https://example.com/article?id=123"
        
        # Submit from Facebook (with fbclid and utm params)
        facebook_url = f"{base_url}&utm_source=facebook&fbclid=IwAR123"
        response1 = client.post(
            "/api/submit-from-extension/",
            json.dumps({
                "url": facebook_url,
                "html": "<html><body>Article content</body></html>",
                "vote": "buena",
            }),
            content_type="application/json",
            HTTP_X_EXTENSION_SESSION="test-session-1",
        )
        
        # Submit from Twitter (with different utm params)
        twitter_url = f"{base_url}&utm_source=twitter&utm_medium=social"
        response2 = client.post(
            "/api/submit-from-extension/",
            json.dumps({
                "url": twitter_url,
                "html": "<html><body>Article content</body></html>",
                "vote": "buena",
            }),
            content_type="application/json",
            HTTP_X_EXTENSION_SESSION="test-session-2",
        )
        
        # Both requests should succeed
        assert response1.status_code in [200, 201]
        assert response2.status_code in [200, 201]
        
        # Should only create ONE noticia
        assert Noticia.objects.count() == 1
        
        # The stored URL should be normalized (no tracking params)
        noticia = Noticia.objects.first()
        assert noticia.enlace == base_url
        assert "fbclid" not in noticia.enlace
        assert "utm_source" not in noticia.enlace
        assert "utm_medium" not in noticia.enlace
        
        # Both votes should exist (different users)
        assert Voto.objects.count() == 2
    
    def test_web_form_also_normalizes(self, client):
        """Test that web form submissions also normalize URLs."""
        # Create a session-based submission via web form
        response = client.post(
            "/noticias/new/",
            data={
                "enlace": "https://example.com/news?utm_campaign=newsletter&utm_source=email",
                "opinion": "buena",
            },
        )
        
        # Should succeed (might redirect)
        assert response.status_code in [200, 302]
        
        # Should create noticia with normalized URL
        assert Noticia.objects.count() == 1
        noticia = Noticia.objects.first()
        assert noticia.enlace == "https://example.com/news"
        assert "utm_" not in noticia.enlace
    
    def test_preserves_functional_parameters(self, client):
        """Functional parameters like IDs should be preserved."""
        url_with_id = "https://example.com/article?id=456&category=tech&utm_source=app"
        
        response = client.post(
            "/api/submit-from-extension/",
            json.dumps({
                "url": url_with_id,
                "html": "<html><body>Tech article</body></html>",
                "vote": "buena",
            }),
            content_type="application/json",
            HTTP_X_EXTENSION_SESSION="test-session-3",
        )
        
        assert response.status_code in [200, 201]
        
        noticia = Noticia.objects.first()
        # Should keep id and category, remove utm_source
        assert "id=456" in noticia.enlace or "id%3D456" in noticia.enlace
        assert "category" in noticia.enlace
        assert "utm_source" not in noticia.enlace
    
    def test_removes_fragments(self, client):
        """URL fragments (anchors) should be removed."""
        url_with_fragment = "https://example.com/article?id=789#section-comments"
        
        response = client.post(
            "/api/submit-from-extension/",
            json.dumps({
                "url": url_with_fragment,
                "html": "<html><body>Article with fragment</body></html>",
                "vote": "neutral",
            }),
            content_type="application/json",
            HTTP_X_EXTENSION_SESSION="test-session-4",
        )
        
        assert response.status_code in [200, 201]
        
        noticia = Noticia.objects.first()
        assert "#" not in noticia.enlace
        assert "section-comments" not in noticia.enlace
        # But should keep the id parameter
        assert "id=789" in noticia.enlace or "id%3D789" in noticia.enlace
    
    def test_multiple_votes_on_normalized_url(self, client, django_user_model):
        """Multiple users can vote on the same normalized article."""
        # Create two users
        user1 = django_user_model.objects.create_user(
            username="user1", email="user1@test.com", password="pass"
        )
        user2 = django_user_model.objects.create_user(
            username="user2", email="user2@test.com", password="pass"
        )
        
        # User 1 submits with tracking params
        client.force_login(user1)
        response1 = client.post(
            "/api/submit-from-extension/",
            json.dumps({
                "url": "https://example.com/news?id=100&utm_source=fb",
                "html": "<html><body>News</body></html>",
                "vote": "buena",
            }),
            content_type="application/json",
        )
        
        # User 2 submits same article with different tracking params
        client.force_login(user2)
        response2 = client.post(
            "/api/submit-from-extension/",
            json.dumps({
                "url": "https://example.com/news?id=100&utm_source=twitter",
                "html": "<html><body>News</body></html>",
                "vote": "mala",
            }),
            content_type="application/json",
        )
        
        assert response1.status_code in [200, 201]
        assert response2.status_code in [200, 201]
        
        # Should only have ONE noticia
        assert Noticia.objects.count() == 1
        
        # But TWO votes with different opinions
        assert Voto.objects.count() == 2
        votes = Voto.objects.all()
        assert votes[0].opinion != votes[1].opinion
        assert {v.opinion for v in votes} == {"buena", "mala"}
