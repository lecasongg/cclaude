from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_factory.core.models import WorkerConfig
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.worker_health import summarize_worker_health


BLUEPRINT_PROGRESS_PERCENT = 68
BLUEPRINT_TARGET_PERCENT = 80


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
            "progress_percent": BLUEPRINT_PROGRESS_PERCENT,
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
        "capabilities": [
            _capability("worker-runtime", "ready", "Claude CLI, Codex CLI, OpenAI-compatible and fake backends"),
            _capability("taskbook-pipeline", "ready", "TaskBook lint, dependency order and pipeline execution"),
            _capability("file-handoff", "ready", "Step outputs are indexed as file-level artifacts"),
            _capability("quality-gate", "ready", "Per-step self-check terms and run quality summary"),
            _capability("correction-rerun", "ready", "Rerun from a selected step with correction context"),
            _capability("run-manifest", "ready", "Structured production manifest for each run"),
            _capability("compliance-suite", "ready", "Quick and model compliance modes"),
            _capability("factory-console-ui", "partial", "2.5D factory floor control room with live API wiring"),
            _capability("agent-isolation", "partial", "Per-worker workspace/profile/skills paths; stronger sandbox policy pending"),
            _capability("multi-module-migration", "planned", "Migration/code-change loops after reverse -> docs -> tests"),
        ],
        "risks": _risks(worker_health["summary"]),
    }


def _capability(key: str, status: str, evidence: str) -> dict[str, str]:
    return {"key": key, "status": status, "evidence": evidence}


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
