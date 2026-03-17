"""
Note: This module is not used for this prototype because I decided to use alternative ways to
classify category and product (By allowing user to select category, so won't need to classifier but
I think this is still a useful module for future use, so I keep this module.)
This module exists to classify pages as category or product using simple heuristics. 
It helps downstream logic reason about page type without heavy parsing. 
Possible improvement: expand rules or add a learned classifier (Another possible way to use LLMs).
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..constants import PAGE_TYPE_CATEGORY, PAGE_TYPE_PRODUCT, PAGE_TYPE_UNKNOWN


def classify_page(soup: BeautifulSoup, url: str) -> str:
    # Fast heuristics based on URL shape and page content.
    href_products = len(soup.select("a[href*='/product/']"))
    has_h1 = bool(soup.select_one("h1"))
    text = soup.get_text(" ", strip=True).lower()

    if "/product/" in url:
        return PAGE_TYPE_PRODUCT
    if href_products >= 2:
        return PAGE_TYPE_CATEGORY
    if has_h1 and ("item #" in text or "product name" in text or "description" in text):
        return PAGE_TYPE_PRODUCT
    if "shop now" in text and href_products >= 1:
        return PAGE_TYPE_CATEGORY
    return PAGE_TYPE_UNKNOWN