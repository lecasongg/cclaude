from __future__ import annotations

import os
import uuid
from pathlib import Path


def pytest_configure(config) -> None:
    if config.option.basetemp:
        return

    repo_root = Path(__file__).resolve().parents[1]
    base_parent = repo_root / ".tmp" / "pytest-runs"
    base_parent.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(base_parent / f"{os.getpid()}-{uuid.uuid4().hex}")
