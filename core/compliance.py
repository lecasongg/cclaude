from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from agent_factory.core.event_log import EventLog
from agent_factory.core.pipeline_executor import PipelineExecutor, StepExecutionContext
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.taskbook import TaskBook, load_taskbook


@dataclass(frozen=True)
class ComplianceResult:
    success: bool
    errors: list[str] = field(default_factory=list)
    cases: list[dict[str, Any]] = field(default_factory=list)


class ComplianceSuite:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def run_quick(self, workspace_root: str | Path) -> ComplianceResult:
        return self.run_with_runner(workspace_root, _mock_step_runner)

    def run_with_runner(self, workspace_root: str | Path, step_runner) -> ComplianceResult:
        workspace_root = Path(workspace_root)
        errors: list[str] = []
        cases: list[dict[str, Any]] = []
        for taskbook_path in sorted((self.root / "taskbooks").glob("*.yml")):
            case_errors = self._run_taskbook_case(taskbook_path, workspace_root / taskbook_path.stem, step_runner)
            errors.extend(case_errors)
            cases.append(
                {
                    "name": taskbook_path.stem,
                    "taskbook_path": str(taskbook_path),
                    "status": "failed" if case_errors else "passed",
                    "errors": case_errors,
                }
            )
        return ComplianceResult(success=not errors, errors=errors, cases=cases)

    def _run_taskbook_case(self, taskbook_path: Path, workspace_root: Path, step_runner) -> list[str]:
        taskbook = load_taskbook(taskbook_path)
        expected_path = self.root / "expected" / f"{taskbook_path.stem}.assert.yml"
        expected = _load_expected(expected_path)
        manager = ResourceManager(workspace_root / "marvis.db")
        for agent_id in sorted({step.agent for step in taskbook.steps}):
            manager.register_agent(agent_id, display_name=agent_id)

        executor = PipelineExecutor(
            resource_manager=manager,
            event_log=EventLog(workspace_root / "events"),
            workspace_root=workspace_root,
            step_runner=step_runner,
        )
        protected_snapshot = _snapshot_forbidden_paths(workspace_root, expected.get("forbidden_modified", []))
        run_id = executor.run(taskbook)
        return _assert_expected(taskbook, expected, manager, workspace_root, run_id, protected_snapshot)


def _mock_step_runner(context: StepExecutionContext) -> dict[str, str]:
    return {output_path: f"mock output for {context.step.step_id}" for output_path in context.output_paths}


def _load_expected(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("assert", {})


def _assert_expected(
    taskbook: TaskBook,
    expected: dict[str, Any],
    manager: ResourceManager,
    workspace_root: Path,
    run_id: str,
    protected_snapshot: dict[str, str | None] | None = None,
) -> list[str]:
    errors: list[str] = []
    expected_run_status = expected.get("run_status")
    if expected_run_status and manager.get_pipeline_run(run_id)["status"] != expected_run_status:
        errors.append(f"expected run_status {expected_run_status}")

    expected_steps = expected.get("steps", {})
    for step_id, step_expected in expected_steps.items():
        step = manager.get_step_run(run_id, step_id)
        expected_status = step_expected.get("status")
        if expected_status and step["status"] != expected_status:
            errors.append(f"expected step {step_id} status {expected_status}")
        for output_path in step_expected.get("output_exists", []):
            resolved = workspace_root / output_path.replace("{run_id}", run_id)
            if not resolved.exists():
                errors.append(f"missing expected output for step {step_id}: {resolved}")
        for content_expected in step_expected.get("output_contains", []):
            output_path = content_expected.get("path", "") if isinstance(content_expected, dict) else ""
            expected_text = content_expected.get("text", "") if isinstance(content_expected, dict) else str(content_expected)
            resolved = workspace_root / output_path.replace("{run_id}", run_id)
            if not resolved.exists():
                errors.append(f"missing expected output for content assertion on step {step_id}: {resolved}")
                continue
            if expected_text not in resolved.read_text(encoding="utf-8", errors="replace"):
                errors.append(f"missing expected content for step {step_id}: {expected_text}")
        for dependency in step_expected.get("depends_after", []):
            dependency_step = manager.get_step_run(run_id, dependency)
            if step["updated_at"] <= dependency_step["updated_at"]:
                errors.append(f"expected step {step_id} after {dependency}")

    known_steps = {step.step_id for step in taskbook.steps}
    for step_id in expected_steps:
        if step_id not in known_steps:
            errors.append(f"expected unknown step: {step_id}")
    for step_id, dependencies in expected.get("depends_after", {}).items():
        step = manager.get_step_run(run_id, step_id)
        for dependency in dependencies:
            dependency_step = manager.get_step_run(run_id, dependency)
            if step["updated_at"] <= dependency_step["updated_at"]:
                errors.append(f"expected step {step_id} after {dependency}")
    for relative_path, before_hash in (protected_snapshot or {}).items():
        after_hash = _file_hash(workspace_root / relative_path)
        if after_hash != before_hash:
            errors.append(f"forbidden path modified: {relative_path}")
    return errors


def _snapshot_forbidden_paths(workspace_root: Path, paths: list[str]) -> dict[str, str | None]:
    return {path: _file_hash(workspace_root / path) for path in paths}


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return sha256(path.read_bytes()).hexdigest()
