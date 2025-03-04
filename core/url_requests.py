import requests
import random
import time
import logging
from typing import Dict, Any, Optional, Tuple, Union, List
from requests.exceptions import RequestException, Timeout, TooManyRedirects, ConnectionError
from bs4 import BeautifulSoup
from functools import lru_cache
logger = logging.getLogger(__name__)

# List of common user agents to rotate through
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36 OPR/78.0.4093.112",
]

# Default headers to use with requests
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Free proxy list - you can update this with your own sources
# These are just examples and may not work - you'll need to find working free proxies
FREE_PROXIES = [
    # Format: "http://ip:port" or "https://ip:port"
    # Leave empty by default - will be populated dynamically if needed
]

# Backoff settings for retries
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 60  # seconds
MAX_RETRIES = 3


def get_random_user_agent() -> str:
    """Return a random user agent from the list."""
    return random.choice(USER_AGENTS)


def get_random_proxy() -> Optional[Dict[str, str]]:
    """Return a random proxy from the list if available."""
    if not FREE_PROXIES:
        return None
    
    proxy = random.choice(FREE_PROXIES)
    return {
        "http": proxy,
        "https": proxy
    }


def make_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    use_proxy: bool = False,
    rotate_user_agent: bool = True,
    retry_on_failure: bool = True,
    max_retries: int = MAX_RETRIES,
) -> Tuple[requests.Response, Dict[str, Any]]:
    """
    Make an HTTP request with various anti-blocking strategies.
    
    Args:
        method: HTTP method ('get' or 'post')
        url: Target URL
        headers: Optional headers to send
        data: Optional form data for POST requests
        params: Optional URL parameters for GET requests
        json: Optional JSON data for POST requests
        timeout: Request timeout in seconds
        use_proxy: Whether to use a proxy
        rotate_user_agent: Whether to use a random user agent
        retry_on_failure: Whether to retry on failure
        max_retries: Maximum number of retries
        
    Returns:
        Tuple of (response, metadata) where metadata contains information about the request
    """
    if method.lower() not in ["get", "post"]:
        raise ValueError(f"Unsupported HTTP method: {method}")
    
    # Prepare headers with a random user agent if requested
    request_headers = DEFAULT_HEADERS.copy()
    if headers:
        request_headers.update(headers)
    
    if rotate_user_agent or "User-Agent" not in request_headers:
        request_headers["User-Agent"] = get_random_user_agent()
    
    # Prepare proxies if requested
    proxies = get_random_proxy() if use_proxy else None
    
    # Metadata to return with the response
    metadata = {
        "user_agent": request_headers.get("User-Agent"),
        "proxy_used": proxies is not None,
        "retries": 0,
        "backoff_time": 0,
    }
    
    # Retry logic with exponential backoff
    retry_count = 0
    backoff = INITIAL_BACKOFF
    
    while True:
        try:
            # Add a small random delay to avoid patterns
            time.sleep(random.uniform(0.1, 1.0))
            
            if method.lower() == "get":
                response = requests.get(
                    url,
                    headers=request_headers,
                    params=params,
                    proxies=proxies,
                    timeout=timeout
                )
            else:  # POST
                response = requests.post(
                    url,
                    headers=request_headers,
                    data=data,
                    json=json,
                    params=params,
                    proxies=proxies,
                    timeout=timeout
                )
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after and retry_after.isdigit() else backoff
                
                logger.warning(f"Rate limited (429) on {url}. Waiting {wait_time}s before retry.")
                
                if retry_on_failure and retry_count < max_retries:
                    time.sleep(wait_time)
                    retry_count += 1
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    
                    # Rotate user agent and proxy for the next attempt
                    if rotate_user_agent:
                        request_headers["User-Agent"] = get_random_user_agent()
                    
                    if use_proxy:
                        proxies = get_random_proxy()
                    
                    metadata["retries"] = retry_count
                    metadata["backoff_time"] += wait_time
                    continue
                else:
                    # Return the rate-limited response if we've exhausted retries
                    logger.error(f"Max retries reached for {url} after {retry_count} attempts")
                    break
            
            # For other successful or unsuccessful responses, just return
            return response, metadata
            
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            logger.warning(f"Request error for {url}: {str(e)}")
            
            if retry_on_failure and retry_count < max_retries:
                time.sleep(backoff)
                retry_count += 1
                backoff = min(backoff * 2, MAX_BACKOFF)
                
                # Rotate user agent and proxy for the next attempt
                if rotate_user_agent:
                    request_headers["User-Agent"] = get_random_user_agent()
                
                if use_proxy:
                    proxies = get_random_proxy()
                
                metadata["retries"] = retry_count
                metadata["backoff_time"] += backoff
                continue
            else:
                # Re-raise the exception if we've exhausted retries
                raise
    
    return response, metadata


def get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    **kwargs
) -> requests.Response:
    """
    Make a GET request with anti-blocking strategies.
    
    Args:
        url: Target URL
        headers: Optional headers to send
        params: Optional URL parameters
        **kwargs: Additional arguments to pass to make_request
        
    Returns:
        Response object
    """
    response, _ = make_request("get", url, headers=headers, params=params, **kwargs)
    return response


def post(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    **kwargs
) -> requests.Response:
    """
    Make a POST request with anti-blocking strategies.
    
    Args:
        url: Target URL
        headers: Optional headers to send
        data: Optional form data
        json: Optional JSON data
        params: Optional URL parameters
        **kwargs: Additional arguments to pass to make_request
        
    Returns:
        Response object
    """
    response, _ = make_request("post", url, headers=headers, data=data, json=json, params=params, **kwargs)
    return response


def update_proxy_list(proxies: List[str]) -> None:
    """
    Update the list of available proxies.
    
    Args:
        proxies: List of proxy URLs in format "http://ip:port" or "https://ip:port"
    """
    global FREE_PROXIES
    FREE_PROXIES = fetch_free_proxies()


@lru_cache(maxsize=1, typed=False)
def fetch_free_proxies() -> List[str]:
    """
    Fetch a list of free proxies from public sources.
    Results are cached using LRU cache to avoid frequent requests to the proxy service.
    The cache will expire after a certain time period (controlled by ttl parameter).
    
    Returns:
        List of proxy URLs
    """
    logger.info("Fetching fresh list of free proxies")
    url = "https://free-proxy-list.net/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    proxies = []
    
    # The proxy table is now a regular table with class 'table table-striped table-bordered'
    # Find the table in the fpl-list div
    table_div = soup.find("div", {"class": "fpl-list"})
    if table_div:
        table = table_div.find("table", {"class": "table"})
        if table:
            # Get all rows except the header row
            rows = table.find_all("tr")[1:] if table.find_all("tr") else []
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    ip = cells[0].text.strip()
                    port = cells[1].text.strip()
                    # Skip invalid IPs like 0.0.0.0 or 127.0.0.x
                    if ip.startswith("0.0.0.0") or ip.startswith("127.0.0."):
                        continue
                    proxies.append(f"{ip}:{port}")
    
    logger.info(f"Found {len(proxies)} free proxies")
    return proxies


def clear_proxy_cache():
    """
    Clear the cache for fetch_free_proxies function.
    Call this function periodically to refresh the proxy list.
    """
    fetch_free_proxies.cache_clear()
    logger.info("Proxy cache cleared")
