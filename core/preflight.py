from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_factory.core.models import WorkerConfig
from agent_factory.core.taskbook import TaskBookError, load_taskbook
from agent_factory.core.worker_health import summarize_worker_health


def run_preflight(
    workers: list[WorkerConfig],
    taskbook_path: str = "",
    source_path: str = "",
    compliance_suite_path: str = "",
) -> dict[str, Any]:
    checks = []
    worker_ids = {worker.worker_id for worker in workers}

    taskbook = None
    if taskbook_path:
        try:
            taskbook = load_taskbook(taskbook_path)
            checks.append(_check("taskbook", "passed", f"{taskbook.title} · {len(taskbook.steps)} steps"))
            missing_agents = sorted({step.agent for step in taskbook.steps} - worker_ids)
            if missing_agents:
                checks.append(_check("taskbook_agents", "failed", f"unknown agents: {', '.join(missing_agents)}"))
            else:
                checks.append(_check("taskbook_agents", "passed", "all step agents are registered"))
        except (OSError, TaskBookError) as exc:
            checks.append(_check("taskbook", "failed", str(exc)))
    else:
        checks.append(_check("taskbook", "warning", "no taskbook path supplied"))

    if source_path:
        resolved = Path(source_path)
        if resolved.exists():
            files = [resolved] if resolved.is_file() else [path for path in resolved.rglob("*") if path.is_file()]
            checks.append(_check("source", "passed", f"{len(files)} source files available"))
        else:
            checks.append(_check("source", "failed", "source path not found"))
    else:
        checks.append(_check("source", "warning", "no source path supplied"))

    worker_health = summarize_worker_health(workers)
    checks.append(
        _check(
            "worker_health",
            "passed" if worker_health["summary"]["warning"] == 0 else "warning",
            f"{worker_health['summary']['ok']}/{worker_health['summary']['total']} workers ready",
        )
    )

    if compliance_suite_path:
        suite = Path(compliance_suite_path)
        taskbooks = sorted((suite / "taskbooks").glob("*.yml")) if suite.exists() else []
        expected = suite / "expected"
        if taskbooks and expected.exists():
            checks.append(_check("compliance_suite", "passed", f"{len(taskbooks)} cases available"))
        elif suite.exists():
            checks.append(_check("compliance_suite", "warning", "suite exists but taskbooks/expected are incomplete"))
        else:
            checks.append(_check("compliance_suite", "failed", "suite path not found"))

    failed = sum(1 for check in checks if check["status"] == "failed")
    warnings = sum(1 for check in checks if check["status"] == "warning")
    return {
        "status": "failed" if failed else "warning" if warnings else "passed",
        "summary": {"passed": sum(1 for check in checks if check["status"] == "passed"), "warnings": warnings, "failed": failed, "total": len(checks)},
        "checks": checks,
    }


def _check(name: str, status: str, message: str) -> dict[str, str]:
    return {"name": name, "status": status, "message": message}
