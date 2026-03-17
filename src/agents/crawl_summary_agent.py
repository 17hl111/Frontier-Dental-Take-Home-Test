# Summary: LLM-based run summary using products, QA report, and metrics.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI


class CrawlSummaryAgent:
    def __init__(self, settings: dict, logger):
        self.settings = settings
        self.logger = logger
        api_key = settings["secrets"].get("openai_api_key", "")
        # Disable the client when LLM use is turned off or no API key is set.
        self.client = OpenAI(api_key=api_key) if api_key and settings["llm"].get("enabled", True) else None
        self.prompt_template = Path("src/prompts/crawl_quality_summary.txt").read_text(encoding="utf-8")

    def run(
        self,
        products_json_path: str,
        qa_report_path: str,
        stats: dict[str, Any],
        output_path: str,
    ) -> dict[str, Any]:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if self.client is None:
            # Skip gracefully when LLM is unavailable.
            summary = {
                "status": "skipped",
                "reason": "LLM disabled or OPENAI_API_KEY not configured.",
                "raw_metrics": stats,
            }
            output_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
            return summary

        products_file = Path(products_json_path)
        qa_file = Path(qa_report_path)

        if not products_file.exists():
            # Avoid failures when no products are present.
            summary = {
                "status": "skipped",
                "reason": f"Products file not found: {products_json_path}",
                "raw_metrics": stats,
            }
            output_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
            return summary

        products = json.loads(products_file.read_text(encoding="utf-8"))
        qa_report = {}
        if qa_file.exists():
            qa_report = json.loads(qa_file.read_text(encoding="utf-8"))

        payload = {
            "task": (
                "Generate a structured crawl quality summary based on run-level metrics, product output, "
                "and the QA review report. Keep it concise and operational."
            ),
            "run_metrics": stats,
            "products": products,
            "qa_report": qa_report,
        }

        try:
            # Request JSON output to normalize downstream parsing.
            response = self.client.chat.completions.create(
                model=self.settings["llm"]["model"],
                response_format={"type": "json_object"},
                temperature=0,
                messages=[
                    {"role": "system", "content": self.prompt_template},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            )
            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)
        except Exception as exc:
            # Keep the summary file valid even on errors.
            self.logger.warning("Crawl quality summary generation failed: %s", exc)
            parsed = {
                "status": "failed",
                "reason": str(exc),
                "raw_metrics": stats,
            }

        output_file.write_text(
            json.dumps(parsed, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return parsed
