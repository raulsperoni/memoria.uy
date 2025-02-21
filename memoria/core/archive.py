import requests
import re
from bs4 import BeautifulSoup


ARCHIVE_PH_SUBMIT_URL = "https://archive.ph/submit/"


class ArchiveInProgress(Exception):
    pass


class ArchiveFailure(Exception):
    pass


def capture(url, user_agent="Mozilla/5.0 (compatible; MyApp/1.0)"):
    """
    Capture the given URL using archive.ph.
    Returns the final archive URL or raises an Exception.
    """
    headers = {"User-Agent": user_agent}
    # Some minimal data; the archive service expects a "url" parameter.
    data = {"url": url, "submitid": "1"}
    response = requests.post(
        ARCHIVE_PH_SUBMIT_URL, data=data, headers=headers, timeout=30
    )

    # If the response is a redirect, assume the archive URL is in the Location header.
    if response.status_code == 302 and "Location" in response.headers:
        archive_url = response.headers["Location"]
        if archive_url == "https://archive.ph/wip":
            raise ArchiveInProgress(f"Archiving in progress for {url}")
        return archive_url, get_archive_details(response.text)

    # Otherwise, try to extract the archive URL from the HTML using regex.
    match = re.search(r"(https?://archive\.ph/\w+)", response.text)
    if match:
        return match.group(1), get_archive_details(response.text)

    raise ArchiveFailure(
        f"Failed to capture {url} via archive.ph (status: {response.status_code})"
    )


def get_archive_details(html):
    """
    Given an archive.ph URL, fetch the page and parse:
      - page title (from the <title> tag),
      - archive date (from a meta tag if available),
      - screenshot URL (from og:image meta tag)
    Returns a dict with these details.
    """

    soup = BeautifulSoup(html, "html.parser")

    # Parse the page title.
    page_title = soup.title.string.strip() if soup.title else None

    # Try to get archive date from a meta tag (this may vary depending on archive.ph's HTML).
    archive_date = None
    meta_date = soup.find("meta", attrs={"property": "article:published_time"})
    if meta_date and meta_date.get("content"):
        archive_date = meta_date["content"]

    # Parse screenshot URL from the Open Graph image meta tag.
    screenshot_url = None
    meta_img = soup.find("meta", attrs={"property": "og:image"})
    if meta_img and meta_img.get("content"):
        screenshot_url = meta_img["content"]

    url = soup.find("meta", attrs={"property": "og:url"})
    if url and url.get("content"):
        url = url["content"]

    return {
        "title": page_title,
        "archive_date": archive_date,
        "screenshot_url": screenshot_url,
        "archive_url": url,
    }
