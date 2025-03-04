from core.url_requests import get, post
import requests.exceptions
import time


class ArchiveNotFound(Exception):
    pass

class ArchiveInProgress(Exception):
    pass


def save_url(original_url):
    """
    Submit a URL to be saved by the Internet Archive (archive.org).
    Returns the archive URL if successful, or raises an exception.
    
    Args:
        original_url: The URL to save to the Internet Archive
        
    Returns:
        Tuple of (archive_url, html_content) if successful
        
    Raises:
        ArchiveInProgress: If the archiving process is still in progress
        ArchiveNotFound: If the archiving process fails
    """
    save_endpoint = "https://web.archive.org/save/"
    save_url = f"{save_endpoint}{original_url}"
    
    response = get(save_url, rotate_user_agent=True, retry_on_failure=True)
    
    # Check if the save was successful
    if response.status_code == 200:
        # Extract the archive URL from the response
        # The URL will be in the format: https://web.archive.org/web/[timestamp]/[original_url]
        archive_url = response.url
        
        # If we got redirected to the "saving" page, the archive is still in progress
        if "_web.archive.org" in archive_url or "/save/" in archive_url:
            raise ArchiveInProgress(f"Archiving in progress for {original_url}")
            
        # Return the archive URL and the HTML content
        return archive_url, response.text
    elif response.status_code == 429:
        # Too many requests, raise an exception
        raise ArchiveNotFound(f"Rate limited while trying to save {original_url}")
    else:
        # Other error, raise an exception
        raise ArchiveNotFound(f"Failed to save {original_url} (status: {response.status_code})")


def get_latest_snapshot(original_url):
    """
    Given a URL, query the Wayback Machine API for the closest snapshot.
    If no snapshot is found, try to save the URL.
    
    Args:
        original_url: The URL to find or save in the Internet Archive
        attempt_save: Whether to attempt saving the URL if no snapshot is found
        
    Returns:
        Tuple of (archive_url, html_content)
        
    Raises:
        ArchiveInProgress: If the archiving process is still in progress
        ArchiveNotFound: If no snapshot is found and saving fails or is disabled
    """
    api_endpoint = "https://archive.org/wayback/available"
    params = {"url": original_url}
    response = get(api_endpoint, params=params, rotate_user_agent=True, retry_on_failure=True)
    try:
        data = response.json()
    except ValueError:
        raise ArchiveNotFound(f"Invalid JSON response for {original_url}")
    snapshots = data.get("archived_snapshots", {})
    # If a "closest" snapshot exists, return its URL
    if "closest" in snapshots:
        url = snapshots["closest"]["url"]
        html = fetch_snapshot(url)
        return url, html
    
    raise ArchiveNotFound(f"No snapshots found for {original_url}")


def fetch_snapshot(archived_url):
    try:
        response = get(archived_url, rotate_user_agent=True, retry_on_failure=True)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            raise ArchiveNotFound(f"Snapshot not found at {archived_url}")
        else:
            raise e
    if response.status_code == 404:
        raise ArchiveNotFound(f"Snapshot not found at {archived_url}")
    return response.text
