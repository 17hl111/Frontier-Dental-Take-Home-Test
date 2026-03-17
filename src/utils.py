"""This module exists to hold small reusable helpers for time, text, and URL normalization. 
It can reduce repetition and keeps low level functions in one place. 
Possible improvement: Add unit tests for edge cases."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from datetime import datetime, timezone
import re


def utc_now_iso() -> str:
    # Stable UTC timestamp for audit and ordering.
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_whitespace(text: str | None) -> str | None:
    # Collapse multiple whitespace characters into single spaces.
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def safe_filename(value: str) -> str:
    # Replace unsafe filename characters to avoid OS issues.
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value)


def parse_price(text: str | None) -> float | None:
    # Extract the first numeric price-like token from a string.
    if not text:
        return None
    match = re.search(r"(\d+[\d,]*\.?\d*)", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def absolutize_url(base_url: str, href: str | None) -> str | None:
    # Build an absolute URL from a page base and link href.
    if not href:
        return None
    return urljoin(base_url, href)


def dedupe_preserve_order(items: list[str]) -> list[str]:
    # Preserve original order while removing duplicates and blanks.
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def normalize_url_for_dedup(url: str) -> str:
    # Normalize by removing tracking query params and fragments.
    parsed = urlparse(url)
    filtered_qs = [(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith("utm_") and k.lower() != "srsltid"]
    clean = parsed._replace(query=urlencode(filtered_qs), fragment="")
    return urlunparse(clean)


def ensure_parent(path: str | Path) -> Path:
    # Create parent directories for a file path.
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p