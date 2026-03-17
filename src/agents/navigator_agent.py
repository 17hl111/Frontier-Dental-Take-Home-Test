"""This module exists to navigate category pages and discover product URLs and pagination. 
It keeps link extraction and next page logic separate from the runner. 
Possible improvement: handle more pagination patterns and add stronger page type validation."""

from __future__ import annotations

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from ..models import DiscoveryResult
from ..scraping.parser import parse_html, all_links
from ..scraping.selectors import CATEGORY_PRODUCT_LINK_SELECTORS, CATEGORY_NEXT_PAGE_SELECTORS
from ..scraping.page_classifier import classify_page
from ..utils import dedupe_preserve_order, normalize_url_for_dedup


class NavigatorAgent:
    def __init__(self, logger):
        self.logger = logger

    def discover_from_category(self, url: str, html: str, category_path: list[str], page_number: int, max_pages: int) -> DiscoveryResult:
        # Parse and classify the category page, then extract product links.
        soup = parse_html(html)
        page_type = classify_page(soup, url)
        product_links = all_links(soup, CATEGORY_PRODUCT_LINK_SELECTORS, url)
        product_links = [normalize_url_for_dedup(link) for link in product_links if "/product/" in link]
        product_links = dedupe_preserve_order(product_links)

        # Resolve next page URL using selectors or a query-string fallback.
        next_page_url = self._extract_next_page(url, soup, page_number, max_pages)
        self.logger.info(
            "Navigator found %s product links on %s",
            len(product_links),
            url,
        )
        return DiscoveryResult(
            page_url=url,
            page_type=page_type,
            category_path=category_path,
            product_links=product_links,
            next_page_url=next_page_url,
        )

    def _extract_next_page(self, current_url: str, soup, page_number: int, max_pages: int) -> str | None:
        if page_number >= max_pages:
            return None

        next_links = all_links(soup, CATEGORY_NEXT_PAGE_SELECTORS, current_url)
        for link in next_links:
            normalized = normalize_url_for_dedup(link)
            if normalized != normalize_url_for_dedup(current_url):
                return normalized

        # heuristic fallback: increment ?p=
        parsed = urlparse(current_url)
        query = parse_qs(parsed.query)
        current_p = int(query.get("p", [str(page_number)])[0])
        query["p"] = [str(current_p + 1)]
        new_query = urlencode({k: v[0] for k, v in query.items()})
        return urlunparse(parsed._replace(query=new_query))