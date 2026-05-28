import json
import subprocess
import sys
import textwrap

import marvisctl
from agent_factory.core.resource_manager import ResourceManager


def test_marvisctl_config_validate_and_render(tmp_path, capsys):
    config_path = _write_agent_config(tmp_path)

    assert marvisctl.main(["config", "validate", "--config", str(config_path)]) == 0
    assert "config ok" in capsys.readouterr().out

    assert marvisctl.main(["config", "render", "niuma-1", "--config", str(config_path)]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["worker_id"] == "niuma-1"
    assert rendered["model"] == "deepseek-v4-pro"
    assert rendered["backend_type"] == "codex_cli"


def test_marvisctl_agent_list(tmp_path, capsys):
    config_path = _write_agent_config(tmp_path)

    assert marvisctl.main(["agent", "list", "--config", str(config_path)]) == 0

    assert "niuma-1" in capsys.readouterr().out


def test_marvisctl_doctor_reports_worker_health_summary(tmp_path, capsys, monkeypatch):
    config_path = tmp_path / "factory_config.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [
                    {
                        "worker_id": "niuma-1",
                        "display_name": "niuma-1",
                        "provider": "openai",
                        "model": "deepseek-v4-pro",
                        "api_key_env": "NIUMA_1_API_KEY",
                        "profile_dir": str(tmp_path / "missing-profile"),
                        "workspace_dir": str(tmp_path / "missing-workspace"),
                        "skills_dir": str(tmp_path / "missing-skills"),
                        "backend_type": "fake",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("NIUMA_1_API_KEY", raising=False)

    assert marvisctl.main(["doctor", "--config", str(config_path)]) == 0

    output = capsys.readouterr().out
    assert "python:" in output
    assert "workers: 0/1 ok" in output
    assert "missing_api_key=1" in output
    assert "path_warnings=1" in output


def test_marvisctl_status_reports_factory_status(tmp_path, capsys):
    config_path = tmp_path / "factory_config.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [
                    {
                        "worker_id": "niuma-1",
                        "display_name": "niuma-1",
                        "provider": "test",
                        "model": "fake-model",
                        "api_key_env": "NIUMA_1_API_KEY",
                        "profile_dir": "profiles/niuma-1",
                        "workspace_dir": "workspaces/niuma-1",
                        "skills_dir": "skills/niuma-1",
                        "backend_type": "fake",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_dir = tmp_path / "artifacts" / "compliance"
    report_dir.mkdir(parents=True)
    (report_dir / "compliance-quick-20260101T000000Z-passed.json").write_text("{}", encoding="utf-8")

    assert marvisctl.main(["status", "--config", str(config_path), "--workspace", str(tmp_path)]) == 0

    output = capsys.readouterr().out
    assert "Marvis AI Factory Console" in output
    assert "80%" in output
    assert "reports 1" in output
    assert "blueprint P0" in output


def test_marvisctl_status_can_print_json(tmp_path, capsys):
    config_path = tmp_path / "factory_config.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert marvisctl.main(["status", "--config", str(config_path), "--workspace", str(tmp_path), "--json"]) == 0

    body = json.loads(capsys.readouterr().out)
    assert body["product"]["name"] == "Marvis AI Factory Console"
    assert body["metrics"]["compliance_reports_total"] == 0
    assert body["milestone_summary"]["P0"]["ready"] >= 8


def test_marvisctl_lists_and_shows_compliance_reports(tmp_path, capsys):
    report_dir = tmp_path / "artifacts" / "compliance"
    report_dir.mkdir(parents=True)
    report = report_dir / "compliance-quick-20260101T000000Z-passed.json"
    report.write_text(json.dumps({"success": True, "cases": [{"name": "legacy-login"}]}), encoding="utf-8")

    assert marvisctl.main(["compliance", "reports", "--workspace", str(tmp_path)]) == 0
    assert report.name in capsys.readouterr().out

    assert marvisctl.main(["compliance", "show", report.name, "--workspace", str(tmp_path)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["success"] is True
    assert shown["cases"][0]["name"] == "legacy-login"


def test_marvisctl_preflight_reports_launch_gate(tmp_path, capsys, monkeypatch):
    workspace = tmp_path / "workspaces" / "niuma-1"
    profile = tmp_path / "profiles" / "niuma-1"
    skills = tmp_path / "skills" / "niuma-1"
    for path in (workspace, profile, skills):
        path.mkdir(parents=True)
    config_path = tmp_path / "factory_config.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [
                    {
                        "worker_id": "niuma-1",
                        "display_name": "niuma-1",
                        "provider": "test",
                        "model": "fake-model",
                        "api_key_env": "NIUMA_1_API_KEY",
                        "profile_dir": str(profile),
                        "workspace_dir": str(workspace),
                        "skills_dir": str(skills),
                        "backend_type": "fake",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    taskbook_path = tmp_path / "legacy.yml"
    taskbook_path.write_text(
        textwrap.dedent(
            """
            title: legacy login
            objective: reverse login
            steps:
              - id: reverse-login
                agent: niuma-1
                objective: reverse login
                outputs:
                  - path: artifacts/runs/{run_id}/reverse-login/function-list.md
            """
        ),
        encoding="utf-8",
    )
    source_path = tmp_path / "login.jsp"
    source_path.write_text("<form>login</form>", encoding="utf-8")
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")

    assert marvisctl.main(
        [
            "preflight",
            "--config",
            str(config_path),
            "--taskbook",
            str(taskbook_path),
            "--source",
            str(source_path),
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "preflight passed" in output
    assert "taskbook_agents" in output


def test_marvisctl_preflight_returns_nonzero_on_failed_gate(tmp_path, capsys):
    config_path = tmp_path / "factory_config.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert marvisctl.main(["preflight", "--config", str(config_path), "--taskbook", str(tmp_path / "missing.yml")]) == 1

    assert "preflight failed" in capsys.readouterr().out


def test_marvisctl_reads_factory_config_shape(tmp_path, capsys):
    config_path = tmp_path / "factory_config.example.json"
    config_path.write_text(
        json.dumps(
            {
                "runtime_mode": "claude-cli",
                "workers": [
                    {
                        "worker_id": "niuma-1",
                        "display_name": "牛马1",
                        "provider": "anthropic",
                        "model": "claude-sonnet-4-6",
                        "api_key_env": "NIUMA_1_API_KEY",
                        "backend_type": "claude_cli",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert marvisctl.main(["config", "render", "niuma-1", "--config", str(config_path)]) == 0

    rendered = json.loads(capsys.readouterr().out)
    assert rendered["worker_id"] == "niuma-1"
    assert rendered["display_name"] == "牛马1"
    assert rendered["backend_type"] == "claude_cli"


def test_marvisctl_defaults_to_factory_config_when_agents_json_is_absent(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "factory_config.example.json"
    config_path.write_text(
        json.dumps(
            {
                "workers": [
                    {
                        "worker_id": "niuma-1",
                        "display_name": "牛马1",
                        "provider": "anthropic",
                        "model": "claude-sonnet-4-6",
                        "api_key_env": "NIUMA_1_API_KEY",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert marvisctl.main(["agent", "list"]) == 0

    assert "niuma-1" in capsys.readouterr().out


def test_marvisctl_script_runs_without_pytest_alias():
    result = subprocess.run(
        [sys.executable, "marvisctl.py", "agent", "list", "--config", "factory_config.example.json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "niuma-1" in result.stdout


def test_marvisctl_taskbook_lint_reports_success(tmp_path, capsys):
    taskbook_path = tmp_path / "login.yml"
    taskbook_path.write_text(
        textwrap.dedent(
            """
            title: 登录模块改造
            objective: 输出登录模块逆向文档
            steps:
              - id: reverse-login
                agent: niuma-1
                objective: 逆向登录模块
                outputs:
                  - path: artifacts/runs/{run_id}/reverse-login/function-list.md
            """
        ),
        encoding="utf-8",
    )

    assert marvisctl.main(["taskbook", "lint", str(taskbook_path)]) == 0

    assert "taskbook ok" in capsys.readouterr().out


def test_marvisctl_taskbook_lint_returns_nonzero_for_invalid_taskbook(tmp_path, capsys):
    taskbook_path = tmp_path / "bad.yml"
    taskbook_path.write_text("title: bad\nobjective: bad\nsteps: []\n", encoding="utf-8")

    assert marvisctl.main(["taskbook", "lint", str(taskbook_path)]) == 1

    assert "taskbook must contain at least one step" in capsys.readouterr().err


def test_marvisctl_artifact_manifest_prints_run_manifest(tmp_path, capsys):
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="niuma-1")
    run_id = manager.create_pipeline_run("login modernization")
    manager.create_step_run(
        run_id,
        "reverse-login",
        "niuma-1",
        "reverse login",
        outputs=["artifacts/runs/{run_id}/reverse-login/function-list.md"],
    )
    manager.update_pipeline_status(run_id, "succeeded")
    manager.update_step_status(run_id, "reverse-login", "succeeded")
    output = tmp_path / "artifacts" / "runs" / run_id / "reverse-login" / "function-list.md"
    output.parent.mkdir(parents=True)
    output.write_text("function list", encoding="utf-8")

    assert marvisctl.main(["artifact", "manifest", run_id, "--workspace", str(tmp_path)]) == 0

    manifest = json.loads(capsys.readouterr().out)
    assert manifest["run"]["run_id"] == run_id
    assert manifest["artifacts"][0]["step_id"] == "reverse-login"


def test_marvisctl_artifact_list_searches_across_runs(tmp_path, capsys):
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="niuma-1")
    run_id = manager.create_pipeline_run("login modernization")
    manager.create_step_run(
        run_id,
        "reverse-login",
        "niuma-1",
        "reverse login",
        outputs=["artifacts/runs/{run_id}/reverse-login/function-list.md"],
    )
    manager.update_pipeline_status(run_id, "succeeded")
    manager.update_step_status(run_id, "reverse-login", "succeeded")
    output = tmp_path / "artifacts" / "runs" / run_id / "reverse-login" / "function-list.md"
    output.parent.mkdir(parents=True)
    output.write_text("function list", encoding="utf-8")

    assert marvisctl.main(["artifact", "list", "--workspace", str(tmp_path), "--query", "function"]) == 0

    text = capsys.readouterr().out
    assert run_id in text
    assert "reverse-login" in text
    assert "function-list.md" in text


def _write_agent_config(tmp_path):
    config_path = tmp_path / "agents.json"
    config_path.write_text(
        json.dumps(
            {
                "defaults": {
                    "backend_type": "codex_cli",
                    "base_url": "http://127.0.0.1:38440/v1",
                },
                "templates": {
                    "reverse-engineer": {
                        "provider": "openai",
                        "model": "deepseek-v4-pro",
                    }
                },
                "agents": {
                    "niuma-1": {
                        "extends": "reverse-engineer",
                        "display_name": "牛马1",
                        "api_key_env": "NIUMA_1_API_KEY",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return config_path
