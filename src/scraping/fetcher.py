# Summary: Playwright-based HTML fetcher with retries and pacing.

from __future__ import annotations

import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential

from ..constants import DEFAULT_HEADERS


class Fetcher:
    def __init__(self, settings: dict, logger):
        self.settings = settings
        self.logger = logger
        # Crawl pacing and browser settings are configurable via YAML.
        self.delay = settings["crawl"]["request_delay_seconds"]
        self.timeout_ms = int(settings["crawl"]["timeout_seconds"] * 1000)
        self.headless = settings["crawl"].get("headless", True)
        self.wait_for_ms = settings["crawl"].get("browser_wait_for_ms", 2500)
        self.user_agent = settings["crawl"]["user_agent"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def fetch_html(self, url: str) -> str:
        # Lightweight throttle to reduce server load.
        self.logger.info("Fetching %s", url)
        time.sleep(self.delay)

        try:
            # Launch a new browser context for each request.
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent=self.user_agent,
                    extra_http_headers=DEFAULT_HEADERS,
                    viewport={"width": 1440, "height": 2200},
                )
                page = context.new_page()

                # Use domcontentloaded for initial readiness, then wait for network idle.
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)

                try:
                    page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 10000))
                except Exception:
                    pass

                # Small scrolling to trigger lazy-loaded content.
                page.wait_for_timeout(self.wait_for_ms)
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(1200)
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(800)

                html = page.content()
                browser.close()
                return html

        except PlaywrightTimeoutError as exc:
            self.logger.warning("Timeout while loading %s", url)
            raise RuntimeError(f"Playwright timeout for {url}") from exc
