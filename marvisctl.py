from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from agent_factory.core.compliance import ComplianceSuite
from agent_factory.core.config_registry import ConfigRegistryError, load_config_registry
from agent_factory.core.taskbook import TaskBookError, load_taskbook


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
    doctor.set_defaults(handler=_doctor)

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
    compliance_run.add_argument("--mode", choices=["quick"], default="quick")
    compliance_run.add_argument("--workspace")
    compliance_run.set_defaults(handler=_compliance_run)

    return parser


def _add_config_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="")


def _doctor(_args: argparse.Namespace) -> int:
    print(f"python: {sys.version.split()[0]}")
    print(f"codex: {shutil.which('codex') or 'not found'}")
    print(f"claude: {shutil.which('claude') or shutil.which('claude.cmd') or 'not found'}")
    return 0


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
    result = ComplianceSuite(args.suite).run_quick(workspace)
    if result.success:
        print("compliance ok")
        return 0
    for error in result.errors:
        print(error, file=sys.stderr)
    return 1


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
