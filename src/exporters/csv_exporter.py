# Summary: CSV exporter with light flattening of JSON-like fields.

from __future__ import annotations

import json
import pandas as pd
from ..utils import ensure_parent


def export_csv(products: list[dict], path: str) -> None:
    # Convert list-like fields to stable string representations for CSV.
    flat_rows = []
    for item in products:
        row = dict(item)
        row["category_path"] = " > ".join(json.loads(row["category_path"]) if isinstance(row.get("category_path"), str) else row.get("category_path", []))
        for field in ["specifications_json", "image_urls_json", "alternative_products_json", "quality_flags_json", "extraction_method_json"]:
            if field in row and isinstance(row[field], str):
                try:
                    parsed = json.loads(row[field])
                    row[field] = json.dumps(parsed, ensure_ascii=False)
                except Exception:
                    pass
        flat_rows.append(row)
    df = pd.DataFrame(flat_rows)
    ensure_parent(path)
    df.to_csv(path, index=False)
