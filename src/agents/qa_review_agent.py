# Summary: LLM-driven QA review for suspicious product records.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI


class QAReviewAgent:
    def __init__(self, settings: dict, logger):
        self.settings = settings
        self.logger = logger
        api_key = settings["secrets"].get("openai_api_key", "")
        # Disable the client when LLM use is turned off or no API key is set.
        self.client = OpenAI(api_key=api_key) if api_key and settings["llm"].get("enabled", True) else None
        self.prompt_template = Path("src/prompts/qa_review_report.txt").read_text(encoding="utf-8")

    def run(self, products_json_path: str, output_path: str) -> dict[str, Any]:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if self.client is None:
            # Skip gracefully when LLM is unavailable.
            report = {
                "reviewed_products": 0,
                "flagged_products": 0,
                "reviews": [],
                "status": "skipped",
                "reason": "LLM disabled or OPENAI_API_KEY not configured.",
            }
            output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            return report

        products_file = Path(products_json_path)
        if not products_file.exists():
            # Avoid raising errors when no products are available.
            report = {
                "reviewed_products": 0,
                "flagged_products": 0,
                "reviews": [],
                "status": "skipped",
                "reason": f"Products file not found: {products_json_path}",
            }
            output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            return report

        products = json.loads(products_file.read_text(encoding="utf-8"))
        if not isinstance(products, list):
            # Fail fast if the JSON output is not a list.
            report = {
                "reviewed_products": 0,
                "flagged_products": 0,
                "reviews": [],
                "status": "skipped",
                "reason": "Products JSON is not a list.",
            }
            output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            return report

        payload = {
            "task": (
                "Review the full crawled product dataset and identify only suspicious or low-confidence records. "
                "If a product looks fine, do not include it in the reviews array."
            ),
            "products": products,
        }

        try:
            # Request JSON output to normalize report parsing.
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
            # Record failure details but keep output file usable.
            self.logger.warning("QA review generation failed: %s", exc)
            parsed = {
                "reviewed_products": len(products),
                "flagged_products": 0,
                "reviews": [],
                "status": "failed",
                "reason": str(exc),
            }

        normalized_report = {
            # Defensive defaults guard against malformed LLM output.
            "reviewed_products": parsed.get("reviewed_products", len(products)),
            "flagged_products": parsed.get("flagged_products", len(parsed.get("reviews", []))),
            "reviews": parsed.get("reviews", []),
            "status": parsed.get("status", "completed"),
            "summary": parsed.get("summary"),
        }

        output_file.write_text(
            json.dumps(normalized_report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return normalized_report
