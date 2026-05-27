from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_factory.core.models import WorkerConfig
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.worker_health import summarize_worker_health


BLUEPRINT_TARGET_PERCENT = 80

CAPABILITY_LEDGER = [
    {
        "key": "worker-runtime",
        "status": "ready",
        "evidence": "Claude CLI, Codex CLI, OpenAI-compatible and fake backends",
        "weight": 10,
        "earned": 10,
    },
    {
        "key": "taskbook-pipeline",
        "status": "ready",
        "evidence": "TaskBook lint, dependency order and pipeline execution",
        "weight": 12,
        "earned": 12,
    },
    {
        "key": "file-handoff",
        "status": "ready",
        "evidence": "Step outputs are indexed as file-level artifacts",
        "weight": 10,
        "earned": 10,
    },
    {
        "key": "quality-gate",
        "status": "ready",
        "evidence": "Per-step self-check terms and run quality summary",
        "weight": 10,
        "earned": 10,
    },
    {
        "key": "correction-rerun",
        "status": "ready",
        "evidence": "Rerun from a selected step with correction context",
        "weight": 8,
        "earned": 8,
    },
    {
        "key": "run-manifest",
        "status": "ready",
        "evidence": "Structured production manifest for each run",
        "weight": 8,
        "earned": 8,
    },
    {
        "key": "compliance-suite",
        "status": "ready",
        "evidence": "Quick/model compliance modes plus persisted compliance reports",
        "weight": 12,
        "earned": 10,
    },
    {
        "key": "factory-console-ui",
        "status": "partial",
        "evidence": "2.5D factory floor control room with live API wiring",
        "weight": 10,
        "earned": 6,
    },
    {
        "key": "run-preflight",
        "status": "ready",
        "evidence": "Launch gate checks taskbook, source path, worker health and compliance suite",
        "weight": 8,
        "earned": 6,
    },
    {
        "key": "agent-isolation",
        "status": "partial",
        "evidence": "Per-worker workspace/profile/skills paths; stronger sandbox policy pending",
        "weight": 6,
        "earned": 0,
    },
    {
        "key": "multi-module-migration",
        "status": "planned",
        "evidence": "Migration/code-change loops after reverse -> docs -> tests",
        "weight": 6,
        "earned": 0,
    },
]


def build_marvis_status(
    workers: list[WorkerConfig],
    bus: TaskBus,
    resource_manager: ResourceManager | None = None,
    runtime_config_path: Path | None = None,
) -> dict[str, Any]:
    runs = resource_manager.list_pipeline_runs() if resource_manager else []
    tasks = bus.list_tasks()
    worker_health = summarize_worker_health(workers)

    return {
        "product": {
            "name": "Marvis AI Factory Console",
            "blueprint_version": "v0.3",
            "stage": "factory-floor prototype",
            "primary_scenario": "legacy-system modernization",
            "progress_percent": blueprint_progress_percent(),
            "target_percent": BLUEPRINT_TARGET_PERCENT,
        },
        "metrics": {
            "workers_total": len(workers),
            "workers_ready": worker_health["summary"]["ok"],
            "tasks_total": len(tasks),
            "runs_total": len(runs),
            "runs_succeeded": _count_status(runs, "succeeded"),
            "runs_failed": _count_status(runs, "failed"),
            "runs_blocked": _count_status(runs, "blocked"),
            "runtime_config_persistence": runtime_config_path is not None,
        },
        "capabilities": [dict(item) for item in CAPABILITY_LEDGER],
        "risks": _risks(worker_health["summary"]),
    }


def blueprint_progress_percent() -> int:
    total = sum(item["weight"] for item in CAPABILITY_LEDGER)
    earned = sum(item["earned"] for item in CAPABILITY_LEDGER)
    return round((earned / total) * 100) if total else 0


def _count_status(rows: list[dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows if row.get("status") == status)


def _risks(summary: dict[str, int | bool]) -> list[dict[str, str]]:
    risks = []
    if summary.get("missing_api_key"):
        risks.append({"level": "warning", "message": f"{summary['missing_api_key']} workers are missing API keys"})
    if summary.get("missing_base_url"):
        risks.append({"level": "warning", "message": f"{summary['missing_base_url']} workers are missing base URLs"})
    if summary.get("path_warnings"):
        risks.append({"level": "warning", "message": f"{summary['path_warnings']} worker paths need attention"})
    if summary.get("backend_command_warnings"):
        risks.append(
            {
                "level": "warning",
                "message": f"{summary['backend_command_warnings']} backend commands are not available on PATH",
            }
        )
    if not risks:
        risks.append({"level": "ok", "message": "Factory health checks are clear"})
    return risks
