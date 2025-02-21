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
    headers = ***REMOVED***"User-Agent": user_agent***REMOVED***
    # Some minimal data; the archive service expects a "url" parameter.
    data = ***REMOVED***"url": url, "submitid": "1"***REMOVED***
    response = requests.post(
        ARCHIVE_PH_SUBMIT_URL, data=data, headers=headers, timeout=30
    )

    # If the response is a redirect, assume the archive URL is in the Location header.
    if response.status_code == 302 and "Location" in response.headers:
        archive_url = response.headers["Location"]
        if archive_url == "https://archive.ph/wip":
            raise ArchiveInProgress(f"Archiving in progress for ***REMOVED***url***REMOVED***")
        return archive_url, get_archive_details(response.text)

    # Otherwise, try to extract the archive URL from the HTML using regex.
    match = re.search(r"(https?://archive\.ph/\w+)", response.text)
    if match:
        return match.group(1), get_archive_details(response.text)

    raise ArchiveFailure(
        f"Failed to capture ***REMOVED***url***REMOVED*** via archive.ph (status: ***REMOVED***response.status_code***REMOVED***)"
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
    meta_date = soup.find("meta", attrs=***REMOVED***"property": "article:published_time"***REMOVED***)
    if meta_date and meta_date.get("content"):
        archive_date = meta_date["content"]

    # Parse screenshot URL from the Open Graph image meta tag.
    screenshot_url = None
    meta_img = soup.find("meta", attrs=***REMOVED***"property": "og:image"***REMOVED***)
    if meta_img and meta_img.get("content"):
        screenshot_url = meta_img["content"]

    url = soup.find("meta", attrs=***REMOVED***"property": "og:url"***REMOVED***)
    if url and url.get("content"):
        url = url["content"]

    return ***REMOVED***
        "title": page_title,
        "archive_date": archive_date,
        "screenshot_url": screenshot_url,
        "archive_url": url,
***REMOVED***
