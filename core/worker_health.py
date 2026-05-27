from __future__ import annotations

import os
import shutil
from pathlib import Path

from agent_factory.core.models import WorkerConfig


def check_worker_health(config: WorkerConfig) -> dict:
    checks = [
        _check_api_key(config),
        _check_base_url(config),
        _check_path("workspace_dir", config.workspace_dir),
        _check_path("profile_dir", config.profile_dir),
        _check_path("skills_dir", config.skills_dir),
        _check_backend_command(config),
    ]
    status = "ok" if all(check["status"] == "passed" for check in checks) else "warning"
    return {
        "worker_id": config.worker_id,
        "status": status,
        "checks": checks,
    }


def _check_api_key(config: WorkerConfig) -> dict:
    configured = bool(os.environ.get(config.api_key_env))
    return {
        "name": "api_key",
        "status": "passed" if configured else "failed",
        "message": f"{config.api_key_env} configured" if configured else f"missing {config.api_key_env}",
    }


def _check_base_url(config: WorkerConfig) -> dict:
    requires_base_url = config.backend_type in {"codex_cli", "claude_cli", "openai_compatible"}
    ok = bool(config.base_url) or not requires_base_url
    return {
        "name": "base_url",
        "status": "passed" if ok else "failed",
        "message": config.base_url or "missing base_url",
    }


def _check_path(name: str, value: str) -> dict:
    path = Path(value)
    return {
        "name": name,
        "status": "passed" if path.exists() else "warning",
        "message": str(path),
    }


def _check_backend_command(config: WorkerConfig) -> dict:
    command = ""
    if config.backend_type == "codex_cli":
        command = "codex"
    elif config.backend_type == "claude_cli":
        command = "claude"
    if not command:
        return {"name": "backend_command", "status": "passed", "message": config.backend_type}
    resolved = shutil.which(command) or shutil.which(f"{command}.cmd") or shutil.which(f"{command}.exe")
    return {
        "name": "backend_command",
        "status": "passed" if resolved else "warning",
        "message": resolved or f"{command} not found on PATH",
    }
