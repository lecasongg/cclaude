from __future__ import annotations

import difflib
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


def list_artifacts_across_runs(
    manager: ResourceManager,
    workspace_root: str | Path,
    query: str = "",
    limit: int = 100,
) -> list[dict]:
    workspace_root = Path(workspace_root)
    normalized_query = query.lower().strip()
    artifacts: list[dict] = []
    for run in manager.list_pipeline_runs():
        run_id = run["run_id"]
        for artifact in _list_artifacts(workspace_root, run_id, manager.list_step_runs(run_id)):
            indexed = {
                **artifact,
                "run_id": run_id,
                "run_title": run["title"],
                "run_status": run["status"],
                "updated_at": run["updated_at"],
            }
            haystack = " ".join(
                [
                    indexed["path"],
                    indexed.get("step_id", ""),
                    indexed["run_id"],
                    indexed["run_title"],
                    indexed["run_status"],
                ]
            ).lower()
            if normalized_query and normalized_query not in haystack:
                continue
            artifacts.append(indexed)
    artifacts.sort(key=lambda item: (item["updated_at"], item["path"]), reverse=True)
    return artifacts[: max(limit, 0)]


def diff_artifacts(
    workspace_root: str | Path,
    left_path: str,
    right_path: str,
    context_lines: int = 3,
) -> dict:
    workspace_root = Path(workspace_root).resolve()
    left = _resolve_artifact_path(workspace_root, left_path)
    right = _resolve_artifact_path(workspace_root, right_path)
    left_text = left.read_text(encoding="utf-8", errors="replace")
    right_text = right.read_text(encoding="utf-8", errors="replace")
    diff = list(
        difflib.unified_diff(
            left_text.splitlines(),
            right_text.splitlines(),
            fromfile=left_path,
            tofile=right_path,
            lineterm="",
            n=max(context_lines, 0),
        )
    )
    return {
        "left": left_path,
        "right": right_path,
        "left_size": left.stat().st_size,
        "right_size": right.stat().st_size,
        "diff": "\n".join(diff),
        "changed": left_text != right_text,
    }


def _resolve_artifact_path(workspace_root: Path, relative_path: str) -> Path:
    normalized = relative_path.replace("\\", "/")
    candidate = (workspace_root / normalized).resolve()
    artifact_root = (workspace_root / "artifacts" / "runs").resolve()
    if not candidate.is_relative_to(artifact_root) or not candidate.is_file():
        raise FileNotFoundError("artifact not found")
    return candidate


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
