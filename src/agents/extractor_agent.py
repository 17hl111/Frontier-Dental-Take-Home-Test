"""This module exists to extract structured product fields from a product detail page. It prioritizes JSON LD and metadata, then falls back to selectors and simple heuristics. Possible improvement: add more selectors and site specific rules for edge cases, but that is left for future hardening."""

from __future__ import annotations

import re
from pathlib import Path

from ..models import RawProductRecord
from ..scraping.parser import (
    parse_html,
    first_text,
    all_image_urls,
    all_links,
    extract_table_key_values,
    text_after_label,
    get_meta_content,
    find_product_json_ld,
    image_urls_from_json_ld,
    get_product_offer,
    extract_main_text_excerpt,
    extract_description_block_text,
)
from ..scraping.selectors import (
    PRODUCT_TITLE_SELECTORS,
    PRODUCT_PRICE_SELECTORS,
    PRODUCT_DESCRIPTION_SELECTORS,
    PRODUCT_IMAGE_SELECTORS,
    PRODUCT_RELATED_LINK_SELECTORS,
)
from ..utils import (
    utc_now_iso,
    parse_price,
    safe_filename,
    dedupe_preserve_order,
    normalize_whitespace,
    ensure_parent,
)


class ExtractorAgent:
    def __init__(self, settings: dict, logger):
        self.settings = settings
        self.logger = logger

    def extract_product(self, url: str, html: str, category_path: list[str]) -> RawProductRecord:
        # Parse HTML into BeautifulSoup and gather base text fields.
        soup = parse_html(html)
        full_text = soup.get_text("\n", strip=True)
        page_text_excerpt = extract_main_text_excerpt(
            soup,
            max_chars=self.settings["llm"].get("max_input_chars", 6000),
        )
        description_block_text = extract_description_block_text(soup)
        meta_description = get_meta_content(
            soup,
            ["description", "og:description", "twitter:description"],
        )
        meta_keywords = get_meta_content(soup, ["keywords"])

        # Prefer JSON-LD when available for high-quality structured data.
        product_ld = find_product_json_ld(soup)
        offer_ld = get_product_offer(product_ld or {})

        title = self._first_non_empty(
            normalize_whitespace((product_ld or {}).get("name")),
            first_text(soup, PRODUCT_TITLE_SELECTORS),
            get_meta_content(soup, ["og:title", "twitter:title"]),
        )

        price_text = self._first_non_empty(
            normalize_whitespace(str(offer_ld.get("price"))) if offer_ld.get("price") is not None else None,
            first_text(soup, PRODUCT_PRICE_SELECTORS),
        )

        description = self._first_non_empty(
            normalize_whitespace((product_ld or {}).get("description")),
            description_block_text,
            first_text(soup, PRODUCT_DESCRIPTION_SELECTORS),
            meta_description,
        )

        # Table specs are merged with any optional heuristics.
        specs = extract_table_key_values(soup)
        heuristic_specs = self._heuristic_specifications(
            category_path=category_path,
            product_name=title,
            description_block_text=description_block_text,
            description=description,
        )
        specs = self._merge_specs(specs, heuristic_specs)
        raw_spec_text = "\n".join([f"{k}: {v}" for k, v in specs.items() if v is not None]) or None

        # Collect images from JSON-LD and page selectors.
        selector_images = all_image_urls(soup, PRODUCT_IMAGE_SELECTORS, url)
        ld_images = image_urls_from_json_ld(product_ld or {}, url)
        images = dedupe_preserve_order(ld_images + selector_images)

        # Related product links are stored as lightweight references.
        related = []
        for link in dedupe_preserve_order(all_links(soup, PRODUCT_RELATED_LINK_SELECTORS, url)):
            if "/product/" in link and link != url:
                related.append({"name": link.rsplit("/", 1)[-1], "url": link})

        ld_brand = self._extract_brand(product_ld or {})
        brand = self._first_non_empty(
            specs.get("Brand"),
            ld_brand,
            self._brand_from_keywords(meta_keywords),
        )

        manufacturer = self._first_non_empty(
            specs.get("Manufacturer"),
            self._extract_manufacturer(product_ld or {}),
        )

        # SKU and product codes are pulled from multiple fallback sources.
        sku = self._clean_possible_code(
            self._first_non_empty(
                normalize_whitespace((product_ld or {}).get("sku")),
                specs.get("Item #"),
                specs.get("SKU"),
                specs.get("Item Number"),
                text_after_label(full_text, ["Item #", "SKU", "Item Number"]),
                self._extract_code_from_keywords(meta_keywords),
            )
        )

        product_code = self._clean_possible_code(
            self._first_non_empty(
                specs.get("Mfr #"),
                specs.get("Product Code"),
                normalize_whitespace((product_ld or {}).get("mpn")),
            )
        )

        availability = self._first_non_empty(
            self._normalize_availability(offer_ld.get("availability")),
            specs.get("Stock Availability"),
            text_after_label(full_text, ["Availability", "Stock Availability"]),
        )

        # Try to infer pack size from text when not explicitly listed.
        pack_size = self._infer_pack_size(title, description_block_text, description, raw_spec_text, page_text_excerpt, full_text)

        # Warnings track key missing fields to support QA.
        warnings = []
        if not title:
            warnings.append("missing_product_name")
        if not description:
            warnings.append("missing_description")
        if not sku:
            warnings.append("missing_sku")

        raw_html_snapshot_path = None
        if self.settings["crawl"].get("save_raw_html", True):
            # Raw HTML snapshots help debugging extraction failures.
            raw_html_snapshot_path = self._save_raw_html(url, html)

        extraction_sources = {
            "primary": "rule_based",
            "llm_fallback_used": False,
            "used_json_ld": bool(product_ld),
            "used_meta_description": bool(meta_description),
            "used_description_block": bool(description_block_text),
            "used_heuristic_specs": bool(heuristic_specs),
        }

        return RawProductRecord(
            category_path=category_path,
            product_name=normalize_whitespace(title),
            brand=normalize_whitespace(brand),
            manufacturer=normalize_whitespace(manufacturer),
            sku=normalize_whitespace(sku),
            product_code=normalize_whitespace(product_code),
            product_url=url,
            price_text=normalize_whitespace(price_text),
            price_value=parse_price(price_text),
            currency=self._first_non_empty(
                normalize_whitespace(offer_ld.get("priceCurrency")),
                "USD",
            ),
            unit_or_pack_size=normalize_whitespace(pack_size),
            availability=normalize_whitespace(availability),
            description=normalize_whitespace(description),
            description_block_text=normalize_whitespace(description_block_text),
            specifications=specs,
            raw_specifications_text=raw_spec_text,
            page_text_excerpt=page_text_excerpt,
            meta_description=meta_description,
            image_urls=images,
            alternative_products=related,
            raw_html_snapshot_path=raw_html_snapshot_path,
            scraped_at=utc_now_iso(),
            extraction_method=extraction_sources,
            extraction_warnings=warnings,
            quality_flags=[],
        )

    def _heuristic_specifications(
        self,
        category_path: list[str],
        product_name: str | None,
        description_block_text: str | None,
        description: str | None,
    ) -> dict:
        # No category-specific heuristics; LLM handles flexible specs.
        return {}

    @staticmethod
    def _merge_specs(base_specs: dict, extra_specs: dict) -> dict:
        # Preserve table values unless they are blank or missing.
        merged = dict(base_specs or {})
        for key, value in (extra_specs or {}).items():
            if key not in merged or merged.get(key) in (None, "", "{}"):
                merged[key] = value
        return merged

    def _save_raw_html(self, url: str, html: str) -> str:
        # Store HTML with a stable filename derived from the URL.
        filename = safe_filename(url.replace("https://", "").replace("http://", "")) + ".html"
        path = ensure_parent(Path("data/raw_html") / filename)
        path.write_text(html, encoding="utf-8")
        return str(path)

    @staticmethod
    def _first_non_empty(*values: str | None) -> str | None:
        # Return the first non-empty normalized string from a list.
        for value in values:
            normalized = normalize_whitespace(value)
            if normalized:
                return normalized
        return None

    @staticmethod
    def _extract_brand(product_ld: dict) -> str | None:
        brand = product_ld.get("brand")
        if isinstance(brand, dict):
            return normalize_whitespace(brand.get("name"))
        if isinstance(brand, str):
            return normalize_whitespace(brand)
        return None

    @staticmethod
    def _extract_manufacturer(product_ld: dict) -> str | None:
        manufacturer = product_ld.get("manufacturer")
        if isinstance(manufacturer, dict):
            return normalize_whitespace(manufacturer.get("name"))
        if isinstance(manufacturer, str):
            return normalize_whitespace(manufacturer)
        return None

    @staticmethod
    def _extract_code_from_keywords(meta_keywords: str | None) -> str | None:
        # Detect SKU-like tokens in comma-separated keywords.
        if not meta_keywords:
            return None
        candidates = [normalize_whitespace(x) for x in meta_keywords.split(",")]
        for candidate in candidates:
            if candidate and re.search(r"[A-Z]{2,}[-]?\d+|[A-Z0-9]{4,}", candidate):
                return candidate
        return None

    @staticmethod
    def _brand_from_keywords(meta_keywords: str | None) -> str | None:
        # Use early keyword tokens as a weak brand signal.
        if not meta_keywords:
            return None
        candidates = [normalize_whitespace(x) for x in meta_keywords.split(",")]
        for candidate in candidates[:3]:
            if candidate and len(candidate.split()) <= 3 and not re.search(r"\d", candidate):
                return candidate
        return None

    @staticmethod
    def _normalize_availability(value: str | None) -> str | None:
        # Map schema.org availability codes into human labels.
        if not value:
            return None
        lowered = value.lower()
        if "instock" in lowered or "in stock" in lowered:
            return "In Stock"
        if "outofstock" in lowered or "out of stock" in lowered:
            return "Out of Stock"
        return normalize_whitespace(value)

    @staticmethod
    def _infer_pack_size(*texts: str | None) -> str | None:
        # Search for pack-size patterns across multiple text sources.
        patterns = [
            r"(\d+\s*/\s*(box|case|pack|pkg|pair|pairs|ct))",
            r"((box|case|pack|pkg)\s+of\s+\d+)",
            r"(\d+\s+(per\s+)?(box|case|pack|pkg|pair|pairs|ct))",
            r"(order\s+\d+\s+boxes\s+to\s+purchase\s+a\s+case)",
        ]
        for text in texts:
            if not text:
                continue
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return normalize_whitespace(match.group(1))
        return None

    @staticmethod
    def _clean_possible_code(value: str | None) -> str | None:
        # Filter out label-like or UI text that looks like a code.
        if not value:
            return None

        normalized = normalize_whitespace(value)
        if not normalized:
            return None

        bad_values = {
            "description",
            "product code",
            "sku",
            "item number",
            "item #",
            "reviews",
            "quantity",
            "details",
        }
        if normalized.lower() in bad_values:
            return None

        return normalized