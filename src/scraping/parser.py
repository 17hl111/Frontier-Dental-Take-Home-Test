# Summary: HTML parsing helpers for text, links, images, and JSON-LD data.

from __future__ import annotations

import json
import re
from typing import Iterable, Any

from bs4 import BeautifulSoup

from ..utils import normalize_whitespace, absolutize_url


def parse_html(html: str) -> BeautifulSoup:
    # Use lxml for speed and resilience.
    return BeautifulSoup(html, "lxml")


def first_text(soup: BeautifulSoup, selectors: Iterable[str]) -> str | None:
    # Return the first non-empty text found among selectors.
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            value = normalize_whitespace(node.get_text(" ", strip=True))
            if value:
                return value
    return None


def all_links(soup: BeautifulSoup, selectors: Iterable[str], base_url: str) -> list[str]:
    # Collect absolute URLs from matching anchor tags.
    links: list[str] = []
    for selector in selectors:
        for node in soup.select(selector):
            href = absolutize_url(base_url, node.get("href"))
            if href:
                links.append(href)
    return links


def all_image_urls(soup: BeautifulSoup, selectors: Iterable[str], base_url: str) -> list[str]:
    # Collect image URLs from src, data-src, or srcset.
    urls: list[str] = []
    for selector in selectors:
        for node in soup.select(selector):
            src = node.get("src") or node.get("data-src") or node.get("srcset")
            if not src:
                continue
            if " " in src and src.startswith("http"):
                src = src.split(" ")[0]
            abs_url = absolutize_url(base_url, src)
            if abs_url:
                urls.append(abs_url)
    return urls


def extract_table_key_values(soup: BeautifulSoup) -> dict[str, str]:
    # Basic table parsing for two-column spec tables.
    results: dict[str, str] = {}
    for row in soup.select("table tr"):
        headers = row.find_all(["th", "td"])
        if len(headers) >= 2:
            key = normalize_whitespace(headers[0].get_text(" ", strip=True))
            val = normalize_whitespace(headers[1].get_text(" ", strip=True))
            if key and val and len(key) <= 120:
                results[key] = val
    return results


def text_after_label(full_text: str, labels: list[str]) -> str | None:
    # Find a short value after a label like "SKU:" in the raw page text.
    for label in labels:
        pattern = re.compile(rf"{re.escape(label)}\s*[:#-]?\s*([^\n\r|]+)", re.IGNORECASE)
        match = pattern.search(full_text)
        if match:
            return normalize_whitespace(match.group(1))
    return None


def get_meta_content(soup: BeautifulSoup, names: list[str]) -> str | None:
    # Read meta content by name or property.
    for name in names:
        node = soup.select_one(f'meta[name="{name}"]') or soup.select_one(f'meta[property="{name}"]')
        if node:
            content = normalize_whitespace(node.get("content"))
            if content:
                return content
    return None


def extract_json_ld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    # Parse JSON-LD blocks from the page, ignoring malformed payloads.
    objects: list[dict[str, Any]] = []
    for node in soup.select('script[type="application/ld+json"]'):
        raw = node.string or node.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    objects.append(item)
        elif isinstance(payload, dict):
            objects.append(payload)
    return objects


def _as_list(value: Any) -> list[Any]:
    # Normalize scalar or list values into a list.
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _type_matches(value: Any, target: str) -> bool:
    # Support both string and list values for @type.
    for item in _as_list(value):
        if isinstance(item, str) and item.lower() == target.lower():
            return True
    return False


def find_product_json_ld(soup: BeautifulSoup) -> dict[str, Any] | None:
    # Find a Product object in JSON-LD or @graph blocks.
    for obj in extract_json_ld_objects(soup):
        if _type_matches(obj.get("@type"), "Product"):
            return obj

        graph = obj.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                if isinstance(item, dict) and _type_matches(item.get("@type"), "Product"):
                    return item
    return None


def image_urls_from_json_ld(product_obj: dict[str, Any], base_url: str) -> list[str]:
    # Extract image URLs from JSON-LD "image" fields.
    urls: list[str] = []
    raw_images = product_obj.get("image")
    for item in _as_list(raw_images):
        if isinstance(item, str):
            abs_url = absolutize_url(base_url, item)
            if abs_url:
                urls.append(abs_url)
        elif isinstance(item, dict):
            candidate = item.get("url") or item.get("contentUrl")
            abs_url = absolutize_url(base_url, candidate)
            if abs_url:
                urls.append(abs_url)
    return urls


def get_product_offer(product_obj: dict[str, Any]) -> dict[str, Any]:
    # Normalize schema.org offers into a single dict.
    offers = product_obj.get("offers")
    if isinstance(offers, list) and offers:
        first = offers[0]
        return first if isinstance(first, dict) else {}
    if isinstance(offers, dict):
        return offers
    return {}


def extract_main_text_excerpt(soup: BeautifulSoup, max_chars: int = 4000) -> str | None:
    # Extract the main text body for LLM context windows.
    candidate_selectors = [
        "main",
        '[role="main"]',
        ".product-info-main",
        ".product-info-details",
        ".column.main",
        ".product-view",
        "body",
    ]
    for selector in candidate_selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        text = normalize_whitespace(node.get_text(" ", strip=True))
        if text and len(text) > 80:
            return text[:max_chars]
    body_text = normalize_whitespace(soup.get_text(" ", strip=True))
    if body_text:
        return body_text[:max_chars]
    return None


def extract_description_block_text(soup: BeautifulSoup, max_chars: int = 2500) -> str | None:
    # Extract the product description block with bullet support.
    candidate_selectors = [
        ".product.attribute.description .value",
        ".product.attribute.description",
        '[data-role="content"] .product.attribute.description',
        ".description .value",
        ".product.info.detailed .description",
        ".product-info-description",
        "#description",
    ]

    chunks: list[str] = []

    for selector in candidate_selectors:
        node = soup.select_one(selector)
        if not node:
            continue

        # Preserve paragraph and list item ordering for a cleaner summary.
        parts: list[str] = []
        for p in node.select("p"):
            text = normalize_whitespace(p.get_text(" ", strip=True))
            if text:
                parts.append(text)

        for li in node.select("li"):
            text = normalize_whitespace(li.get_text(" ", strip=True))
            if text:
                parts.append(text)

        if not parts:
            fallback_text = normalize_whitespace(node.get_text(" ", strip=True))
            if fallback_text:
                parts.append(fallback_text)

        if parts:
            joined = "\n".join(dict.fromkeys(parts))
            joined = _clean_description_noise(joined)
            if joined:
                return joined[:max_chars]

    return None


def _clean_description_noise(text: str) -> str:
    # Remove obvious promo or UI noise from description text.
    if not text:
        return text

    noise_patterns = [
        r"chevron-(up|down|left|right)",
        r"promo\b.*?$",
        r"q\d+\s+buy.*?$",
        r"offer ends.*?$",
        r"\breviews?\b",
        r"\bfrom \$?\d+(\.\d+)?",
    ]

    cleaned_lines: list[str] = []
    for line in text.splitlines():
        current = normalize_whitespace(line)
        if not current:
            continue
        lowered = current.lower()
        skip = False
        for pattern in noise_patterns:
            if re.search(pattern, lowered, re.IGNORECASE):
                skip = True
                break
        if not skip:
            cleaned_lines.append(current)

    return "\n".join(cleaned_lines) if cleaned_lines else normalize_whitespace(text)
