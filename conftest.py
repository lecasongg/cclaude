"""Pytest bootstrap: alias ``agent_factory`` to this repo so legacy test imports resolve."""
from __future__ import annotations

import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

if "agent_factory" not in sys.modules:
    pkg = types.ModuleType("agent_factory")
    pkg.__path__ = [str(_ROOT)]
    sys.modules["agent_factory"] = pkg
