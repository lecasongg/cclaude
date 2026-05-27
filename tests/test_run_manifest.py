from agent_factory.core.event_log import EventLog
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.run_manifest import build_run_manifest


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
