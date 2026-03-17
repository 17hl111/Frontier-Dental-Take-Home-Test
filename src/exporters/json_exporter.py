"""This module exists to export product records to JSON. 
It writes a full snapshot for downstream inspection and QA. 
Possible improvement: add streaming exports for large datasets, but this prototype focuses on simplicity."""

from __future__ import annotations

import json
from ..utils import ensure_parent


def export_json(products: list[dict], path: str) -> None:
    # Write full product records with unicode preserved.
    ensure_parent(path).write_text(json.dumps(products, indent=2, ensure_ascii=False), encoding="utf-8")