import json
from pathlib import Path

from fastapi.testclient import TestClient

from agent_factory.core.api import create_app
from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.models import WorkerConfig
from agent_factory.core.security import SecurityGate
from agent_factory.core.supervisor import HermesSupervisor
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.worker_runtime import FakeWorkerBackend, WorkerRuntime


def _worker_config(worker_id: str) -> WorkerConfig:
    return WorkerConfig(
        worker_id=worker_id,
        display_name=worker_id,
        provider="deepseek",
        model="deepseek-chat",
        api_key_env=f"{worker_id.upper().replace('-', '_')}_API_KEY",
        profile_dir=f"profiles/{worker_id}",
        workspace_dir=f"workspaces/{worker_id}",
        skills_dir=f"skills/{worker_id}",
    )


def _client(tmp_path: Path) -> TestClient:
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path)
    config = _worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, FakeWorkerBackend("ok"))})
    return TestClient(
        create_app(
            supervisor=supervisor,
            bus=bus,
            workers=[config],
            security=SecurityGate("local-token"),
            pipeline_workspace_root=tmp_path,
        )
    )


def test_api_manages_compliance_baselines(tmp_path):
    client = _client(tmp_path)
    report_dir = tmp_path / "artifacts" / "compliance"
    report_dir.mkdir(parents=True)
    baseline_report = report_dir / "compliance-model-20260101T000000Z-passed.json"
    current_report = report_dir / "compliance-model-20260102T000000Z-failed.json"
    baseline_report.write_text(
        json.dumps(
            {
                "mode": "model",
                "success": True,
                "cases": [{"name": "legacy-login", "status": "passed"}],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    current_report.write_text(
        json.dumps(
            {
                "mode": "model",
                "success": False,
                "cases": [{"name": "legacy-login", "status": "failed"}],
                "errors": ["legacy-login failed"],
            }
        ),
        encoding="utf-8",
    )

    created = client.post(
        "/api/compliance/baselines",
        headers={"x-hermes-token": "local-token"},
        json={"name": "moon-bridge-deepseek", "report_filename": baseline_report.name},
    )
    listed = client.get("/api/compliance/baselines", headers={"x-hermes-token": "local-token"})
    compared = client.post(
        f"/api/compliance/baselines/moon-bridge-deepseek/compare/{current_report.name}",
        headers={"x-hermes-token": "local-token"},
    )

    assert created.status_code == 200
    assert created.json()["baseline"]["name"] == "moon-bridge-deepseek"
    assert listed.status_code == 200
    assert listed.json()["baselines"][0]["name"] == "moon-bridge-deepseek"
    assert compared.status_code == 200
    assert compared.json()["passed"] is False
    assert compared.json()["regressions"] == [{"name": "legacy-login", "baseline": "passed", "current": "failed"}]
