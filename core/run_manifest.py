from __future__ import annotations

from pathlib import Path

from agent_factory.core.event_log import EventLog
from agent_factory.core.quality import evaluate_run_quality
from agent_factory.core.resource_manager import ResourceManager


def build_run_manifest(
    manager: ResourceManager,
    workspace_root: str | Path,
    run_id: str,
    event_log: EventLog | None = None,
) -> dict:
    workspace_root = Path(workspace_root)
    run = manager.get_pipeline_run(run_id)
    steps = manager.list_step_runs(run_id)
    artifacts = _list_artifacts(workspace_root, run_id, steps)
    return {
        "manifest_version": 1,
        "run": run,
        "steps": steps,
        "artifacts": artifacts,
        "quality": evaluate_run_quality(manager, workspace_root, run_id),
        "events": event_log.read_events(run_id) if event_log is not None else [],
    }


def _list_artifacts(workspace_root: Path, run_id: str, steps: list[dict]) -> list[dict]:
    step_by_output: dict[str, str] = {}
    for step in steps:
        for output_path in step["outputs"]:
            resolved = (workspace_root / output_path.replace("{run_id}", run_id)).as_posix()
            step_by_output[resolved] = step["step_id"]

    run_root = workspace_root / "artifacts" / "runs" / run_id
    if not run_root.exists():
        return []

    artifacts = []
    for path in sorted(run_root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(workspace_root).as_posix()
        artifacts.append(
            {
                "path": relative_path,
                "size": path.stat().st_size,
                "exists": True,
                "step_id": step_by_output.get(path.as_posix(), _infer_step_id(workspace_root, run_id, relative_path)),
            }
        )
    return artifacts


def _infer_step_id(workspace_root: Path, run_id: str, relative_path: str) -> str:
    prefix = f"artifacts/runs/{run_id}/"
    if not relative_path.startswith(prefix):
        return ""
    remainder = relative_path[len(prefix) :]
    return remainder.split("/", 1)[0] if "/" in remainder else ""
