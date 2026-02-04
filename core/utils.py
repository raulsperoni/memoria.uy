# utils.py - Utility functions for core app

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import logging

logger = logging.getLogger(__name__)

# Common tracking parameters to strip from URLs
TRACKING_PARAMS = {
    # Google Analytics
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic',
    
    # Facebook
    'fbclid', 'fb_action_ids', 'fb_action_types', 'fb_source', 'fb_ref',
    
    # Google Ads
    'gclid', 'gclsrc', 'dclid',
    
    # Microsoft/Bing
    'msclkid',
    
    # Email marketing
    'mc_cid', 'mc_eid', '_bta_tid', '_bta_c',
    
    # Other common tracking
    '_ga', '_gl', 'ref', 'referrer',
    
    # Social media
    'igshid', 'twclid',
}


def normalize_url(url):
    """
    Normalize URL by removing tracking parameters and fragments.
    
    This prevents duplicates when the same article is shared via different
    channels (email, social media, etc.) with different tracking parameters.
    
    Args:
        url: The URL to normalize
        
    Returns:
        str: Normalized URL without tracking params and fragments
        
    Examples:
        >>> normalize_url('https://example.com/article?id=123&utm_source=fb')
        'https://example.com/article?id=123'
        
        >>> normalize_url('https://example.com/article?fbclid=xxx#section')
        'https://example.com/article'
    """
    try:
        parsed = urlparse(url)
        
        # Parse query parameters
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        # Filter out tracking params
        clean_params = {
            k: v for k, v in params.items() 
            if k not in TRACKING_PARAMS
        }
        
        # Rebuild query string (sorted for consistency)
        clean_query = urlencode(sorted(clean_params.items()), doseq=True) if clean_params else ''
        
        # Rebuild URL without fragment (# anchor) and with clean params
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            clean_query,
            ''  # no fragment
        ))
        
        # Log if we changed anything
        if normalized != url:
            logger.debug(f"Normalized URL: {url} -> {normalized}")
        
        return normalized
        
    except Exception as e:
        # If normalization fails, return original URL
        logger.warning(f"Failed to normalize URL {url}: {e}")
        return url


# Token for one-click unsubscribe + profile access (reengagement email)
REENGAGEMENT_TOKEN_MAX_AGE_DAYS = 30


def make_reengagement_access_token(user_id):
    """Return a signed token for the user to access profile and unsubscribe (no login)."""
    from django.core.signing import TimestampSigner
    signer = TimestampSigner()
    return signer.sign(str(user_id))


def get_user_from_reengagement_token(token):
    """
    Validate token and return the User or None if invalid/expired.
    """
    from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
    from django.contrib.auth import get_user_model
    try:
        signer = TimestampSigner()
        user_id = signer.unsign(token, max_age=REENGAGEMENT_TOKEN_MAX_AGE_DAYS * 24 * 3600)
        return get_user_model().objects.filter(pk=int(user_id)).first()
    except (SignatureExpired, BadSignature, ValueError):
        return None
