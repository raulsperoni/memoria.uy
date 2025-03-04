import re
from core.url_requests import post


ARCHIVE_PH_SUBMIT_URL = "https://archive.ph/submit/"


class ArchiveInProgress(Exception):
    pass


class ArchiveNotFound(Exception):
    pass


def get_latest_snapshot(url, user_agent=None):
    """
    Capture the given URL using archive.ph.
    Returns the final archive URL or raises an Exception.
    """
    headers = {"User-Agent": user_agent} if user_agent else {}
    # Some minimal data; the archive service expects a "url" parameter.
    data = {"url": url, "submitid": "1"}
    response = post(
        ARCHIVE_PH_SUBMIT_URL, 
        data=data, 
        headers=headers, 
        timeout=30,
        rotate_user_agent=True,
        retry_on_failure=True
    )

    # If the response is a redirect, assume the archive URL is in the Location header.
    if response.status_code == 302 and "Location" in response.headers:
        archive_url = response.headers["Location"]
        if archive_url == "https://archive.ph/wip":
            raise ArchiveInProgress(f"Archiving in progress for {url}")
        return archive_url, response.text

    # Otherwise, try to extract the archive URL from the HTML using regex.
    match = re.search(r"(https?://archive\.ph/\w+)", response.text)
    if match:
        archive_url = match.group(1)
        if archive_url == "https://archive.ph/wip":
            raise ArchiveInProgress(f"Archiving in progress for {url}")
        return archive_url, response.text

    raise ArchiveNotFound(
        f"Failed to capture {url} via archive.ph (status: {response.status_code})"
    )
