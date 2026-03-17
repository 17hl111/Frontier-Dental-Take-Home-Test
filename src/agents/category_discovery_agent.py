# Summary: Discover category names and URLs from site navigation pages.

from __future__ import annotations

from urllib.parse import urlparse

from ..scraping.parser import parse_html
from ..utils import absolutize_url, dedupe_preserve_order, normalize_url_for_dedup, normalize_whitespace


class CategoryDiscoveryAgent:
    def __init__(self, logger):
        self.logger = logger

    def discover(self, base_url: str, html: str) -> list[dict[str, str]]:
        # Parse the page and extract all category-like links.
        soup = parse_html(html)
        raw_links = self._collect_catalog_links(soup, base_url)
        raw_links = dedupe_preserve_order(raw_links)

        categories: list[dict[str, str]] = []
        seen: set[str] = set()
        for link in raw_links:
            top_url, slug = self._top_level_category_url(base_url, link)
            if not top_url or not slug:
                continue
            normalized = normalize_url_for_dedup(top_url)
            if normalized in seen:
                continue
            seen.add(normalized)

            # Always use the top-level slug for name to avoid subcategory labels.
            cleaned_name = self._name_from_slug(slug)
            if not cleaned_name:
                continue

            categories.append({"name": cleaned_name, "url": normalized})

        self.logger.info("Discovered %s categories", len(categories))
        return categories

    @staticmethod
    def _collect_catalog_links(soup, base_url: str) -> list[str]:
        # Keep only catalog-like URLs and ignore product or search links.
        out: list[str] = []
        for node in soup.select("a[href]"):
            href = node.get("href")
            abs_url = absolutize_url(base_url, href)
            if not abs_url:
                continue
            if "/catalog/" not in abs_url:
                continue
            if "/product/" in abs_url:
                continue
            if "catalogsearch" in abs_url:
                continue
            if abs_url.rstrip("/") == f"{base_url.rstrip('/')}/catalog":
                continue
            out.append(abs_url)
        return out

    @staticmethod
    def _top_level_category_url(base_url: str, url: str) -> tuple[str | None, str | None]:
        # Reduce any /catalog/<top>/<sub> URL to /catalog/<top>.
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if "catalog" not in parts:
            return None, None
        idx = parts.index("catalog")
        if idx + 1 >= len(parts):
            return None, None
        slug = parts[idx + 1]
        top_url = f"{base_url.rstrip('/')}/catalog/{slug}"
        return top_url, slug

    @staticmethod
    def _name_from_slug(slug: str) -> str:
        # Build a readable name from the top-level slug only.
        cleaned = normalize_whitespace(slug.replace("-", " ").replace("_", " "))
        return cleaned.title() if cleaned else ""
