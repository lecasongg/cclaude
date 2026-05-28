from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if "agent_factory" not in sys.modules:
    pkg = types.ModuleType("agent_factory")
    pkg.__path__ = [str(_ROOT)]
    sys.modules["agent_factory"] = pkg

from agent_factory.core.compliance import ComplianceSuite, list_compliance_reports, read_compliance_report
from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.backends import build_backend
from agent_factory.core.config import apply_runtime_config, load_factory_config, load_runtime_config
from agent_factory.core.config_registry import ConfigRegistryError, load_config_registry
from agent_factory.core.event_log import EventLog
from agent_factory.core.marvis_status import build_marvis_status
from agent_factory.core.preflight import run_preflight
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.run_manifest import build_run_manifest, list_artifacts_across_runs
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.taskbook import TaskBookError, load_taskbook
from agent_factory.core.worker_runtime import WorkerRuntime
from agent_factory.core.worker_health import summarize_worker_health
from agent_factory.core.worker_step_runner import WorkerRuntimeStepRunner


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (ConfigRegistryError, TaskBookError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="marvisctl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    _add_config_arg(doctor)
    doctor.set_defaults(handler=_doctor)

    status = subparsers.add_parser("status")
    _add_config_arg(status)
    status.add_argument("--workspace", default=".")
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=_status)

    preflight = subparsers.add_parser("preflight")
    _add_config_arg(preflight)
    preflight.add_argument("--taskbook", default="")
    preflight.add_argument("--source", default="")
    preflight.add_argument("--suite", default="")
    preflight.add_argument("--json", action="store_true")
    preflight.set_defaults(handler=_preflight)

    config = subparsers.add_parser("config")
    config_subparsers = config.add_subparsers(dest="config_command", required=True)
    config_validate = config_subparsers.add_parser("validate")
    _add_config_arg(config_validate)
    config_validate.set_defaults(handler=_config_validate)
    config_render = config_subparsers.add_parser("render")
    config_render.add_argument("agent_id")
    _add_config_arg(config_render)
    config_render.set_defaults(handler=_config_render)

    agent = subparsers.add_parser("agent")
    agent_subparsers = agent.add_subparsers(dest="agent_command", required=True)
    agent_list = agent_subparsers.add_parser("list")
    _add_config_arg(agent_list)
    agent_list.set_defaults(handler=_agent_list)
    agent_check = agent_subparsers.add_parser("check")
    agent_check.add_argument("--all", action="store_true")
    _add_config_arg(agent_check)
    agent_check.set_defaults(handler=_agent_check)

    taskbook = subparsers.add_parser("taskbook")
    taskbook_subparsers = taskbook.add_subparsers(dest="taskbook_command", required=True)
    taskbook_lint = taskbook_subparsers.add_parser("lint")
    taskbook_lint.add_argument("path")
    taskbook_lint.set_defaults(handler=_taskbook_lint)
    taskbook_dry_run = taskbook_subparsers.add_parser("dry-run")
    taskbook_dry_run.add_argument("path")
    taskbook_dry_run.set_defaults(handler=_taskbook_dry_run)

    compliance = subparsers.add_parser("compliance")
    compliance_subparsers = compliance.add_subparsers(dest="compliance_command", required=True)
    compliance_run = compliance_subparsers.add_parser("run")
    compliance_run.add_argument("--suite", required=True)
    compliance_run.add_argument("--mode", choices=["quick", "model"], default="quick")
    _add_config_arg(compliance_run)
    compliance_run.add_argument("--workspace")
    compliance_run.add_argument("--report-dir")
    compliance_run.set_defaults(handler=_compliance_run)
    compliance_reports = compliance_subparsers.add_parser("reports")
    compliance_reports.add_argument("--workspace", default=".")
    compliance_reports.add_argument("--json", action="store_true")
    compliance_reports.set_defaults(handler=_compliance_reports)
    compliance_show = compliance_subparsers.add_parser("show")
    compliance_show.add_argument("filename")
    compliance_show.add_argument("--workspace", default=".")
    compliance_show.set_defaults(handler=_compliance_show)

    artifact = subparsers.add_parser("artifact")
    artifact_subparsers = artifact.add_subparsers(dest="artifact_command", required=True)
    artifact_manifest = artifact_subparsers.add_parser("manifest")
    artifact_manifest.add_argument("run_id")
    artifact_manifest.add_argument("--workspace", default=".")
    artifact_manifest.set_defaults(handler=_artifact_manifest)
    artifact_list = artifact_subparsers.add_parser("list")
    artifact_list.add_argument("--workspace", default=".")
    artifact_list.add_argument("--query", default="")
    artifact_list.add_argument("--limit", type=int, default=50)
    artifact_list.add_argument("--json", action="store_true")
    artifact_list.set_defaults(handler=_artifact_list)

    return parser


def _add_config_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="")


def _doctor(args: argparse.Namespace) -> int:
    print(f"python: {sys.version.split()[0]}")
    print(f"codex: {shutil.which('codex') or 'not found'}")
    print(f"claude: {shutil.which('claude') or shutil.which('claude.cmd') or 'not found'}")
    config_path = Path(_resolve_config_path(args.config))
    if config_path.exists():
        config = load_factory_config(config_path)
        runtime_config = load_runtime_config(config_path.parent / "runtime_config.json")
        apply_runtime_config(config, runtime_config)
        health = summarize_worker_health([worker for worker in config.workers if worker.enabled])["summary"]
        print(
            "workers: "
            f"{health['ok']}/{health['total']} ok, "
            f"missing_api_key={health['missing_api_key']}, "
            f"missing_base_url={health['missing_base_url']}, "
            f"path_warnings={health['path_warnings']}, "
            f"backend_command_warnings={health['backend_command_warnings']}"
        )
    return 0


def _status(args: argparse.Namespace) -> int:
    config_path = Path(_resolve_config_path(args.config))
    config = load_factory_config(config_path)
    runtime_config = load_runtime_config(config_path.parent / "runtime_config.json")
    apply_runtime_config(config, runtime_config)
    workers = [worker for worker in config.workers if worker.enabled]
    workspace = Path(args.workspace)
    manager = ResourceManager(workspace / "marvis.db")
    status = build_marvis_status(
        workers,
        TaskBus([worker.worker_id for worker in workers]),
        manager,
        config_path.parent / "runtime_config.json",
    )
    reports = sorted((workspace / "artifacts" / "compliance").glob("compliance-*.json")) if (workspace / "artifacts" / "compliance").exists() else []
    status["metrics"]["compliance_reports_total"] = len(reports)
    if reports:
        status["metrics"]["latest_compliance_report"] = str(reports[-1])
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        product = status["product"]
        metrics = status["metrics"]
        print(f"{product['name']} {product['blueprint_version']} | {product['progress_percent']}%")
        print(
            f"workers {metrics['workers_ready']}/{metrics['workers_total']} ready | "
            f"runs {metrics['runs_total']} total | reports {metrics['compliance_reports_total']}"
        )
        milestone_summary = status.get("milestone_summary", {})
        if milestone_summary:
            summary_text = " | ".join(
                f"{phase} {values.get('ready', 0)}/{values.get('total', 0)} ready"
                for phase, values in sorted(milestone_summary.items())
            )
            print(f"blueprint {summary_text}")
        for risk in status["risks"]:
            print(f"{risk['level']}\t{risk['message']}")
    return 0


def _preflight(args: argparse.Namespace) -> int:
    config_path = Path(_resolve_config_path(args.config))
    config = load_factory_config(config_path)
    runtime_config = load_runtime_config(config_path.parent / "runtime_config.json")
    apply_runtime_config(config, runtime_config)
    workers = [worker for worker in config.workers if worker.enabled]
    result = run_preflight(workers, args.taskbook, args.source, args.suite)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        summary = result["summary"]
        print(
            f"preflight {result['status']}: "
            f"{summary['passed']}/{summary['total']} passed, "
            f"warnings={summary['warnings']}, failed={summary['failed']}"
        )
        for check in result["checks"]:
            print(f"{check['status']}\t{check['name']}\t{check['message']}")
    return 0 if result["status"] != "failed" else 1


def _config_validate(args: argparse.Namespace) -> int:
    load_config_registry(_resolve_config_path(args.config))
    print("config ok")
    return 0


def _config_render(args: argparse.Namespace) -> int:
    registry = load_config_registry(_resolve_config_path(args.config))
    print(json.dumps(registry.render_agent(args.agent_id), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _agent_list(args: argparse.Namespace) -> int:
    registry = load_config_registry(_resolve_config_path(args.config))
    for agent_id in sorted(registry.agents):
        rendered = registry.render_agent(agent_id)
        print(f"{agent_id}\t{rendered.get('display_name', '')}\t{rendered.get('model', '')}")
    return 0


def _agent_check(args: argparse.Namespace) -> int:
    if not args.all:
        raise ConfigRegistryError("agent check requires --all in this version")
    registry = load_config_registry(_resolve_config_path(args.config))
    for agent_id in sorted(registry.agents):
        registry.render_agent(agent_id)
    print("agents ok")
    return 0


def _taskbook_lint(args: argparse.Namespace) -> int:
    load_taskbook(args.path)
    print("taskbook ok")
    return 0


def _taskbook_dry_run(args: argparse.Namespace) -> int:
    taskbook = load_taskbook(args.path)
    print(json.dumps({"title": taskbook.title, "execution_order": taskbook.execution_order()}, ensure_ascii=False, indent=2))
    return 0


def _compliance_run(args: argparse.Namespace) -> int:
    workspace = args.workspace or tempfile.mkdtemp(prefix="marvis-compliance-")
    report_dir = args.report_dir or str(Path(workspace) / "compliance-reports")
    suite = ComplianceSuite(args.suite)
    if args.mode == "quick":
        result = suite.run_quick(workspace, report_dir=report_dir)
    else:
        config_path = Path(_resolve_config_path(args.config))
        config = load_factory_config(config_path)
        runtime_config = load_runtime_config(config_path.parent / "runtime_config.json")
        apply_runtime_config(config, runtime_config)
        workers = [worker for worker in config.workers if worker.enabled]
        bus = TaskBus([worker.worker_id for worker in workers])
        artifacts = ArtifactStore(Path(workspace) / "worker-artifacts")
        runtimes = {
            worker.worker_id: WorkerRuntime(worker, bus, artifacts, build_backend(worker))
            for worker in workers
        }
        result = suite.run_with_runner(workspace, WorkerRuntimeStepRunner(runtimes), mode=args.mode, report_dir=report_dir)
    if result.success:
        print(f"compliance ok ({args.mode})")
        print(f"report: {result.report_path}")
        return 0
    for error in result.errors:
        print(error, file=sys.stderr)
    print(f"report: {result.report_path}", file=sys.stderr)
    return 1


def _compliance_reports(args: argparse.Namespace) -> int:
    reports = list_compliance_reports(Path(args.workspace) / "artifacts" / "compliance")
    if args.json:
        print(json.dumps({"reports": reports}, ensure_ascii=False, indent=2))
    else:
        if not reports:
            print("no compliance reports")
        for report in reports:
            print(f"{report['filename']}\t{report['size']}\t{report['path']}")
    return 0


def _compliance_show(args: argparse.Namespace) -> int:
    report = read_compliance_report(Path(args.workspace) / "artifacts" / "compliance", args.filename)
    print(json.dumps(report["report"], ensure_ascii=False, indent=2))
    return 0


def _artifact_manifest(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    manager = ResourceManager(workspace / "marvis.db")
    event_log_path = workspace / "events"
    event_log = EventLog(event_log_path) if event_log_path.exists() else None
    print(json.dumps(build_run_manifest(manager, workspace, args.run_id, event_log), ensure_ascii=False, indent=2))
    return 0


def _artifact_list(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    manager = ResourceManager(workspace / "marvis.db")
    artifacts = list_artifacts_across_runs(manager, workspace, query=args.query, limit=args.limit)
    if args.json:
        print(json.dumps({"artifacts": artifacts}, ensure_ascii=False, indent=2))
    elif not artifacts:
        print("no artifacts")
    else:
        for artifact in artifacts:
            print(
                f"{artifact['run_id']}\t{artifact['step_id']}\t{artifact['size']}\t{artifact['path']}"
            )
    return 0


def _resolve_config_path(config: str) -> str:
    if config:
        return config
    for name in ("agents.json", "factory_config.json", "factory_config.example.json", "config.example.json"):
        path = Path(name)
        if path.exists():
            return str(path)
    return "agents.json"


if __name__ == "__main__":
    raise SystemExit(main())
