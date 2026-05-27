from agent_factory.core.marvis_status import build_marvis_status
from agent_factory.core.models import WorkerConfig
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.task_bus import TaskBus


def test_marvis_status_reports_blueprint_progress_and_capabilities(tmp_path):
    worker = WorkerConfig(
        worker_id="niuma-1",
        display_name="niuma-1",
        provider="test",
        model="fake-model",
        api_key_env="NIUMA_1_API_KEY",
        profile_dir="profiles/niuma-1",
        workspace_dir="workspaces/niuma-1",
        skills_dir="skills/niuma-1",
        backend_type="fake",
    )
    bus = TaskBus(["niuma-1"])
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="niuma-1")
    run_id = manager.create_pipeline_run("legacy login")
    manager.update_pipeline_status(run_id, "succeeded")

    status = build_marvis_status([worker], bus, manager, tmp_path / "runtime_config.json")

    assert status["product"]["name"] == "Marvis AI Factory Console"
    assert status["product"]["primary_scenario"] == "legacy-system modernization"
    assert status["product"]["progress_percent"] == 68
    assert status["product"]["target_percent"] == 80
    assert status["metrics"]["runs_total"] == 1
    assert status["metrics"]["runs_succeeded"] == 1
    assert status["metrics"]["runtime_config_persistence"] is True
    assert {capability["key"] for capability in status["capabilities"]} >= {
        "taskbook-pipeline",
        "file-handoff",
        "quality-gate",
        "compliance-suite",
        "factory-console-ui",
    }
