"""This module exists to orchestrate the end to end crawl workflow. It coordinates category discovery, navigation, extraction, normalization, validation, persistence, and export steps. Possible improvement: separate scheduling from execution and add more robust concurrency control, but that is out of scope."""

from __future__ import annotations

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from .agents.category_discovery_agent import CategoryDiscoveryAgent
from .agents.navigator_agent import NavigatorAgent
from .agents.extractor_agent import ExtractorAgent
from .agents.llm_normalizer_agent import LLMNormalizerAgent
from .agents.validator_agent import ValidatorAgent
from .agents.qa_review_agent import QAReviewAgent
from .agents.crawl_summary_agent import CrawlSummaryAgent
from .config import load_settings
from .exporters.json_exporter import export_json
from .exporters.csv_exporter import export_csv
from .logging_setup import setup_logger
from .models import CategorySeed
from .scraping.fetcher import Fetcher
from .storage import Storage
from .utils import normalize_url_for_dedup, utc_now_iso


class Runner:
    def __init__(self, settings_path: str = "config/settings.yaml"):
        self.settings = load_settings(settings_path)
        self.logger = setup_logger(
            self.settings["logging"]["level"],
            self.settings["logging"]["file_path"],
        )
        # Concurrency is limited to product-detail pages only.
        self.max_workers = max(1, int(self.settings.get("crawl", {}).get("max_concurrent_products", 4)))
        self.storage = Storage(
            self.settings["storage"]["sqlite_path"],
            self.settings["storage"]["checkpoint_path"],
        )
        self.fetcher = Fetcher(self.settings, self.logger)
        self.category_discovery = CategoryDiscoveryAgent(self.logger)
        self.navigator = NavigatorAgent(self.logger)
        self.extractor = ExtractorAgent(self.settings, self.logger)
        self.llm = LLMNormalizerAgent(self.settings, self.logger)
        self.validator = ValidatorAgent(self.storage, self.logger)
        self.qa_review_agent = QAReviewAgent(self.settings, self.logger)
        self.crawl_summary_agent = CrawlSummaryAgent(self.settings, self.logger)

    def run(
        self,
        max_products: int | None = None,
        max_pages: int | None = None,
        disable_llm: bool = False,
        headed: bool = False,
        fresh: bool = False,
        categories_override: list[dict] | None = None,
    ) -> dict:
        # Allow CLI or UI toggles to override runtime behavior.
        if disable_llm:
            self.settings["llm"]["enabled"] = False
        if headed:
            self.settings["crawl"]["headless"] = False
            self.fetcher.headless = False

        # Restore checkpoint to support resume.
        checkpoint = self.storage.empty_checkpoint() if fresh else self.storage.load_checkpoint()
        completed_product_urls = set(checkpoint.get("completed_product_urls", []))
        completed_category_pages = set(checkpoint.get("completed_category_pages", []))
        failed_product_urls = set(checkpoint.get("failed_product_urls", []))
        stats = checkpoint.get("stats", {"scraped": 0, "failed": 0, "llm_calls": 0, "llm_attempted": 0})

        effective_max_products = max_products or self.settings["crawl"]["max_products_per_category"]
        effective_max_pages = max_pages or self.settings["crawl"]["max_pages_per_category"]
        categories_to_use = categories_override if categories_override else self.settings["site"]["categories"]

        for category_cfg in categories_to_use:
            category = CategorySeed(**category_cfg)
            self.logger.info("Starting category: %s", category.name)
            next_url = category.url
            page_number = 1
            processed_in_category = 0

            # Category pages are processed serially to preserve pagination order.
            while next_url and page_number <= effective_max_pages and processed_in_category < effective_max_products:
                normalized_page_url = normalize_url_for_dedup(next_url)
                if normalized_page_url in completed_category_pages:
                    self.logger.info("Skipping completed category page %s", normalized_page_url)
                    next_url = None
                    break

                try:
                    # Fetch and parse the category page to discover product links.
                    category_html = self.fetcher.fetch_html(next_url)
                    discovery = self.navigator.discover_from_category(
                        url=next_url,
                        html=category_html,
                        category_path=[category.name],
                        page_number=page_number,
                        max_pages=effective_max_pages,
                    )
                    self.storage.mark_url(normalized_page_url, "category", "success")
                    completed_category_pages.add(normalized_page_url)
                except Exception as exc:
                    self.logger.error("Failed category page %s: %s", next_url, exc)
                    self.storage.mark_url(normalized_page_url, "category", "failed", error_message=str(exc))
                    break

                scheduled_product_urls: set[str] = set()
                product_iter = iter(discovery.product_links)

                def submit_next(executor, in_flight: dict) -> None:
                    # Fill the worker pool while respecting product limits.
                    while (
                        len(in_flight) < self.max_workers
                        and processed_in_category + len(in_flight) < effective_max_products
                    ):
                        try:
                            product_url = next(product_iter)
                        except StopIteration:
                            return

                        normalized_product_url = normalize_url_for_dedup(product_url)
                        if normalized_product_url in completed_product_urls:
                            continue
                        if normalized_product_url in scheduled_product_urls:
                            continue

                        scheduled_product_urls.add(normalized_product_url)
                        future = executor.submit(self._process_product, product_url, [category.name])
                        in_flight[future] = (product_url, normalized_product_url)

                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    in_flight: dict = {}
                    submit_next(executor, in_flight)

                    while in_flight:
                        done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                        for future in done:
                            product_url, normalized_product_url = in_flight.pop(future)
                            try:
                                normalized = future.result()
                            except Exception as exc:
                                # Any fetch/parse/LLM failure is tracked as a failed URL.
                                self.logger.error("Failed product %s: %s", product_url, exc)
                                self.storage.mark_url(normalized_product_url, "product", "failed", error_message=str(exc))
                                failed_product_urls.add(normalized_product_url)
                                stats["failed"] += 1
                            else:
                                # Validation and persistence happen on the main thread for SQLite safety.
                                result = self.validator.validate(normalized)
                                normalized.quality_flags = result.quality_flags
                                if result.duplicate_of:
                                    self.logger.info("Skipping duplicate product %s", product_url)
                                    self.storage.mark_url(normalized_product_url, "product", "success")
                                    completed_product_urls.add(normalized_product_url)
                                elif result.is_valid:
                                    self.storage.upsert_product(normalized)
                                    self.storage.mark_url(normalized_product_url, "product", "success")
                                    completed_product_urls.add(normalized_product_url)
                                    processed_in_category += 1
                                    stats["scraped"] += 1
                                    if normalized.llm_attempted:
                                        stats["llm_attempted"] += 1
                                    if normalized.llm_used:
                                        stats["llm_calls"] += 1
                                    self.logger.info(
                                        "Saved product %s | llm_attempted=%s llm_used=%s changed=%s",
                                        normalized.product_name or product_url,
                                        normalized.llm_attempted,
                                        normalized.llm_used,
                                        normalized.llm_changed_fields,
                                    )
                                else:
                                    self.storage.mark_url(
                                        normalized_product_url,
                                        "product",
                                        "failed",
                                        error_message=",".join(result.missing_fields),
                                    )
                                    failed_product_urls.add(normalized_product_url)
                                    stats["failed"] += 1
                                    self.logger.warning("Invalid product %s missing=%s", product_url, result.missing_fields)

                            submit_next(executor, in_flight)

                next_url = discovery.next_page_url
                page_number += 1
                # Persist progress so a crash or abort can resume cleanly.
                self.storage.save_checkpoint(
                    {
                        "completed_category_pages": sorted(completed_category_pages),
                        "completed_product_urls": sorted(completed_product_urls),
                        "failed_product_urls": sorted(failed_product_urls),
                        "stats": stats,
                        "updated_at": utc_now_iso(),
                    }
                )

        self.export()

        output_dir = Path(self.settings["output"]["json_path"]).parent
        qa_report_path = str(output_dir / "qa_review_report.json")
        crawl_summary_path = str(output_dir / "crawl_quality_summary.json")

        try:
            # LLM-based QA review over the final JSON output.
            self.qa_review_agent.run(
                products_json_path=self.settings["output"]["json_path"],
                output_path=qa_report_path,
            )
        except Exception as exc:
            self.logger.warning("QA review step failed: %s", exc)

        try:
            # LLM-based run summary combining QA signals and crawl stats.
            self.crawl_summary_agent.run(
                products_json_path=self.settings["output"]["json_path"],
                qa_report_path=qa_report_path,
                stats=stats,
                output_path=crawl_summary_path,
            )
        except Exception as exc:
            self.logger.warning("Crawl quality summary step failed: %s", exc)

        return stats

    def export(self) -> None:
        # Export the current product table to JSON/CSV.
        products = self.storage.get_products()
        if self.settings["output"].get("export_json", True):
            export_json(products, self.settings["output"]["json_path"])
        if self.settings["output"].get("export_csv", True):
            export_csv(products, self.settings["output"]["csv_path"])

    def show_stats(self) -> dict:
        # Lightweight stats without running a crawl.
        return self.storage.get_stats()

    def cleanup_environment(self) -> dict:
        # Remove generated files and reset checkpoints.
        self.storage.close()

        targets = [
            "output/sample_products.json",
            "output/sample_products.csv",
            "output/safco_products.db",
            "output/qa_review_report.json",
            "output/crawl_quality_summary.json",
            "data/checkpoints/state.json",
            "logs/scraper.log",
        ]

        deleted: list[str] = []
        missing: list[str] = []

        for item in targets:
            path = Path(item)
            if path.exists():
                path.unlink()
                deleted.append(item)
            else:
                missing.append(item)

        raw_dir = Path("data/raw_html")
        raw_deleted = 0
        if raw_dir.exists():
            for child in raw_dir.iterdir():
                if child.is_file():
                    child.unlink()
                    raw_deleted += 1

        return {
            "deleted_files": deleted,
            "missing_files": missing,
            "deleted_raw_html_files": raw_deleted,
        }

    def discover_categories(self, base_url: str | None = None) -> list[dict[str, str]]:
        # Discover catalog categories from a site entry page.
        site_base = base_url or self.settings["site"]["base_url"]
        candidates = [
            f"{site_base.rstrip('/')}/catalog",
            site_base,
        ]

        for url in candidates:
            try:
                html = self.fetcher.fetch_html(url)
                categories = self.category_discovery.discover(site_base, html)
                if categories:
                    return categories
            except Exception as exc:
                self.logger.warning("Category discovery failed for %s: %s", url, exc)

        return []

    def _process_product(self, product_url: str, category_path: list[str]):
        # Worker function used by the thread pool for product pages.
        product_html = self.fetcher.fetch_html(product_url)
        raw = self.extractor.extract_product(product_url, product_html, category_path)
        normalized = self.llm.normalize(raw)
        return normalized