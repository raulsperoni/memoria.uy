#!/usr/bin/env python
"""
Script to test the parse_from_meta_tags function with a specific URL.
"""
import os
import sys
import django
import logging

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memoria.settings")
django.setup()

from core.parse import parse_from_meta_tags

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_parse_meta_tags(url):
    """
    Test the parse_from_meta_tags function with a specific URL.

    Args:
        url: The URL to test
    """
    logger.info(f"Testing parse_from_meta_tags with URL: {url}")
    title, image_url = parse_from_meta_tags(url)

    logger.info(f"Results:")
    logger.info(f"Title: {title}")
    logger.info(f"Image URL: {image_url}")

    return title, image_url


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_parse_meta.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    title, image_url = test_parse_meta_tags(url)

    print("\nResults:")
    print(f"Title: {title}")
    print(f"Image URL: {image_url}")
