from agent_factory.core.marvis_status import (
    BLUEPRINT_MILESTONES,
    BLUEPRINT_TARGET_PERCENT,
    CAPABILITY_LEDGER,
    blueprint_progress_percent,
    build_marvis_status,
)
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
    assert status["product"]["progress_percent"] == blueprint_progress_percent()
    assert status["product"]["target_percent"] == BLUEPRINT_TARGET_PERCENT
    assert status["metrics"]["runs_total"] == 1
    assert status["metrics"]["runs_succeeded"] == 1
    assert status["metrics"]["runtime_config_persistence"] is True
    assert {capability["key"] for capability in status["capabilities"]} >= {
        "taskbook-pipeline",
        "file-handoff",
        "quality-gate",
        "compliance-suite",
        "factory-console-ui",
        "run-preflight",
    }
    assert all("weight" in capability and "earned" in capability for capability in status["capabilities"])
    assert {milestone["key"] for milestone in status["milestones"]} >= {
        "quick-compliance",
        "pipeline-god-view",
        "agent-isolation",
    }
    assert status["milestone_summary"]["P0"]["ready"] >= 8
    assert status["milestone_summary"]["P1"]["ready"] >= 1
    assert status["milestone_summary"]["P1"]["partial"] >= 3


def test_marvis_blueprint_progress_is_calculated_from_capability_ledger():
    total = sum(item["weight"] for item in CAPABILITY_LEDGER)
    earned = sum(item["earned"] for item in CAPABILITY_LEDGER)

    assert total == 100
    assert blueprint_progress_percent() == round((earned / total) * 100)


def test_marvis_blueprint_milestones_are_phase_grouped():
    assert {item["phase"] for item in BLUEPRINT_MILESTONES} >= {"P0", "P1", "P2"}
    assert all({"phase", "key", "title", "status", "evidence", "next_step"} <= set(item) for item in BLUEPRINT_MILESTONES)
