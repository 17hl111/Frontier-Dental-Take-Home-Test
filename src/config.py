"""This module exists to load YAML settings and merge in environment secrets. 
It keeps configuration parsing isolated so the rest of the code can depend on a simple dict. 
Possible improvement: validate the config with a schema or pydantic model."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import yaml
from dotenv import load_dotenv


def load_settings(path: str | Path = "config/settings.yaml") -> dict[str, Any]:
    # Read .env first so secrets can be injected into the config object.
    load_dotenv()
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data.setdefault("secrets", {})
    # Store API keys inside the in-memory settings only.
    data["secrets"]["openai_api_key"] = os.getenv("OPENAI_API_KEY", "")
    return data