"""This module exists to configure pytest imports for the project root. It ensures tests can import src without altering the runtime package layout. Possible improvement: add common fixtures for test data, but current tests are minimal."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Ensure imports work when running tests from the repo root.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))