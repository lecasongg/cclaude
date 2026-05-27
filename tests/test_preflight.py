from agent_factory.core.models import WorkerConfig
from agent_factory.core.preflight import run_preflight


def test_preflight_checks_taskbook_source_workers_and_suite(tmp_path, monkeypatch):
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    workspace = tmp_path / "workspaces" / "niuma-1"
    profile = tmp_path / "profiles" / "niuma-1"
    skills = tmp_path / "skills" / "niuma-1"
    for path in (workspace, profile, skills):
        path.mkdir(parents=True)
    taskbook = tmp_path / "taskbooks" / "legacy.yml"
    taskbook.parent.mkdir()
    taskbook.write_text(
        """
title: legacy login
objective: reverse login
steps:
  - id: reverse-login
    agent: niuma-1
    objective: reverse login
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    source = tmp_path / "source" / "login.jsp"
    source.parent.mkdir()
    source.write_text("<form>login</form>", encoding="utf-8")
    suite = tmp_path / "suite"
    (suite / "taskbooks").mkdir(parents=True)
    (suite / "expected").mkdir()
    (suite / "taskbooks" / "legacy.yml").write_text(taskbook.read_text(encoding="utf-8"), encoding="utf-8")
    worker = WorkerConfig(
        worker_id="niuma-1",
        display_name="niuma-1",
        provider="test",
        model="fake-model",
        api_key_env="NIUMA_1_API_KEY",
        profile_dir=str(profile),
        workspace_dir=str(workspace),
        skills_dir=str(skills),
        backend_type="fake",
    )

    result = run_preflight([worker], str(taskbook), str(source), str(suite))

    assert result["status"] == "passed"
    assert {check["name"]: check["status"] for check in result["checks"]} == {
        "taskbook": "passed",
        "taskbook_agents": "passed",
        "source": "passed",
        "worker_health": "passed",
        "compliance_suite": "passed",
    }


def test_preflight_fails_unknown_taskbook_agent(tmp_path):
    taskbook = tmp_path / "legacy.yml"
    taskbook.write_text(
        """
title: legacy login
objective: reverse login
steps:
  - id: reverse-login
    agent: missing-agent
    objective: reverse login
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )

    result = run_preflight([], str(taskbook))

    assert result["status"] == "failed"
    assert any(check["name"] == "taskbook_agents" and check["status"] == "failed" for check in result["checks"])
