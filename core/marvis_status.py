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

BLUEPRINT_MILESTONES = [
    {
        "phase": "P0",
        "key": "config-registry",
        "title": "ConfigRegistry",
        "status": "ready",
        "evidence": "defaults/template/agent merge plus marvisctl config validate/render",
        "next_step": "Expose template cloning in the factory console",
    },
    {
        "phase": "P0",
        "key": "resource-manager",
        "title": "SQLite ResourceManager",
        "status": "ready",
        "evidence": "agent registry, leases, pipeline runs and step runs persist in SQLite",
        "next_step": "Add richer lease timeout diagnostics",
    },
    {
        "phase": "P0",
        "key": "event-log",
        "title": "Append-only EventLog",
        "status": "ready",
        "evidence": "run-scoped jsonl events are exposed through API and UI",
        "next_step": "Index event severity and progress payloads",
    },
    {
        "phase": "P0",
        "key": "taskbook-linter",
        "title": "TaskBook Loader And Linter",
        "status": "ready",
        "evidence": "YAML parsing, required fields, dependency DAG, input allowlist and output path checks",
        "next_step": "Add execution-time path policy checks before worker dispatch",
    },
    {
        "phase": "P0",
        "key": "pipeline-executor",
        "title": "Pipeline Executor",
        "status": "ready",
        "evidence": "multi-step dependency execution, artifacts, failure blocking and correction reruns",
        "next_step": "Support resumable running steps after server restart",
    },
    {
        "phase": "P0",
        "key": "marvisctl",
        "title": "marvisctl Operator CLI",
        "status": "ready",
        "evidence": "doctor/config/agent/taskbook/preflight/compliance/status commands",
        "next_step": "Add agent template clone and bulk validation commands",
    },
    {
        "phase": "P0",
        "key": "quick-compliance",
        "title": "Taskbook Compliance Quick Suite",
        "status": "ready",
        "evidence": "mock-mode suite covers handoff, dependency, missing-input, forbidden-write and restart-recovery contracts",
        "next_step": "Add correction-loop compliance case",
    },
    {
        "phase": "P0",
        "key": "api-expansion",
        "title": "Factory API",
        "status": "ready",
        "evidence": "runs, events, artifacts, quality, manifest, preflight and compliance endpoints",
        "next_step": "Add paginated artifact search and report comparison",
    },
    {
        "phase": "P0",
        "key": "minimal-pipeline-ui",
        "title": "Minimum Pipeline UI",
        "status": "ready",
        "evidence": "2.5D factory console can start runs, inspect steps, open artifacts and run gates",
        "next_step": "Verify desktop/mobile layout with browser automation",
    },
    {
        "phase": "P1",
        "key": "workstation-center",
        "title": "Workstation Center",
        "status": "partial",
        "evidence": "worker cards, health summary and config editing are present",
        "next_step": "Add tag/group management and template-based worker creation",
    },
    {
        "phase": "P1",
        "key": "pipeline-god-view",
        "title": "Pipeline God View",
        "status": "partial",
        "evidence": "isometric floor shows multiple lines and step machines",
        "next_step": "Increase spatial clarity, density controls and multi-run filtering",
    },
    {
        "phase": "P1",
        "key": "artifact-audit",
        "title": "Artifact Library And Audit",
        "status": "partial",
        "evidence": "run manifests and artifact drawers expose provenance per run",
        "next_step": "Add cross-run artifact index and diffable report views",
    },
    {
        "phase": "P1",
        "key": "model-compliance",
        "title": "Model Compliance Suite",
        "status": "partial",
        "evidence": "model mode can run against configured worker backends",
        "next_step": "Add baseline reports for Moon Bridge / DeepSeek model changes",
    },
    {
        "phase": "P1",
        "key": "agent-isolation",
        "title": "Agent Isolation And Permission Boundary",
        "status": "partial",
        "evidence": "per-worker workspace/profile/skills paths exist; policy enforcement is still light",
        "next_step": "Add path policy checks before worker execution",
    },
    {
        "phase": "P2",
        "key": "scalable-platform",
        "title": "Scalable Multi-scheduler Platform",
        "status": "planned",
        "evidence": "single-machine factory runtime is the current scope",
        "next_step": "Design multi-scheduler coordination after P1 stabilizes",
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
        "milestones": [dict(item) for item in BLUEPRINT_MILESTONES],
        "milestone_summary": _milestone_summary(BLUEPRINT_MILESTONES),
        "risks": _risks(worker_health["summary"]),
    }


def blueprint_progress_percent() -> int:
    total = sum(item["weight"] for item in CAPABILITY_LEDGER)
    earned = sum(item["earned"] for item in CAPABILITY_LEDGER)
    return round((earned / total) * 100) if total else 0


def _count_status(rows: list[dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows if row.get("status") == status)


def _milestone_summary(milestones: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for milestone in milestones:
        phase = milestone["phase"]
        status = milestone["status"]
        phase_summary = summary.setdefault(phase, {"ready": 0, "partial": 0, "planned": 0, "total": 0})
        phase_summary[status] = phase_summary.get(status, 0) + 1
        phase_summary["total"] += 1
    return summary


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
