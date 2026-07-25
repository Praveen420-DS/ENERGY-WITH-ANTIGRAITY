"""Shared immutable production-package fixtures for Week 3 tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "models" / "production" / "current.json"


def example_request() -> dict[str, Any]:
    """Read the committed example request through the active manifest."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    example_path = (
        MANIFEST.parent
        / manifest["version_directory"]
        / "example_request.json"
    )
    return json.loads(example_path.read_text(encoding="utf-8"))
