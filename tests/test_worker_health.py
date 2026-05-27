import os

from agent_factory.core.models import WorkerConfig
from agent_factory.core.worker_health import check_worker_health, summarize_worker_health


def make_config(**overrides):
    data = {
        "worker_id": "niuma-1",
        "display_name": "牛马1",
        "provider": "openai",
        "model": "deepseek-v4-pro",
        "api_key_env": "NIUMA_1_API_KEY",
        "base_url": "http://127.0.0.1:38440/v1",
        "profile_dir": "profiles/niuma-1",
        "workspace_dir": "workspaces/niuma-1",
        "skills_dir": "skills/niuma-1",
        "backend_type": "codex_cli",
    }
    data.update(overrides)
    return WorkerConfig(**data)


def test_worker_health_reports_missing_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("NIUMA_1_API_KEY", raising=False)
    config = make_config(workspace_dir=str(tmp_path / "workspace"), profile_dir=str(tmp_path / "profile"), skills_dir=str(tmp_path / "skills"))

    health = check_worker_health(config)

    assert health["status"] == "warning"
    assert any(check["name"] == "api_key" and check["status"] == "failed" for check in health["checks"])


def test_worker_health_reports_paths_and_key_ok(monkeypatch, tmp_path):
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    workspace = tmp_path / "workspace"
    profile = tmp_path / "profile"
    skills = tmp_path / "skills"
    for path in (workspace, profile, skills):
        path.mkdir()
    config = make_config(workspace_dir=str(workspace), profile_dir=str(profile), skills_dir=str(skills), backend_type="fake", base_url="")

    health = check_worker_health(config)

    assert health["status"] == "ok"
    assert {check["name"]: check["status"] for check in health["checks"]}["workspace_dir"] == "passed"
    assert {check["name"]: check["status"] for check in health["checks"]}["api_key"] == "passed"


def test_worker_health_marks_missing_base_url_for_cli_backends(monkeypatch, tmp_path):
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    config = make_config(base_url="", workspace_dir=str(tmp_path / "workspace"), profile_dir=str(tmp_path / "profile"), skills_dir=str(tmp_path / "skills"))

    health = check_worker_health(config)

    assert health["status"] == "warning"
    assert any(check["name"] == "base_url" and check["status"] == "failed" for check in health["checks"])


def test_worker_health_summary_counts_fleet_risks(monkeypatch, tmp_path):
    monkeypatch.delenv("NIUMA_1_API_KEY", raising=False)
    monkeypatch.setenv("NIUMA_2_API_KEY", "sk-test")
    healthy_workspace = tmp_path / "workspace"
    healthy_profile = tmp_path / "profile"
    healthy_skills = tmp_path / "skills"
    for path in (healthy_workspace, healthy_profile, healthy_skills):
        path.mkdir()

    summary = summarize_worker_health(
        [
            make_config(
                workspace_dir=str(tmp_path / "missing-workspace"),
                profile_dir=str(tmp_path / "missing-profile"),
                skills_dir=str(tmp_path / "missing-skills"),
            ),
            make_config(
                worker_id="niuma-2",
                api_key_env="NIUMA_2_API_KEY",
                backend_type="fake",
                base_url="",
                workspace_dir=str(healthy_workspace),
                profile_dir=str(healthy_profile),
                skills_dir=str(healthy_skills),
            ),
        ]
    )

    assert summary["summary"]["total"] == 2
    assert summary["summary"]["ok"] == 1
    assert summary["summary"]["warning"] == 1
    assert summary["summary"]["missing_api_key"] == 1
    assert summary["summary"]["path_warnings"] == 1
