"""This module exists to persist crawl state and product data in SQLite with checkpoint support. It allows resumable runs and consistent exports by reading from a single store. Possible improvement: add migrations and batch writes for performance, but that is deferred."""

from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from typing import Any

from .models import NormalizedProduct
from .utils import ensure_parent, utc_now_iso


class Storage:
    def __init__(self, sqlite_path: str, checkpoint_path: str):
        self.sqlite_path = sqlite_path
        self.checkpoint_path = checkpoint_path
        # Ensure directories exist before connecting or writing checkpoints.
        ensure_parent(sqlite_path)
        ensure_parent(checkpoint_path)
        self.conn = sqlite3.connect(sqlite_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        # Product table stores the latest normalized record per product_url.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_url TEXT PRIMARY KEY,
                source_site TEXT,
                category_path TEXT,
                product_name TEXT,
                brand TEXT,
                manufacturer TEXT,
                sku TEXT,
                product_code TEXT,
                price_text TEXT,
                price_value REAL,
                currency TEXT,
                unit_or_pack_size TEXT,
                availability TEXT,
                description TEXT,
                description_block_text TEXT,
                raw_specifications_text TEXT,
                page_text_excerpt TEXT,
                meta_description TEXT,
                specifications_json TEXT,
                image_urls_json TEXT,
                alternative_products_json TEXT,
                page_type TEXT,
                raw_html_snapshot_path TEXT,
                scraped_at TEXT,
                extraction_method_json TEXT,
                quality_flags_json TEXT,
                llm_attempted INTEGER DEFAULT 0,
                llm_used INTEGER DEFAULT 0,
                llm_changed_fields_json TEXT
            )
            """
        )
        # Crawl state table tracks success/failure per URL.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crawl_state (
                url TEXT PRIMARY KEY,
                url_type TEXT,
                status TEXT,
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                updated_at TEXT
            )
            """
        )
        # Run metadata table is reserved for run-level tracking.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT,
                finished_at TEXT,
                categories_processed INTEGER,
                products_scraped INTEGER,
                products_failed INTEGER,
                llm_calls INTEGER,
                notes TEXT
            )
            """
        )
        self.conn.commit()

    def upsert_product(self, product: NormalizedProduct) -> None:
        # Idempotent write keyed by product_url.
        self.conn.execute(
            """
            INSERT INTO products (
                product_url, source_site, category_path, product_name, brand, manufacturer,
                sku, product_code, price_text, price_value, currency, unit_or_pack_size,
                availability, description, description_block_text, raw_specifications_text,
                page_text_excerpt, meta_description, specifications_json, image_urls_json,
                alternative_products_json, page_type, raw_html_snapshot_path, scraped_at,
                extraction_method_json, quality_flags_json, llm_attempted, llm_used,
                llm_changed_fields_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_url) DO UPDATE SET
                source_site=excluded.source_site,
                category_path=excluded.category_path,
                product_name=excluded.product_name,
                brand=excluded.brand,
                manufacturer=excluded.manufacturer,
                sku=excluded.sku,
                product_code=excluded.product_code,
                price_text=excluded.price_text,
                price_value=excluded.price_value,
                currency=excluded.currency,
                unit_or_pack_size=excluded.unit_or_pack_size,
                availability=excluded.availability,
                description=excluded.description,
                description_block_text=excluded.description_block_text,
                raw_specifications_text=excluded.raw_specifications_text,
                page_text_excerpt=excluded.page_text_excerpt,
                meta_description=excluded.meta_description,
                specifications_json=excluded.specifications_json,
                image_urls_json=excluded.image_urls_json,
                alternative_products_json=excluded.alternative_products_json,
                page_type=excluded.page_type,
                raw_html_snapshot_path=excluded.raw_html_snapshot_path,
                scraped_at=excluded.scraped_at,
                extraction_method_json=excluded.extraction_method_json,
                quality_flags_json=excluded.quality_flags_json,
                llm_attempted=excluded.llm_attempted,
                llm_used=excluded.llm_used,
                llm_changed_fields_json=excluded.llm_changed_fields_json
            """,
            (
                product.product_url,
                product.source_site,
                json.dumps(product.category_path),
                product.product_name,
                product.brand,
                product.manufacturer,
                product.sku,
                product.product_code,
                product.price_text,
                product.price_value,
                product.currency,
                product.unit_or_pack_size,
                product.availability,
                product.description,
                product.description_block_text,
                product.raw_specifications_text,
                product.page_text_excerpt,
                product.meta_description,
                json.dumps(product.specifications),
                json.dumps(product.image_urls),
                json.dumps(product.alternative_products),
                product.page_type,
                product.raw_html_snapshot_path,
                product.scraped_at,
                json.dumps(product.extraction_method),
                json.dumps(product.quality_flags),
                int(product.llm_attempted),
                int(product.llm_used),
                json.dumps(product.llm_changed_fields),
            ),
        )
        self.conn.commit()

    def mark_url(self, url: str, url_type: str, status: str, retry_count: int = 0, error_message: str | None = None) -> None:
        # Record success/failure status for a URL.
        self.conn.execute(
            """
            INSERT INTO crawl_state (url, url_type, status, retry_count, error_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                url_type=excluded.url_type,
                status=excluded.status,
                retry_count=excluded.retry_count,
                error_message=excluded.error_message,
                updated_at=excluded.updated_at
            """,
            (url, url_type, status, retry_count, error_message, utc_now_iso()),
        )
        self.conn.commit()

    def has_successful_url(self, url: str) -> bool:
        # Lightweight duplicate check for the validator.
        row = self.conn.execute(
            "SELECT 1 FROM crawl_state WHERE url = ? AND status = 'success' LIMIT 1",
            (url,),
        ).fetchone()
        return row is not None

    def get_products(self) -> list[dict[str, Any]]:
        # Return raw DB rows to preserve storage-level JSON fields.
        rows = self.conn.execute("SELECT * FROM products ORDER BY scraped_at DESC").fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append({k: row[k] for k in row.keys()})
        return out

    def get_stats(self) -> dict[str, Any]:
        # Aggregate counts for CLI/UI summaries.
        total_products = self.conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        llm_products = self.conn.execute("SELECT COUNT(*) AS c FROM products WHERE llm_used = 1").fetchone()["c"]
        llm_attempted = self.conn.execute("SELECT COUNT(*) AS c FROM products WHERE llm_attempted = 1").fetchone()["c"]
        failed_urls = self.conn.execute("SELECT COUNT(*) AS c FROM crawl_state WHERE status = 'failed'").fetchone()["c"]
        return {
            "total_products": total_products,
            "llm_attempted_products": llm_attempted,
            "llm_improved_products": llm_products,
            "failed_urls": failed_urls,
        }

    def save_checkpoint(self, state: dict[str, Any]) -> None:
        # Persist incremental progress to support resume.
        ensure_parent(self.checkpoint_path).write_text(json.dumps(state, indent=2), encoding="utf-8")

    def load_checkpoint(self) -> dict[str, Any]:
        path = Path(self.checkpoint_path)
        if not path.exists():
            return self.empty_checkpoint()
        return json.loads(path.read_text(encoding="utf-8"))

    def empty_checkpoint(self) -> dict[str, Any]:
        # Default structure used for a fresh run.
        return {
            "completed_category_pages": [],
            "completed_product_urls": [],
            "failed_product_urls": [],
            "stats": {"scraped": 0, "failed": 0, "llm_calls": 0, "llm_attempted": 0},
        }

    def clear_checkpoint(self) -> None:
        path = Path(self.checkpoint_path)
        if path.exists():
            path.unlink()

    def close(self) -> None:
        # Explicit close for cleanup paths and tests.
        self.conn.close()