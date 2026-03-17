"""This module exists to validate required fields and attach quality flags. 
It also checks for duplicates using normalized URLs. 
Possible improvement: add richer validation rules and consistency checks."""

from __future__ import annotations

from ..models import NormalizedProduct, ValidationResult
from ..utils import normalize_url_for_dedup


class ValidatorAgent:
    def __init__(self, storage, logger):
        self.storage = storage
        self.logger = logger

    def validate(self, product: NormalizedProduct) -> ValidationResult:
        # Hard requirements for persistence.
        missing = []
        quality_flags = list(product.quality_flags)

        if not product.product_name:
            missing.append("product_name")
        if not product.product_url:
            missing.append("product_url")
        if not product.category_path:
            missing.append("category_path")

        # Soft-quality flags help QA prioritize review.
        if not product.brand:
            quality_flags.append("missing_brand")
        if not product.price_text:
            quality_flags.append("missing_price")
        if not product.sku:
            quality_flags.append("missing_sku")
        if not product.description:
            quality_flags.append("missing_description")
        if not product.specifications:
            quality_flags.append("missing_specifications")

        # Keep LLM usage visible in output.
        if product.llm_attempted:
            quality_flags.append("llm_attempted")
        if product.llm_used:
            quality_flags.append("llm_fallback_used")
        if product.llm_changed_fields:
            quality_flags.append("llm_changed_fields_present")

        duplicate_of = None
        # Deduplicate by normalized URL across runs.
        norm_url = normalize_url_for_dedup(product.product_url)
        if self.storage.has_successful_url(norm_url):
            duplicate_of = norm_url
            quality_flags.append("duplicate_url")

        is_valid = len(missing) == 0
        return ValidationResult(
            is_valid=is_valid,
            quality_flags=sorted(set(quality_flags)),
            missing_fields=missing,
            duplicate_of=duplicate_of,
        )