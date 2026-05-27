import json
import textwrap

import marvisctl


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
