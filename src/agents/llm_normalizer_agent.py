# Summary: LLM-based normalization for missing or weak product fields.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..models import RawProductRecord, NormalizedProduct
from ..utils import normalize_whitespace


class LLMNormalizerAgent:
    FIELDS_WE_ALLOW_LLM_TO_FILL = [
        "brand",
        "manufacturer",
        "sku",
        "product_code",
        "unit_or_pack_size",
        "availability",
        "description",
        "specifications",
    ]
    def __init__(self, settings: dict, logger):
        self.settings = settings
        self.logger = logger
        api_key = settings["secrets"].get("openai_api_key", "")
        # Client is optional and only built when an API key is present.
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.prompt_template = Path("src/prompts/normalize_product.txt").read_text(encoding="utf-8")

    def should_call_llm(self, raw: RawProductRecord) -> bool:
        # Fast checks to avoid unnecessary LLM calls.
        if not self.settings["llm"].get("enabled", True):
            return False
        if self.client is None:
            return False

        if any(v in (None, "") for v in [raw.brand, raw.manufacturer, raw.sku, raw.unit_or_pack_size]):
            return True

        if not raw.description:
            return True

        if not raw.specifications:
            return True

        return False

    def normalize(self, raw: RawProductRecord) -> NormalizedProduct:
        # Convert raw extraction to normalized output, optionally calling the LLM.
        base = raw.model_dump(exclude={"extraction_warnings"})

        if not self.should_call_llm(raw):
            return NormalizedProduct(
                **base,
                llm_attempted=False,
                llm_used=False,
                llm_changed_fields=[],
            )

        payload = self._build_payload(raw)
        llm_attempted = True
        parsed_llm: dict[str, Any] = {}

        try:
            # Request strict JSON from the model to simplify merging.
            response = self.client.chat.completions.create(
                model=self.settings["llm"]["model"],
                response_format={"type": "json_object"},
                temperature=0,
                messages=[
                    {"role": "system", "content": self.prompt_template},
                    {"role": "user", "content": payload},
                ],
            )
            content = response.choices[0].message.content or "{}"
            parsed_llm = json.loads(content)
            self.logger.info("LLM attempted normalization for %s", raw.product_url)
        except Exception as exc:
            # Fail open: keep rule-based fields and skip LLM changes.
            self.logger.warning("LLM normalization failed for %s: %s", raw.product_url, exc)
            parsed_llm = {}

        merged = dict(base)
        changed_fields: list[str] = []

        for field in self.FIELDS_WE_ALLOW_LLM_TO_FILL:
            llm_value = parsed_llm.get(field)

            if field == "specifications":
                # Specifications are merged with conservative rules.
                original_specs = merged.get("specifications") or {}
                merged_specs, specs_changed = self._merge_specifications(
                    existing=original_specs,
                    incoming=llm_value,
                )
                if specs_changed:
                    merged["specifications"] = merged_specs
                    changed_fields.append("specifications")
                continue

            # Only fill empty values so deterministic extraction stays authoritative.
            current_value = normalize_whitespace(merged.get(field))
            candidate_value = normalize_whitespace(llm_value) if isinstance(llm_value, str) or llm_value is None else llm_value

            if not current_value and candidate_value:
                merged[field] = candidate_value
                changed_fields.append(field)

        llm_used = len(changed_fields) > 0

        merged_extraction_method = dict(merged.get("extraction_method") or {})
        merged_extraction_method["llm_fallback_used"] = llm_used
        merged_extraction_method["llm_attempted"] = llm_attempted
        merged["extraction_method"] = merged_extraction_method

        # Track LLM usage as quality flags for downstream QA.
        quality_flags = list(merged.get("quality_flags") or [])
        if llm_attempted:
            quality_flags.append("llm_attempted")
        if llm_used:
            quality_flags.append("llm_improved_fields")
        merged["quality_flags"] = sorted(set(quality_flags))

        merged["llm_attempted"] = llm_attempted
        merged["llm_used"] = llm_used
        merged["llm_changed_fields"] = changed_fields

        return NormalizedProduct(**merged)

    def _build_payload(self, raw: RawProductRecord) -> str:
        # Build a structured JSON payload for the LLM prompt.
        max_chars = self.settings["llm"].get("max_input_chars", 6000)

        missing_fields = []
        for field in self.FIELDS_WE_ALLOW_LLM_TO_FILL:
            value = getattr(raw, field, None)
            if field == "specifications":
                if not raw.specifications:
                    missing_fields.append(field)
            elif value in (None, ""):
                missing_fields.append(field)

        structured_spec_instruction = {
            "type": "adaptive",
            "rule": "Infer a compact specifications object based on the product description. Use a natural structure derived from the product content.",
        }

        # The payload limits text sizes to control token cost.
        payload = {
            "task": "Fill only missing or weak fields. Do not overwrite strong rule-based values. specifications must remain a nested JSON object.",
            "missing_fields_only": missing_fields,
            "product_url": raw.product_url,
            "category_path": raw.category_path,
            "product_name": raw.product_name,
            "specification_structure_guidance": structured_spec_instruction,
            "existing_rule_based_values": {
                "brand": raw.brand,
                "manufacturer": raw.manufacturer,
                "sku": raw.sku,
                "product_code": raw.product_code,
                "unit_or_pack_size": raw.unit_or_pack_size,
                "availability": raw.availability,
                "description": raw.description,
                "specifications": raw.specifications,
            },
            "description_block_text": (raw.description_block_text or "")[:2500],
            "meta_description": raw.meta_description,
            "raw_specifications_text": (raw.raw_specifications_text or "")[:2000],
            "page_text_excerpt": (raw.page_text_excerpt or "")[:max_chars],
        }

        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _merge_specifications(self, existing: dict, incoming: Any) -> tuple[dict, bool]:
        # Merge specs without overwriting non-empty values.
        base = dict(existing or {})
        changed = False

        if not isinstance(incoming, dict):
            return base, False

        for key, value in incoming.items():
            normalized_key = key.strip() if isinstance(key, str) else key
            normalized_value = normalize_whitespace(value) if isinstance(value, str) else value

            if normalized_key not in base:
                if normalized_value not in (None, "", {}, []):
                    base[normalized_key] = normalized_value
                    changed = True
                continue

            current = base.get(normalized_key)

            if current in (None, "", {}, []):
                if normalized_value not in (None, "", {}, []):
                    base[normalized_key] = normalized_value
                    changed = True

        return base, changed
