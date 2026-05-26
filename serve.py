"""Launcher: alias ``agent_factory`` to this repo, then run ``worker_server``.

The legacy code imports via ``agent_factory.core.*`` from a previous checkout
named ``agent_factory``. This checkout is named ``cclaude``; mirror the
``conftest.py`` alias at runtime so the server starts without touching
backend source.
"""
from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

if "agent_factory" not in sys.modules:
    pkg = types.ModuleType("agent_factory")
    pkg.__path__ = [str(_ROOT)]
    sys.modules["agent_factory"] = pkg

runpy.run_path(str(_ROOT / "worker_server.py"), run_name="__main__")
