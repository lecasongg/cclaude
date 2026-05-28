from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
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
    suite_path: str = ""
    mode: str = "quick"
    workspace_root: str = ""
    report_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "errors": self.errors,
            "cases": self.cases,
            "suite_path": self.suite_path,
            "mode": self.mode,
            "workspace_root": self.workspace_root,
            "report_path": self.report_path,
        }


class ComplianceSuite:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def run_quick(self, workspace_root: str | Path, report_dir: str | Path | None = None) -> ComplianceResult:
        return self.run_with_runner(workspace_root, _mock_step_runner, mode="quick", report_dir=report_dir)

    def run_with_runner(
        self,
        workspace_root: str | Path,
        step_runner,
        mode: str = "model",
        report_dir: str | Path | None = None,
    ) -> ComplianceResult:
        workspace_root = Path(workspace_root)
        errors: list[str] = []
        cases: list[dict[str, Any]] = []
        for taskbook_path in sorted((self.root / "taskbooks").glob("*.yml")):
            case_errors, expected_result = self._run_taskbook_case(taskbook_path, workspace_root / taskbook_path.stem, step_runner)
            case_passed = _case_passed(case_errors, expected_result)
            if not case_passed:
                errors.extend(case_errors or [f"case {taskbook_path.stem} expected {expected_result}"])
            cases.append(
                {
                    "name": taskbook_path.stem,
                    "taskbook_path": str(taskbook_path),
                    "status": "passed" if case_passed else "failed",
                    "expected_result": expected_result,
                    "errors": case_errors,
                }
            )
        result = ComplianceResult(
            success=not errors,
            errors=errors,
            cases=cases,
            suite_path=str(self.root),
            mode=mode,
            workspace_root=str(workspace_root),
        )
        if report_dir:
            report_path = write_compliance_report(result, report_dir)
            result = replace(result, report_path=str(report_path))
        return result

    def _run_taskbook_case(self, taskbook_path: Path, workspace_root: Path, step_runner) -> tuple[list[str], str]:
        taskbook = load_taskbook(taskbook_path)
        expected_path = self.root / "expected" / f"{taskbook_path.stem}.assert.yml"
        expected = _load_expected(expected_path)
        _install_case_fixtures(self.root / "fixtures" / taskbook_path.stem, workspace_root)
        manager = ResourceManager(workspace_root / "marvis.db")
        for agent_id in sorted({step.agent for step in taskbook.steps}):
            manager.register_agent(agent_id, display_name=agent_id)
        _seed_reconcile_state(expected.get("reconcile_on_startup", {}), manager, taskbook)

        executor = PipelineExecutor(
            resource_manager=manager,
            event_log=EventLog(workspace_root / "events"),
            workspace_root=workspace_root,
            step_runner=step_runner,
        )
        protected_snapshot = _snapshot_forbidden_paths(workspace_root, expected.get("forbidden_modified", []))
        if expected.get("reconcile_on_startup"):
            run_id = _first_pipeline_run_id(manager)
            summary = manager.reconcile_on_startup()
            return (
                _assert_expected(taskbook, expected, manager, workspace_root, run_id, protected_snapshot, reconcile_summary=summary),
                expected.get("expected_result", "passed"),
            )
        if expected.get("correction_loop"):
            run_id = executor.run(taskbook)
            correction = expected["correction_loop"]
            executor.rerun_from_step(run_id, taskbook, correction["step_id"], correction=correction.get("text", ""))
            return _assert_expected(taskbook, expected, manager, workspace_root, run_id, protected_snapshot), expected.get("expected_result", "passed")
        run_id = executor.run(taskbook)
        return _assert_expected(taskbook, expected, manager, workspace_root, run_id, protected_snapshot), expected.get("expected_result", "passed")


def _mock_step_runner(context: StepExecutionContext) -> dict[str, str]:
    if "fail-before-correction" in context.step.objective and not context.correction:
        raise RuntimeError("compliance correction required")
    return {output_path: f"mock output for {context.step.step_id}" for output_path in context.output_paths}


def _case_passed(case_errors: list[str], expected_result: str) -> bool:
    if expected_result == "failed":
        return bool(case_errors)
    return not case_errors


def _install_case_fixtures(fixture_root: Path, workspace_root: Path) -> None:
    if not fixture_root.exists():
        return
    workspace_root.mkdir(parents=True, exist_ok=True)
    for item in fixture_root.iterdir():
        target = workspace_root / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _seed_reconcile_state(reconcile_expected: dict[str, Any], manager: ResourceManager, taskbook: TaskBook) -> None:
    if not reconcile_expected:
        return
    run_id = manager.create_pipeline_run(taskbook.title, taskbook_path="compliance-restart-recovery")
    for step in taskbook.steps:
        manager.create_step_run(
            run_id,
            step_id=step.step_id,
            agent_id=step.agent,
            objective=step.objective,
            depends_on=step.depends_on,
            outputs=[item.path for item in step.outputs],
            self_check=step.self_check,
        )
    manager.acquire_lease(taskbook.steps[0].agent, run_id, owner="compliance-reconcile")
    manager.update_pipeline_status(run_id, reconcile_expected.get("initial_run_status", "running"))
    manager.update_step_status(run_id, taskbook.steps[0].step_id, reconcile_expected.get("initial_step_status", "running"))


def _first_pipeline_run_id(manager: ResourceManager) -> str:
    runs = manager.list_pipeline_runs()
    if not runs:
        raise RuntimeError("missing seeded pipeline run")
    return runs[-1]["run_id"]


def write_compliance_report(result: ComplianceResult, report_dir: str | Path) -> Path:
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    status = "passed" if result.success else "failed"
    path = report_dir / f"compliance-{result.mode}-{timestamp}-{status}.json"
    body = result.to_dict()
    body["report_path"] = str(path)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_compliance_reports(report_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(report_dir)
    reports = []
    if root.exists():
        for path in sorted(root.glob("compliance-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            reports.append(
                {
                    "filename": path.name,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "updated_at": path.stat().st_mtime,
                }
            )
    return reports


def read_compliance_report(report_dir: str | Path, filename: str) -> dict[str, Any]:
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        raise FileNotFoundError("compliance report not found")
    path = Path(report_dir) / filename
    if not path.exists():
        raise FileNotFoundError("compliance report not found")
    return {"filename": filename, "path": str(path), "report": json.loads(path.read_text(encoding="utf-8"))}


def write_compliance_baseline(report_dir: str | Path, name: str, report_filename: str) -> Path:
    if not _valid_baseline_name(name):
        raise FileNotFoundError("compliance baseline not found")
    report = read_compliance_report(report_dir, report_filename)
    baseline_dir = Path(report_dir) / "baselines"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    path = baseline_dir / f"{name}.json"
    path.write_text(json.dumps(report["report"], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_compliance_baselines(report_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(report_dir) / "baselines"
    baselines = []
    if root.exists():
        for path in sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            report = json.loads(path.read_text(encoding="utf-8"))
            baselines.append(
                {
                    "name": path.stem,
                    "filename": path.name,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "updated_at": path.stat().st_mtime,
                    "success": bool(report.get("success")),
                    "mode": report.get("mode", ""),
                    "cases": len(report.get("cases", [])),
                }
            )
    return baselines


def compare_compliance_baseline(report_dir: str | Path, name: str, report_filename: str) -> dict[str, Any]:
    if not _valid_baseline_name(name):
        raise FileNotFoundError("compliance baseline not found")
    baseline_path = Path(report_dir) / "baselines" / f"{name}.json"
    if not baseline_path.exists():
        raise FileNotFoundError("compliance baseline not found")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = read_compliance_report(report_dir, report_filename)["report"]
    baseline_cases = {case["name"]: case.get("status", "") for case in baseline.get("cases", [])}
    current_cases = {case["name"]: case.get("status", "") for case in current.get("cases", [])}
    regressions = [
        {"name": name, "baseline": baseline_cases[name], "current": current_cases.get(name, "missing")}
        for name in sorted(baseline_cases)
        if baseline_cases[name] == "passed" and current_cases.get(name) != "passed"
    ]
    new_failures = [
        {"name": name, "current": status}
        for name, status in sorted(current_cases.items())
        if name not in baseline_cases and status != "passed"
    ]
    return {
        "baseline": name,
        "report": report_filename,
        "passed": not regressions and not new_failures and bool(current.get("success")),
        "regressions": regressions,
        "new_failures": new_failures,
        "baseline_success": bool(baseline.get("success")),
        "current_success": bool(current.get("success")),
    }


def _valid_baseline_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", name.strip()))


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
    reconcile_summary: dict[str, int] | None = None,
) -> list[str]:
    errors: list[str] = []
    expected_run_status = expected.get("run_status")
    if expected_run_status and manager.get_pipeline_run(run_id)["status"] != expected_run_status:
        errors.append(f"expected run_status {expected_run_status}")

    correction_expected = expected.get("correction_loop", {})
    if correction_expected:
        events = EventLog(workspace_root / "events").read_events(run_id)
        event_types = [event["type"] for event in events]
        for event_type in ("step_failed", "step_rerun_requested", "correction_added", "run_succeeded"):
            if event_type not in event_types:
                errors.append(f"missing correction-loop event: {event_type}")

    reconcile_expected = expected.get("reconcile_on_startup", {})
    if reconcile_expected:
        for key, expected_value in reconcile_expected.get("summary", {}).items():
            actual_value = (reconcile_summary or {}).get(key)
            if actual_value != expected_value:
                errors.append(f"expected reconcile summary {key}={expected_value}, got {actual_value}")
        expected_agent_status = reconcile_expected.get("agent_status")
        if expected_agent_status:
            for agent_id in sorted({step.agent for step in taskbook.steps}):
                actual = manager.get_agent_state(agent_id)["status"]
                if actual != expected_agent_status:
                    errors.append(f"expected agent {agent_id} status {expected_agent_status}, got {actual}")

    for input_path in expected.get("input_exists", []):
        resolved = workspace_root / input_path.replace("{run_id}", run_id)
        if not resolved.exists():
            errors.append(f"missing expected input: {resolved}")

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
