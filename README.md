# Frontier Safco Scraper

An agent-based product scraping prototype for Safco Dental catalog pages. It demonstrates rule-first extraction, selective LLM normalization, QA review, and crawl-quality reporting.

---

## Architecture Overview

The system is composed of focused modules coordinated by a single runner:

- **Runner** (`src/runner.py`): Orchestrates crawl, normalization, validation, storage, export, QA, and summary steps.
- **Fetcher** (`src/scraping/fetcher.py`): Retrieves HTML via Playwright with retry and pacing.
- **Agents** (`src/agents/`):
  - `CategoryDiscoveryAgent`: Discovers top-level categories from the site.
  - `NavigatorAgent`: Extracts product links and pagination from category pages.
  - `ExtractorAgent`: Rule-based extraction from product pages.
  - `LLMNormalizerAgent`: Selectively fills missing or weak fields using LLM.
  - `ValidatorAgent`: Validates required fields and adds quality flags.
  - `QAReviewAgent`: LLM-based QA review for suspicious records.
  - `CrawlSummaryAgent`: LLM-based run summary.
- **Storage** (`src/storage.py`): SQLite persistence and checkpointing.
- **Exporters** (`src/exporters/`): JSON and CSV output.
- **UI** (`ui_app.py`): Streamlit interface for discovery, selection, runs, and review.

---

## Why This Approach

- **Rule-first extraction** keeps deterministic fields stable and auditable.
- **LLM fallback** is used only when it adds value, reducing cost and risk.
- **Agent separation** keeps responsibilities clear and production-ready.
- **Persistence + checkpoints** enables resumable runs and repeatable exports.

---

## Agent Responsibilities

- **CategoryDiscoveryAgent**: Discover top-level `/catalog/<category>` pages from the site navigation.
- **NavigatorAgent**: Identify product links and next-page links on category pages.
- **ExtractorAgent**: Extract fields using JSON-LD, metadata, selectors, and heuristics.
- **LLMNormalizerAgent**: Fill missing/weak fields and normalize specifications.
- **ValidatorAgent**: Enforce required fields and add quality flags.
- **QAReviewAgent**: Identify suspicious records requiring manual review.
- **CrawlSummaryAgent**: Summarize run quality and recommendations.

---

## Setup & Execution Instructions

### 1) Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Playwright browser install

```bash
playwright install chromium
```

### 3) Configure API key (optional for LLM features)

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=...
```

### 4) Run via CLI  (Please use the UI option below for better experience)

```bash
python -m src.main run
```

Optional CLI flags:

```bash
python -m src.main run --max-products 5 --max-pages 2 --disable-llm --headed --fresh
```

### 5) Run via UI  (Highly recommended)

```bash
streamlit run ui_app.py
```

UI flow:
- Click **Discover Categories** to load categories.
- Select categories to crawl.
- Click **Run Scraper**.

---

## Sample Output Dataset

Sample output files are included in `output/`:

- `output/sample_products.json`
- `output/sample_products.csv`
- `output/safco_products.db`
- `output/qa_review_report.json`
- `output/crawl_quality_summary.json`

The sample dataset includes products from at least two categories.

---

## Output Schema (Normalized Product)

The primary output schema matches `NormalizedProduct` (`src/models.py`).

Field | Type | Description
--- | --- | ---
`source_site` | string | Source site identifier (`safcodental`).
`category_path` | array[string] | Category hierarchy path.
`product_name` | string or null | Product title.
`brand` | string or null | Brand name.
`manufacturer` | string or null | Manufacturer name.
`sku` | string or null | SKU or item number.
`product_code` | string or null | Manufacturer product code.
`product_url` | string | Product detail URL.
`price_text` | string or null | Raw price string.
`price_value` | number or null | Parsed numeric price.
`currency` | string or null | Currency code (default `USD`).
`unit_or_pack_size` | string or null | Pack size or unit.
`availability` | string or null | Availability indicator.
`description` | string or null | Clean description text.
`description_block_text` | string or null | Raw description block text.
`specifications` | object | Structured attributes inferred from product content.
`raw_specifications_text` | string or null | Raw extracted spec text.
`page_text_excerpt` | string or null | Text excerpt for LLM context.
`meta_description` | string or null | Meta description.
`image_urls` | array[string] | Product image URLs.
`alternative_products` | array[object] | Related product links.
`page_type` | string | Page type label.
`raw_html_snapshot_path` | string or null | Local HTML snapshot path.
`scraped_at` | string | ISO timestamp (UTC).
`extraction_method` | object | Extraction provenance flags.
`quality_flags` | array[string] | Validation and quality flags.
`llm_attempted` | boolean | Whether LLM was called.
`llm_used` | boolean | Whether LLM changed any fields.
`llm_changed_fields` | array[string] | Fields modified by LLM.

Notes:
- `specifications` is an adaptive structure inferred from product content.
- CSV export flattens JSON-like fields into stringified JSON columns.

---

## Limitations

- Category discovery relies on `/catalog` navigation and may miss hidden categories.
- Selectors are tailored to Safco layout and can break on redesigns.
- Playwright launches a browser per request (slower than pooling).
- LLM features require a valid API key and can be disabled.
- Validation is lightweight and not a full data-quality system.

---

## Failure Handling

- **Retries**: HTML fetch is retried with exponential backoff.
- **Logging**: Errors and progress are logged to console and file.
- **Checkpointing**: Progress saved in `data/checkpoints/state.json`.
- **Deduplication**: Normalized URLs prevent duplicates.
- **LLM failure**: LLM errors fall back to rule-based data.

---

## How to Scale to Full-Site Crawling in Production

- Browser pooling to avoid per-request Chromium startup.
- Adaptive rate limiting based on status codes and latency.
- Queue-based scheduling for categories and products.
- Error-type-aware retries (network vs parse vs blocked).
- Selector monitoring and automated layout-change alerts.
- Incremental exports and partitioned storage.

---

## How to Monitor Data Quality

- Track missing-field rates (brand, price, SKU, specs).
- Monitor LLM usage and changed fields as quality signals.
- Compare specification completeness vs description length.
- Add schema validation and price/pack-size anomaly checks.
- Review QA reports for targeted manual audits.

---

## Config-Driven Execution & Secrets Management

- Settings are in `config/settings.yaml` (crawl limits, output paths, logging).
- Secrets are loaded from `.env` using `OPENAI_API_KEY`.

---

## Requirements Coverage Checklist

- Product extraction: Yes
- Structured output (CSV/JSON/SQLite): Yes
- Agentic workflow: Yes
- Dynamic content or pagination: Yes (Playwright + pagination logic)
- Runnable project: Yes
- Setup & execution instructions: Yes
- Sample output dataset: Yes
- Schema documented: Yes
- Limitations: Yes
- Failure handling: Yes
- Scaling guidance: Yes
- Data quality monitoring: Yes
