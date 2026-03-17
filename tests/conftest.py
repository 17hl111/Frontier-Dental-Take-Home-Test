# Summary: Pytest configuration to add project root to sys.path.

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Ensure imports work when running tests from the repo root.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
