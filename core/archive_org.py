from core.url_requests import get
import requests.exceptions


class ArchiveNotFound(Exception):
    pass

class ArchiveInProgress(Exception):
    pass


def get_latest_snapshot(original_url):
    """
    Given a URL, query the Wayback Machine API for the closest snapshot.
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
