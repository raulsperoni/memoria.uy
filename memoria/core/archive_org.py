import requests


class ArchiveNotFound(Exception):
    pass


def get_latest_snapshot(original_url):
    """
    Given a URL, query the Wayback Machine API for the closest snapshot.
    """
    api_endpoint = "https://archive.org/wayback/available"
    params = {"url": original_url}
    response = requests.get(api_endpoint, params=params)
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
        response = requests.get(archived_url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            raise ArchiveNotFound(f"Snapshot not found at {archived_url}")
        else:
            raise e
    if response.status_code == 404:
        raise ArchiveNotFound(f"Snapshot not found at {archived_url}")
    return response.text
