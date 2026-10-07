from __future__ import annotations

import tempfile
from pathlib import Path


def workspace_tempdir() -> tempfile.TemporaryDirectory[str]:
    parent = Path(__file__).resolve().parents[1] / ".test-tmp"
    parent.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=parent)

