"""This module exists to define the structured data models used across the pipeline. 
It provides a single source of truth for product fields and validation results. 
Possible improvement: enforce stricter typing for specifications and nested fields."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class CategorySeed(BaseModel):
    # Input seed used to start a category crawl.
    name: str
    url: str


class CrawlTask(BaseModel):
    # Internal task representation for pending work.
    url: str
    page_type: str
    category_path: list[str] = Field(default_factory=list)
    source: str = "safcodental"


class DiscoveryResult(BaseModel):
    # Output of category discovery: product links and pagination.
    page_url: str
    page_type: str
    category_path: list[str] = Field(default_factory=list)
    product_links: list[str] = Field(default_factory=list)
    next_page_url: str | None = None


class RawProductRecord(BaseModel):
    # Rule-based extraction result before any LLM normalization.
    source_site: str = "safcodental"
    category_path: list[str] = Field(default_factory=list)
    product_name: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    sku: str | None = None
    product_code: str | None = None
    product_url: str
    price_text: str | None = None
    price_value: float | None = None
    currency: str | None = "USD"
    unit_or_pack_size: str | None = None
    availability: str | None = None
    description: str | None = None
    description_block_text: str | None = None
    specifications: dict[str, Any] = Field(default_factory=dict)
    raw_specifications_text: str | None = None
    page_text_excerpt: str | None = None
    meta_description: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    alternative_products: list[dict[str, str]] = Field(default_factory=list)
    page_type: str = "product_detail"
    raw_html_snapshot_path: str | None = None
    scraped_at: str
    extraction_method: dict[str, Any] = Field(default_factory=dict)
    extraction_warnings: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)


class NormalizedProduct(BaseModel):
    # Normalized product record after LLM fallback and validation.
    source_site: str = "safcodental"
    category_path: list[str] = Field(default_factory=list)
    product_name: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    sku: str | None = None
    product_code: str | None = None
    product_url: str
    price_text: str | None = None
    price_value: float | None = None
    currency: str | None = "USD"
    unit_or_pack_size: str | None = None
    availability: str | None = None
    description: str | None = None
    description_block_text: str | None = None
    specifications: dict[str, Any] = Field(default_factory=dict)
    raw_specifications_text: str | None = None
    page_text_excerpt: str | None = None
    meta_description: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    alternative_products: list[dict[str, str]] = Field(default_factory=list)
    page_type: str = "product_detail"
    raw_html_snapshot_path: str | None = None
    scraped_at: str
    extraction_method: dict[str, Any] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)
    llm_attempted: bool = False
    llm_used: bool = False
    llm_changed_fields: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    # Validation output used to decide persistence and QA flags.
    is_valid: bool
    quality_flags: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    duplicate_of: str | None = None