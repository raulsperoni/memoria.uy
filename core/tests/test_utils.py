# test_utils.py - Tests for core utility functions

import pytest
from core.utils import normalize_url


class TestNormalizeUrl:
    """Test URL normalization (stripping tracking params)."""
    
    def test_strips_utm_parameters(self):
        """Should remove all UTM tracking parameters."""
        url = "https://example.com/article?id=123&utm_source=facebook&utm_medium=social&utm_campaign=spring"
        expected = "https://example.com/article?id=123"
        assert normalize_url(url) == expected
    
    def test_strips_fbclid(self):
        """Should remove Facebook click ID."""
        url = "https://example.com/article?id=123&fbclid=IwAR1234567890"
        expected = "https://example.com/article?id=123"
        assert normalize_url(url) == expected
    
    def test_strips_gclid(self):
        """Should remove Google click ID."""
        url = "https://example.com/article?id=123&gclid=CjwKCAiA"
        expected = "https://example.com/article?id=123"
        assert normalize_url(url) == expected
    
    def test_strips_multiple_tracking_params(self):
        """Should remove multiple tracking parameters at once."""
        url = "https://example.com/article?id=123&utm_source=email&fbclid=xxx&gclid=yyy&mc_cid=zzz"
        expected = "https://example.com/article?id=123"
        assert normalize_url(url) == expected
    
    def test_strips_fragment(self):
        """Should remove URL fragment (anchor)."""
        url = "https://example.com/article?id=123#section-2"
        expected = "https://example.com/article?id=123"
        assert normalize_url(url) == expected
    
    def test_preserves_functional_params(self):
        """Should keep parameters that are not tracking-related."""
        url = "https://example.com/search?q=test&category=news&page=2"
        result = normalize_url(url)
        # Should keep all functional params (may be sorted differently)
        assert "q=test" in result
        assert "category=news" in result
        assert "page=2" in result
        assert "utm_" not in result
    
    def test_handles_url_with_only_tracking_params(self):
        """Should work when URL has only tracking params."""
        url = "https://example.com/article?utm_source=twitter&fbclid=xxx"
        expected = "https://example.com/article"
        assert normalize_url(url) == expected
    
    def test_handles_url_without_query_string(self):
        """Should work with URLs that have no query parameters."""
        url = "https://example.com/article"
        assert normalize_url(url) == url
    
    def test_normalizes_consistently(self):
        """Should normalize same article from different sources to same URL."""
        url_facebook = "https://example.com/news/story?utm_source=facebook&fbclid=xxx#top"
        url_twitter = "https://example.com/news/story?utm_source=twitter&utm_medium=social"
        url_email = "https://example.com/news/story?utm_campaign=newsletter&mc_cid=yyy"
        url_clean = "https://example.com/news/story"
        
        assert normalize_url(url_facebook) == url_clean
        assert normalize_url(url_twitter) == url_clean
        assert normalize_url(url_email) == url_clean
    
    def test_handles_malformed_url_gracefully(self):
        """Should return original URL if normalization fails."""
        malformed = "not a url at all"
        # Should return original without crashing
        result = normalize_url(malformed)
        assert result == malformed
    
    def test_preserves_case_in_domain(self):
        """Should preserve the domain case (though browsers normalize it)."""
        url = "https://Example.COM/article?utm_source=test"
        result = normalize_url(url)
        assert result.startswith("https://Example.COM/")
    
    def test_sorts_params_for_consistency(self):
        """Should sort parameters for consistent output."""
        url1 = "https://example.com/article?z=3&a=1&m=2"
        url2 = "https://example.com/article?a=1&m=2&z=3"
        # Both should normalize to the same sorted version
        assert normalize_url(url1) == normalize_url(url2)
    
    def test_handles_empty_param_values(self):
        """Should handle parameters with empty values."""
        url = "https://example.com/article?id=&utm_source=test"
        result = normalize_url(url)
        # Should keep id= (empty functional param) but remove utm_source
        assert "id=" in result or "id" not in result  # Either keep empty or remove
        assert "utm_source" not in result
    
    def test_real_world_news_urls(self):
        """Test with real-world news URL patterns."""
        # La Diaria style
        ladiaria = "https://ladiaria.com.uy/politica/articulo/2024/1/test/?utm_source=newsletter"
        assert "utm_source" not in normalize_url(ladiaria)
        
        # El Observador style
        observador = "https://www.elobservador.com.uy/nota/test-123?ref=home&utm_medium=web"
        result = normalize_url(observador)
        assert "utm_medium" not in result
        assert "ref" not in result  # ref is also a tracking param
        
        # With fragment
        with_fragment = "https://example.com/article#comments?utm_source=app"
        result = normalize_url(with_fragment)
        assert "#" not in result
        assert "utm_source" not in result
