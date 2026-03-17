# Summary: JSON exporter for product records.

from __future__ import annotations

import json
from ..utils import ensure_parent


def export_json(products: list[dict], path: str) -> None:
    # Write full product records with unicode preserved.
    ensure_parent(path).write_text(json.dumps(products, indent=2, ensure_ascii=False), encoding="utf-8")
