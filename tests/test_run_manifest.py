from agent_factory.core.event_log import EventLog
from agent_factory.core.resource_manager import ResourceManager
import pytest

from agent_factory.core.run_manifest import build_run_manifest, diff_artifacts, list_artifacts_across_runs


def test_run_manifest_indexes_artifacts_by_declared_step(tmp_path):
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="niuma-1")
    run_id = manager.create_pipeline_run("login modernization", taskbook_path="taskbooks/login.yml")
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
    event_log = EventLog(tmp_path / "events")
    event_log.write_event(run_id, "artifact_written", step_id="reverse-login", payload={"path": output.as_posix()})

    manifest = build_run_manifest(manager, tmp_path, run_id, event_log)

    assert manifest["manifest_version"] == 1
    assert manifest["run"]["taskbook_path"] == "taskbooks/login.yml"
    assert manifest["artifacts"] == [
        {
            "path": f"artifacts/runs/{run_id}/reverse-login/function-list.md",
            "size": len("function list"),
            "exists": True,
            "step_id": "reverse-login",
        }
    ]
    assert manifest["quality"]["summary"]["status"] == "passed"
    assert manifest["events"][0]["type"] == "artifact_written"


def test_list_artifacts_across_runs_supports_query_and_limit(tmp_path):
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="niuma-1")
    first_run = _create_run_with_artifact(manager, tmp_path, "login modernization", "reverse-login", "function-list.md")
    _create_run_with_artifact(manager, tmp_path, "order modernization", "write-tests", "test-plan.md")

    artifacts = list_artifacts_across_runs(manager, tmp_path, query="function", limit=5)

    assert len(artifacts) == 1
    assert artifacts[0]["run_id"] == first_run
    assert artifacts[0]["run_title"] == "login modernization"
    assert artifacts[0]["step_id"] == "reverse-login"
    assert artifacts[0]["path"].endswith("function-list.md")

    assert len(list_artifacts_across_runs(manager, tmp_path, limit=1)) == 1


def test_diff_artifacts_returns_unified_diff_and_blocks_escape(tmp_path):
    left = tmp_path / "artifacts" / "runs" / "run-1" / "reverse" / "function-list.md"
    right = tmp_path / "artifacts" / "runs" / "run-2" / "reverse" / "function-list.md"
    left.parent.mkdir(parents=True)
    right.parent.mkdir(parents=True)
    left.write_text("login\nlogout\n", encoding="utf-8")
    right.write_text("login\nlogout\nreset-password\n", encoding="utf-8")

    result = diff_artifacts(
        tmp_path,
        "artifacts/runs/run-1/reverse/function-list.md",
        "artifacts/runs/run-2/reverse/function-list.md",
    )

    assert result["changed"] is True
    assert "+reset-password" in result["diff"]
    assert result["left_size"] == left.stat().st_size

    with pytest.raises(FileNotFoundError, match="artifact not found"):
        diff_artifacts(tmp_path, "../secret.txt", "artifacts/runs/run-2/reverse/function-list.md")


def _create_run_with_artifact(manager, tmp_path, title, step_id, filename):
    run_id = manager.create_pipeline_run(title)
    manager.create_step_run(
        run_id,
        step_id,
        "niuma-1",
        step_id,
        outputs=[f"artifacts/runs/{{run_id}}/{step_id}/{filename}"],
    )
    manager.update_pipeline_status(run_id, "succeeded")
    manager.update_step_status(run_id, step_id, "succeeded")
    output = tmp_path / "artifacts" / "runs" / run_id / step_id / filename
    output.parent.mkdir(parents=True)
    output.write_text(filename, encoding="utf-8")
    return run_id
