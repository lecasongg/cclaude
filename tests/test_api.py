import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from agent_factory.core.marvis_status import blueprint_progress_percent
from agent_factory.core.api import create_app
from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.event_log import EventLog
from agent_factory.core.models import WorkerConfig
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.security import SecurityGate
from agent_factory.core.supervisor import HermesSupervisor
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.worker_runtime import FakeWorkerBackend, OpenAICompatibleWorkerBackend, WorkerRuntime


def worker_config(worker_id):
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


def build_client(tmp_path):
    bus = TaskBus(["niuma-1", "niuma-2"])
    artifacts = ArtifactStore(tmp_path)
    runtimes = {
        "niuma-1": WorkerRuntime(worker_config("niuma-1"), bus, artifacts, FakeWorkerBackend("清单")),
        "niuma-2": WorkerRuntime(worker_config("niuma-2"), bus, artifacts, FakeWorkerBackend("文档")),
    }
    supervisor = HermesSupervisor(bus, artifacts, runtimes)
    app = create_app(
        supervisor=supervisor,
        bus=bus,
        workers=[worker_config("niuma-1"), worker_config("niuma-2")],
        security=SecurityGate("local-token"),
        runtime_config_path=tmp_path / "runtime_config.json",
        runtime_config={},
    )
    return TestClient(app)


def test_api_rejects_missing_token(tmp_path):
    client = build_client(tmp_path)

    response = client.post("/api/delegate", json={"worker_id": "niuma-1", "prompt": "分析"})

    assert response.status_code == 401


def test_api_rejects_health_without_token(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 401


def test_api_reports_health_with_token(tmp_path, monkeypatch):
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-worker-1")
    monkeypatch.delenv("NIUMA_2_API_KEY", raising=False)
    client = build_client(tmp_path)

    response = client.get("/api/health", headers={"x-hermes-token": "local-token"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "workers_total": 2,
        "workers_with_api_key": 1,
        "tasks_total": 0,
        "runtime_config_persistence": True,
    }


def test_api_reports_marvis_factory_status(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/api/marvis/status", headers={"x-hermes-token": "local-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["product"]["name"] == "Marvis AI Factory Console"
    assert body["product"]["primary_scenario"] == "legacy-system modernization"
    assert body["product"]["progress_percent"] == blueprint_progress_percent()
    assert body["metrics"]["workers_total"] == 2
    assert {capability["key"] for capability in body["capabilities"]} >= {"taskbook-pipeline", "factory-console-ui"}
    assert body["milestone_summary"]["P0"]["ready"] >= 8
    assert {milestone["key"] for milestone in body["milestones"]} >= {"quick-compliance", "pipeline-god-view"}


def test_api_runs_preflight(tmp_path):
    client = build_client(tmp_path)
    taskbook_path = tmp_path / "login.yml"
    taskbook_path.write_text(
        """
title: login
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

    response = client.post(
        "/api/preflight",
        headers={"x-hermes-token": "local-token"},
        json={"taskbook_path": str(taskbook_path), "source_path": str(tmp_path / "missing.jsp")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert {check["name"] for check in response.json()["checks"]} >= {"taskbook", "taskbook_agents", "source", "worker_health"}


def test_api_builds_file_context_from_local_path(tmp_path):
    source = tmp_path / "user-list.jsp"
    source.write_text("<table>用户名称</table>", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/api/file-context/path",
        headers={"x-hermes-token": "local-token"},
        json={"path": str(source)},
    )

    assert response.status_code == 200
    assert response.json()["files"] == [{"path": str(source), "size": source.stat().st_size}]
    assert "文件：" in response.json()["prompt"]
    assert "user-list.jsp" in response.json()["prompt"]
    assert "用户名称" in response.json()["prompt"]


def test_api_normalizes_quoted_file_context_path(tmp_path):
    source = tmp_path / "user-list.jsp"
    source.write_text("<table>用户名称</table>", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/api/file-context/path",
        headers={"x-hermes-token": "local-token"},
        json={"path": f'  "{source}"  '},
    )

    assert response.status_code == 200
    assert response.json()["files"][0]["path"] == str(source)


def test_api_builds_file_context_from_upload(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/api/file-context/upload",
        headers={"x-hermes-token": "local-token"},
        files={"files": ("user-list.jsp", "<table>用户名称</table>", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["files"] == [{"path": "user-list.jsp", "size": len("<table>用户名称</table>".encode("utf-8"))}]
    assert "已读取附件内容，不要再尝试访问本地路径" in response.json()["prompt"]
    assert "下面就是文件正文" in response.json()["prompt"]
    assert "文件：user-list.jsp" in response.json()["prompt"]
    assert "用户名称" in response.json()["prompt"]


def test_console_does_not_force_json_header_for_file_upload():
    console = Path(__file__).parents[1] / "web" / "console.html"
    html = console.read_text(encoding="utf-8")

    assert "options.body instanceof FormData" in html
    assert "'content-type': 'application/json', 'x-hermes-token': this.token" not in html


def test_api_installs_worker_task_manual_from_upload(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/api/workers/niuma-1/installed-documents/task_manual",
        headers={"x-hermes-token": "local-token"},
        files={"file": ("manual.md", "任务手册正文", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["installed_documents"]["task_manual"] == {
        "installed": True,
        "filename": "manual.md",
        "size": len("任务手册正文".encode("utf-8")),
    }
    assert "任务手册正文" not in response.text
    saved = json.loads((tmp_path / "runtime_config.json").read_text(encoding="utf-8"))
    assert saved["workers"]["niuma-1"]["installed_documents"]["task_manual"]["content"] == "任务手册正文"


def test_api_installs_worker_conversion_rules_from_upload(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/api/workers/niuma-1/installed-documents/conversion_rules",
        headers={"x-hermes-token": "local-token"},
        files={"file": ("rules.md", "转换规则正文", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["installed_documents"]["conversion_rules"] == {
        "installed": True,
        "filename": "rules.md",
        "size": len("转换规则正文".encode("utf-8")),
    }
    assert "转换规则正文" not in response.text
    saved = json.loads((tmp_path / "runtime_config.json").read_text(encoding="utf-8"))
    assert saved["workers"]["niuma-1"]["installed_documents"]["conversion_rules"]["content"] == "转换规则正文"


def test_api_rejects_niuma_1_delegate_until_manual_and_rules_installed(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/api/delegate",
        headers={"x-hermes-token": "local-token"},
        json={"worker_id": "niuma-1", "prompt": "分析"},
    )

    assert response.status_code == 400
    assert "任务手册" in response.json()["detail"]
    assert "转换规则" in response.json()["detail"]


def install_niuma_1_documents(client):
    for kind, filename, content in [
        ("task_manual", "manual.md", "任务手册正文"),
        ("conversion_rules", "rules.md", "转换规则正文"),
    ]:
        response = client.post(
            f"/api/workers/niuma-1/installed-documents/{kind}",
            headers={"x-hermes-token": "local-token"},
            files={"file": (filename, content, "text/markdown")},
        )
        assert response.status_code == 200


def test_api_prepends_manual_then_rules_before_niuma_1_delegate(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path)
    config = worker_config("niuma-1")
    backend = FakeWorkerBackend("清单")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, backend)})
    app = create_app(supervisor, bus, [config], SecurityGate("local-token"), runtime_config_path=tmp_path / "runtime_config.json", runtime_config={})
    client = TestClient(app)
    install_niuma_1_documents(client)

    response = client.post(
        "/api/delegate",
        headers={"x-hermes-token": "local-token"},
        json={"worker_id": "niuma-1", "prompt": "用户任务正文"},
    )

    assert response.status_code == 200
    prompt = backend.calls[0][0]
    assert prompt.index("任务手册正文") < prompt.index("转换规则正文") < prompt.index("用户任务正文")


def test_api_prepends_manual_then_rules_before_chain_source(tmp_path):
    bus = TaskBus(["niuma-1", "niuma-2"])
    artifacts = ArtifactStore(tmp_path)
    backend_1 = FakeWorkerBackend("清单")
    backend_2 = FakeWorkerBackend("文档")
    config_1 = worker_config("niuma-1")
    config_2 = worker_config("niuma-2")
    supervisor = HermesSupervisor(
        bus,
        artifacts,
        {
            "niuma-1": WorkerRuntime(config_1, bus, artifacts, backend_1),
            "niuma-2": WorkerRuntime(config_2, bus, artifacts, backend_2),
        },
    )
    app = create_app(supervisor, bus, [config_1, config_2], SecurityGate("local-token"), runtime_config_path=tmp_path / "runtime_config.json", runtime_config={})
    client = TestClient(app)
    install_niuma_1_documents(client)

    response = client.post(
        "/api/chain",
        headers={"x-hermes-token": "local-token"},
        json={"source_worker": "niuma-1", "target_worker": "niuma-2", "prompt": "用户任务正文", "next_instruction": "写需求文档"},
    )

    assert response.status_code == 200
    prompt = backend_1.calls[0][0]
    assert prompt.index("任务手册正文") < prompt.index("转换规则正文") < prompt.index("用户任务正文")


def test_api_chain_does_not_leak_niuma_1_documents_into_niuma_2_prompt(tmp_path):
    bus = TaskBus(["niuma-1", "niuma-2"])
    artifacts = ArtifactStore(tmp_path)
    backend_1 = FakeWorkerBackend("# 需求清单")
    backend_2 = FakeWorkerBackend("# 需求文档")
    config_1 = worker_config("niuma-1")
    config_2 = worker_config("niuma-2")
    supervisor = HermesSupervisor(
        bus,
        artifacts,
        {
            "niuma-1": WorkerRuntime(config_1, bus, artifacts, backend_1),
            "niuma-2": WorkerRuntime(config_2, bus, artifacts, backend_2),
        },
    )
    app = create_app(supervisor, bus, [config_1, config_2], SecurityGate("local-token"), runtime_config_path=tmp_path / "runtime_config.json", runtime_config={})
    client = TestClient(app)
    install_niuma_1_documents(client)

    response = client.post(
        "/api/chain",
        headers={"x-hermes-token": "local-token"},
        json={"source_worker": "niuma-1", "target_worker": "niuma-2", "prompt": "逆向分析 JSP", "next_instruction": "写需求文档"},
    )

    assert response.status_code == 200
    target_prompt = backend_2.calls[0][0]
    assert "任务手册正文" not in target_prompt
    assert "转换规则正文" not in target_prompt
    assert "上游任务: 逆向分析 JSP" in target_prompt
    assert "上游产物文件路径" in target_prompt
    assert "result.md" in target_prompt
    assert "# 需求清单" not in target_prompt


def test_api_does_not_require_manual_rules_for_niuma_2_direct_delegate(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/api/delegate",
        headers={"x-hermes-token": "local-token"},
        json={"worker_id": "niuma-2", "prompt": "写文档"},
    )

    assert response.status_code == 200
    assert response.json()["worker_id"] == "niuma-2"


def test_console_uses_kind_specific_file_inputs_for_document_install():
    console = Path(__file__).parents[1] / "web" / "console.html"
    html = console.read_text(encoding="utf-8")

    assert "__marvisInstallDocument && window.__marvisInstallDocument(event, 'conversion_rules')" in html
    assert "__marvisInstallDocument && window.__marvisInstallDocument(event, 'task_manual')" in html
    assert "@change=\"installDocument\"" not in html


def test_console_displays_worker_backend_type():
    console = Path(__file__).parents[1] / "web" / "console.html"
    html = console.read_text(encoding="utf-8")

    assert "worker.backend_type" in html
    assert "后端" in html


def test_console_worker_config_modal_shows_backend_type_read_only():
    console = Path(__file__).parents[1] / "web" / "console.html"
    html = console.read_text(encoding="utf-8")

    assert "configForm.backend_type" in html
    assert "后端类型" in html


def test_console_fetches_pipeline_runs_and_events():
    console = Path(__file__).parents[1] / "web" / "console.html"
    html = console.read_text(encoding="utf-8")

    assert "Marvis AI 工厂控制台" in html
    assert "工厂屋顶掀开后的上帝视角总控图" in html
    assert "2.5D 工厂沙盘" in html
    assert 'class="viewport"' in html
    assert 'class="room core"' in html
    assert 'class="pipe"' in html
    assert "工位 / 车间区" in html
    assert "多流水线总览" in html
    assert "控制中心 / 主智能体办公室" in html
    assert "产物仓库" in html
    assert "步骤时间线 / 运行日志" in html
    assert "任务书工作间" in html
    assert "taskbookPath" in html
    assert "sourcePath" in html
    assert "window.location.protocol === 'file:'" in html
    assert "http://127.0.0.1:8846" in html
    assert "normalizedBaseUrl" in html
    assert "lintTaskbook" in html
    assert "startTaskbookRun" in html
    assert "runPreflight" in html
    assert "openPreflightResult" in html
    assert "/api/preflight" in html
    assert "runCompliance" in html
    assert "selectedRunEvents" in html
    assert "selectedRunArtifactContent" in html
    assert "factoryArtifacts" in html
    assert "artifactQuery" in html
    assert "refreshFactoryArtifacts" in html
    assert "loadFactoryArtifact" in html
    assert "factoryArtifactLabel" in html
    assert "/api/artifacts?limit=24" in html
    assert "selectedRunQuality" in html
    assert "质量闸口" in html
    assert "qualityScoreLabel" in html
    assert "openQualityStep" in html
    assert "artifactLabel" in html
    assert "notifyError" in html
    assert "配置中心" in html
    assert "refreshWorkerHealthSummary" in html
    assert "/api/workers/health-summary" in html
    assert "marvisStatus" in html
    assert "marvisProgressLabel" in html
    assert "milestoneSummaryLabel" in html
    assert "蓝图里程碑" in html
    assert "验收地图" in html
    assert "openMarvisStatus" in html
    assert "/api/marvis/status" in html
    assert "complianceReports" in html
    assert "refreshComplianceReports" in html
    assert "openComplianceReport" in html
    assert "/api/compliance/reports" in html
    assert "工厂状态同步完成" in html
    assert "验厂通过" in html
    assert "refreshTaskbooks" in html
    assert "selectedTaskbookFilename" in html
    assert "selectedTaskbookPath" in html
    assert "selectedStep" in html
    assert "correctionText" in html
    assert "rerunSelectedStep" in html
    assert "selectedRun.taskbook_path" in html
    assert "selectedRun.source_path" in html
    assert "/api/runs/${this.selectedRun.run_id}/steps/${this.selectedStep.step_id}/rerun" in html
    assert "drawerHtml" in html
    assert "/api/taskbooks/${filename}" in html
    assert "/api/compliance/run" in html
    assert "/api/runs" in html
    assert "/api/runs/${runId}/events" in html
    assert "/api/runs/${runId}/artifacts" in html
    assert "/api/runs/${runId}/quality" in html
    assert "openRunManifest" in html
    assert "/api/runs/${this.selectedRun.run_id}/manifest" in html

def test_console_has_taskbook_studio_editor():
    console = Path(__file__).parents[1] / "web" / "console.html"
    html = console.read_text(encoding="utf-8")

    assert "任务书调度架" in html
    assert "new-taskbook.yml" in html
    assert "selectedTaskbookFilename" in html
    assert "taskbookEditorContent" in html
    assert "refreshTaskbooks" in html
    assert "legacyModernizationDraft" in html
    assert "老系统流程" in html
    assert "reverse-module" in html
    assert "write-test-plan" in html
    assert "loadTaskbook" in html
    assert "saveTaskbook" in html
    assert "openTaskbookComposer" in html
    assert "composeTaskbookFromWorkers" in html
    assert "selectedComposerAgents" in html
    assert "智能体组合器" in html
    assert "/api/taskbooks/${filename}" in html
    assert "/api/taskbooks" in html

def test_console_has_agent_creation_and_configuration_flow():
    console = Path(__file__).parents[1] / "web" / "console.html"
    html = console.read_text(encoding="utf-8")

    assert "新建智能体工位" in html
    assert "workerCreateForm" in html
    assert "openWorkerCreateForm" in html
    assert "createWorker" in html
    assert "创建智能体" in html
    assert "克隆模板" in html
    assert "批量数量" in html
    assert "create-tags" in html
    assert "create-capabilities" in html
    assert "workerTemplate" in html
    assert "workerConfigForm" in html
    assert "保存配置" in html
    assert "加入任务书" in html
    assert "/api/workers" in html
    assert "/api/workers/${body.worker.worker_id}/config" in html

def test_console_has_pipeline_filter_density_and_compliance_baselines():
    console = Path(__file__).parents[1] / "web" / "console.html"
    html = console.read_text(encoding="utf-8")

    assert "runFilter" in html
    assert "runStatusFocus" in html
    assert "lineDensity" in html
    assert "visibleRuns" in html
    assert "保存基线" in html
    assert "对比最新报告" in html
    assert "refreshComplianceBaselines" in html
    assert "saveComplianceBaseline" in html
    assert "compareComplianceBaseline" in html
    assert "/api/compliance/baselines" in html
    assert "/api/compliance/baselines/${encodeURIComponent(name)}/compare/${encodeURIComponent(filename)}" in html

def test_api_lists_workers_with_token(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/api/workers", headers={"x-hermes-token": "local-token"})

    assert response.status_code == 200
    assert response.json()["workers"] == [
        {
            "worker_id": "niuma-1",
            "display_name": "niuma-1",
            "status": "idle",
            "queue_depth": 0,
            "current_task_id": "",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "backend_type": "fake",
            "api_key_env": "NIUMA_1_API_KEY",
            "api_key_configured": False,
            "base_url": "",
            "role": "通用交付工位",
            "group": "",
            "tags": [],
            "capabilities": [],
            "workspace_dir": "workspaces/niuma-1",
            "skills_dir": "skills/niuma-1",
            "installed_documents": {
                "task_manual": {"installed": False, "filename": "", "size": 0},
                "conversion_rules": {"installed": False, "filename": "", "size": 0},
            },
        },
        {
            "worker_id": "niuma-2",
            "display_name": "niuma-2",
            "status": "idle",
            "queue_depth": 0,
            "current_task_id": "",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "backend_type": "fake",
            "api_key_env": "NIUMA_2_API_KEY",
            "api_key_configured": False,
            "base_url": "",
            "role": "通用交付工位",
            "group": "",
            "tags": [],
            "capabilities": [],
            "workspace_dir": "workspaces/niuma-2",
            "skills_dir": "skills/niuma-2",
            "installed_documents": {
                "task_manual": {"installed": False, "filename": "", "size": 0},
                "conversion_rules": {"installed": False, "filename": "", "size": 0},
            },
        },
    ]


def test_api_exposes_worker_health(tmp_path, monkeypatch):
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    client = build_client(tmp_path)

    response = client.get("/api/workers/niuma-1/health", headers={"x-hermes-token": "local-token"})

    assert response.status_code == 200
    assert response.json()["worker_id"] == "niuma-1"
    assert "checks" in response.json()


def test_api_exposes_worker_health_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    monkeypatch.delenv("NIUMA_2_API_KEY", raising=False)
    client = build_client(tmp_path)

    response = client.get("/api/workers/health-summary", headers={"x-hermes-token": "local-token"})

    assert response.status_code == 200
    assert response.json()["summary"]["total"] == 2
    assert response.json()["summary"]["missing_api_key"] == 1
    assert {worker["worker_id"] for worker in response.json()["workers"]} == {"niuma-1", "niuma-2"}


def test_api_creates_worker_and_runs_taskbook_with_new_agent(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path / "worker-artifacts")
    existing = worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(existing, bus, artifacts, FakeWorkerBackend("existing"))})
    resource_manager = ResourceManager(tmp_path / "marvis.db")
    runtime_config_path = tmp_path / "runtime_config.json"
    app = create_app(
        supervisor,
        bus,
        [existing],
        SecurityGate("local-token"),
        runtime_config_path=runtime_config_path,
        runtime_config={"workers": {}},
        resource_manager=resource_manager,
        event_log=EventLog(tmp_path / "events"),
        pipeline_workspace_root=tmp_path,
    )
    client = TestClient(app)

    created = client.post(
        "/api/workers",
        headers={"x-hermes-token": "local-token"},
        json={
            "worker_id": "niuma-3",
            "display_name": "牛马3",
            "role": "测试用例工位",
            "group": "qa",
            "tags": ["pytest", "docs"],
            "capabilities": ["test-plan"],
        },
    )

    assert created.status_code == 200
    assert created.json()["worker"]["worker_id"] == "niuma-3"
    assert created.json()["worker"]["group"] == "qa"
    assert created.json()["worker"]["tags"] == ["pytest", "docs"]
    assert created.json()["worker"]["capabilities"] == ["test-plan"]
    assert resource_manager.get_agent("niuma-3")["display_name"] == "牛马3"
    assert resource_manager.get_agent("niuma-3")["group_name"] == "qa"
    assert "niuma-3" in json.loads(runtime_config_path.read_text(encoding="utf-8"))["workers"]

    taskbook_path = tmp_path / "new-agent.yml"
    taskbook_path.write_text(
        """
title: new agent flow
objective: verify newly created agent can run
steps:
  - id: write-tests
    agent: niuma-3
    objective: write tests
    outputs:
      - path: artifacts/runs/{run_id}/write-tests/test-plan.md
""",
        encoding="utf-8",
    )
    run = client.post(
        "/api/runs",
        headers={"x-hermes-token": "local-token"},
        json={"taskbook_path": str(taskbook_path)},
    )

    assert run.status_code == 200
    assert run.json()["steps"][0]["agent_id"] == "niuma-3"
    assert run.json()["run"]["status"] == "succeeded"


def test_api_rejects_duplicate_or_invalid_worker_create(tmp_path):
    client = build_client(tmp_path)

    duplicate = client.post(
        "/api/workers",
        headers={"x-hermes-token": "local-token"},
        json={"worker_id": "niuma-1"},
    )
    invalid = client.post(
        "/api/workers",
        headers={"x-hermes-token": "local-token"},
        json={"worker_id": "bad/worker"},
    )

    assert duplicate.status_code == 400
    assert invalid.status_code == 400


def test_api_updates_worker_runtime_config_without_exposing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("NIUMA_1_API_KEY", raising=False)
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path)
    config = worker_config("niuma-1")
    backend = OpenAICompatibleWorkerBackend()
    runtimes = {"niuma-1": WorkerRuntime(config, bus, artifacts, backend)}
    supervisor = HermesSupervisor(bus, artifacts, runtimes)
    app = create_app(
        supervisor,
        bus,
        [config],
        SecurityGate("local-token"),
        runtime_config_path=tmp_path / "runtime_config.json",
        runtime_config={},
    )
    client = TestClient(app)

    response = client.patch(
        "/api/workers/niuma-1/config",
        headers={"x-hermes-token": "local-token"},
        json={
            "provider": "smarthse",
            "model": "deepseek-v4-pro",
            "role": "JSP 逆向工位",
            "group": "legacy-modernization",
            "tags": ["jsp", "sql"],
            "capabilities": ["reverse"],
            "base_url": "http://smarthse.51vip.biz:53001/v1",
            "api_key": "sk-secret",
        },
    )

    assert response.status_code == 200
    assert response.json()["worker"]["provider"] == "smarthse"
    assert response.json()["worker"]["model"] == "deepseek-v4-pro"
    assert response.json()["worker"]["role"] == "JSP 逆向工位"
    assert response.json()["worker"]["group"] == "legacy-modernization"
    assert response.json()["worker"]["tags"] == ["jsp", "sql"]
    assert response.json()["worker"]["capabilities"] == ["reverse"]
    assert response.json()["worker"]["api_key_configured"] is True
    assert response.json()["worker"]["base_url"] == "http://smarthse.51vip.biz:53001/v1"
    assert "sk-secret" not in response.text
    assert os.environ["NIUMA_1_API_KEY"] == "sk-secret"
    assert backend.api_url == "https://api.deepseek.com/chat/completions"
    saved = json.loads((tmp_path / "runtime_config.json").read_text(encoding="utf-8"))
    assert "model_base_url" not in saved
    assert saved["workers"]["niuma-1"] == {
        "provider": "smarthse",
        "model": "deepseek-v4-pro",
        "role": "JSP 逆向工位",
        "group": "legacy-modernization",
        "tags": ["jsp", "sql"],
        "capabilities": ["reverse"],
        "base_url": "http://smarthse.51vip.biz:53001/v1",
        "api_key": "sk-secret",
    }

    response = client.patch(
        "/api/workers/niuma-1/config",
        headers={"x-hermes-token": "local-token"},
        json={"model": "claude-opus-4-7", "api_key": ""},
    )

    assert response.status_code == 200
    saved = json.loads((tmp_path / "runtime_config.json").read_text(encoding="utf-8"))
    assert saved["workers"]["niuma-1"]["model"] == "claude-opus-4-7"
    assert saved["workers"]["niuma-1"]["api_key"] == "sk-secret"


    client = build_client(tmp_path)
    install_niuma_1_documents(client)

    response = client.post(
        "/api/delegate",
        headers={"x-hermes-token": "local-token"},
        json={"worker_id": "niuma-1", "prompt": "分析"},
    )

    assert response.status_code == 200
    assert response.json()["worker_id"] == "niuma-1"
    assert response.json()["status"] == "succeeded"
    assert response.json()["result_text"] == "清单"


def test_api_lists_task_history_and_reads_artifact(tmp_path):
    client = build_client(tmp_path)
    install_niuma_1_documents(client)
    created = client.post(
        "/api/delegate",
        headers={"x-hermes-token": "local-token"},
        json={"worker_id": "niuma-1", "prompt": "分析"},
    ).json()

    history = client.get("/api/tasks", headers={"x-hermes-token": "local-token"})

    assert history.status_code == 200
    assert history.json()["tasks"][0]["task_id"] == created["task_id"]
    assert history.json()["tasks"][0]["result_text"] == "清单"

    artifact = client.get(
        f"/api/artifacts/{created['artifact_ids'][0]}",
        headers={"x-hermes-token": "local-token"},
    )

    assert artifact.status_code == 200
    assert artifact.json() == {"artifact_id": created["artifact_ids"][0], "content": "清单"}


    client = build_client(tmp_path)
    install_niuma_1_documents(client)

    response = client.post(
        "/api/chain",
        headers={"x-hermes-token": "local-token"},
        json={
            "source_worker": "niuma-1",
            "target_worker": "niuma-2",
            "prompt": "逆向分析",
            "next_instruction": "写需求文档",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"]["status"] == "succeeded"
    assert body["target"]["status"] == "succeeded"
    assert body["target"]["parent_task_id"] == body["source"]["task_id"]


def test_api_exposes_pipeline_runs_steps_and_events(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path)
    config = worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, FakeWorkerBackend("清单"))})
    resource_manager = ResourceManager(tmp_path / "marvis.db")
    resource_manager.register_agent("niuma-1", display_name="牛马1")
    run_id = resource_manager.create_pipeline_run("登录模块改造")
    resource_manager.create_step_run(run_id, "reverse-login", "niuma-1", "逆向登录模块")
    resource_manager.update_pipeline_status(run_id, "running")
    resource_manager.update_step_status(run_id, "reverse-login", "running")
    event_log = EventLog(tmp_path / "events")
    event_log.write_event(run_id, "step_started", agent_id="niuma-1", step_id="reverse-login")
    app = create_app(
        supervisor,
        bus,
        [config],
        SecurityGate("local-token"),
        resource_manager=resource_manager,
        event_log=event_log,
    )
    client = TestClient(app)

    runs = client.get("/api/runs", headers={"x-hermes-token": "local-token"})
    run = client.get(f"/api/runs/{run_id}", headers={"x-hermes-token": "local-token"})
    events = client.get(f"/api/runs/{run_id}/events", headers={"x-hermes-token": "local-token"})

    assert runs.status_code == 200
    assert runs.json()["runs"][0]["run_id"] == run_id
    assert run.status_code == 200
    assert run.json()["run"]["title"] == "登录模块改造"
    assert run.json()["steps"][0]["step_id"] == "reverse-login"
    assert events.status_code == 200
    assert events.json()["events"][0]["type"] == "step_started"


def test_api_starts_taskbook_pipeline_run(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path / "worker-artifacts")
    config = worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, FakeWorkerBackend("功能清单"))})
    resource_manager = ResourceManager(tmp_path / "marvis.db")
    event_log = EventLog(tmp_path / "events")
    taskbook_path = tmp_path / "login.yml"
    taskbook_path.write_text(
        """
title: 登录模块改造
objective: 输出登录模块逆向文档
steps:
  - id: reverse-login
    agent: niuma-1
    objective: 逆向登录模块
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    app = create_app(
        supervisor,
        bus,
        [config],
        SecurityGate("local-token"),
        resource_manager=resource_manager,
        event_log=event_log,
        pipeline_workspace_root=tmp_path,
    )
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        headers={"x-hermes-token": "local-token"},
        json={"taskbook_path": str(taskbook_path)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["status"] == "succeeded"
    assert body["run"]["taskbook_path"] == str(taskbook_path)
    assert body["steps"][0]["status"] == "succeeded"
    output_path = tmp_path / "artifacts" / "runs" / body["run"]["run_id"] / "reverse-login" / "function-list.md"
    assert output_path.read_text(encoding="utf-8") == "功能清单"

    artifacts_response = client.get(
        f"/api/runs/{body['run']['run_id']}/artifacts",
        headers={"x-hermes-token": "local-token"},
    )
    artifact_id = f"artifacts/runs/{body['run']['run_id']}/reverse-login/function-list.md"
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()["artifacts"][0]["path"] == artifact_id
    assert artifacts_response.json()["artifacts"][0]["step_id"] == "reverse-login"
    assert artifacts_response.json()["artifacts"][0]["exists"] is True

    artifact_response = client.get(
        f"/api/runs/{body['run']['run_id']}/artifacts/{artifact_id}",
        headers={"x-hermes-token": "local-token"},
    )
    assert artifact_response.status_code == 200
    assert artifact_response.json() == {"path": artifact_id, "content": "功能清单"}

    quality_response = client.get(
        f"/api/runs/{body['run']['run_id']}/quality",
        headers={"x-hermes-token": "local-token"},
    )
    assert quality_response.status_code == 200
    assert quality_response.json()["run_id"] == body["run"]["run_id"]
    assert quality_response.json()["summary"]["failed"] == 0

    manifest_response = client.get(
        f"/api/runs/{body['run']['run_id']}/manifest",
        headers={"x-hermes-token": "local-token"},
    )
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert manifest["manifest_version"] == 1
    assert manifest["run"]["run_id"] == body["run"]["run_id"]
    assert manifest["steps"][0]["step_id"] == "reverse-login"
    assert manifest["artifacts"][0]["path"] == artifact_id
    assert manifest["artifacts"][0]["step_id"] == "reverse-login"
    assert manifest["quality"]["summary"]["failed"] == 0
    assert [event["type"] for event in manifest["events"]] == [
        "run_created",
        "step_started",
        "artifact_written",
        "step_succeeded",
        "run_succeeded",
    ]

    all_artifacts_response = client.get(
        "/api/artifacts?q=function-list",
        headers={"x-hermes-token": "local-token"},
    )
    assert all_artifacts_response.status_code == 200
    all_artifacts = all_artifacts_response.json()["artifacts"]
    assert all_artifacts[0]["path"] == artifact_id
    assert all_artifacts[0]["run_id"] == body["run"]["run_id"]
    assert all_artifacts[0]["run_status"] == "succeeded"

    other = tmp_path / "artifacts" / "runs" / "run-other" / "reverse-login" / "function-list.md"
    other.parent.mkdir(parents=True)
    other.write_text("鍔熻兘娓呭崟\nreset-password", encoding="utf-8")
    diff_response = client.get(
        f"/api/artifacts/diff?left={artifact_id}&right=artifacts/runs/run-other/reverse-login/function-list.md",
        headers={"x-hermes-token": "local-token"},
    )
    assert diff_response.status_code == 200
    assert diff_response.json()["changed"] is True
    assert "+reset-password" in diff_response.json()["diff"]


def test_api_lints_taskbook_path(tmp_path):
    client = build_client(tmp_path)
    taskbook_path = tmp_path / "login.yml"
    taskbook_path.write_text(
        """
title: 登录模块改造
objective: 输出登录模块逆向文档
steps:
  - id: reverse-login
    agent: niuma-1
    objective: 逆向登录模块
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )

    response = client.post(
        "/api/taskbooks/lint",
        headers={"x-hermes-token": "local-token"},
        json={"taskbook_path": str(taskbook_path)},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "登录模块改造"
    assert response.json()["execution_order"] == ["reverse-login"]


def test_api_lists_reads_and_saves_taskbooks(tmp_path):
    taskbooks_dir = tmp_path / "taskbooks"
    taskbooks_dir.mkdir()
    existing = taskbooks_dir / "legacy.yml"
    existing.write_text(
        """
title: 登录模块改造
objective: 输出登录模块逆向文档
steps:
  - id: reverse-login
    agent: niuma-1
    objective: 逆向登录模块
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path)
    config = worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, FakeWorkerBackend("清单"))})
    app = create_app(supervisor, bus, [config], SecurityGate("local-token"), pipeline_workspace_root=tmp_path)
    client = TestClient(app)

    listed = client.get("/api/taskbooks", headers={"x-hermes-token": "local-token"})
    read = client.get("/api/taskbooks/legacy.yml", headers={"x-hermes-token": "local-token"})
    saved = client.put(
        "/api/taskbooks/new.yml",
        headers={"x-hermes-token": "local-token"},
        json={"content": existing.read_text(encoding="utf-8").replace("登录模块改造", "新模块改造")},
    )

    assert listed.status_code == 200
    assert listed.json()["taskbooks"][0]["filename"] == "legacy.yml"
    assert read.status_code == 200
    assert "登录模块改造" in read.json()["content"]
    assert saved.status_code == 200
    assert (taskbooks_dir / "new.yml").exists()


def test_api_run_injects_source_path_context_into_worker_prompt(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path / "worker-artifacts")
    backend = FakeWorkerBackend("功能清单")
    config = worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, backend)})
    resource_manager = ResourceManager(tmp_path / "marvis.db")
    event_log = EventLog(tmp_path / "events")
    source = tmp_path / "login.jsp"
    source.write_text("<form>登录</form>", encoding="utf-8")
    taskbook_path = tmp_path / "login.yml"
    taskbook_path.write_text(
        """
title: 登录模块改造
objective: 输出登录模块逆向文档
steps:
  - id: reverse-login
    agent: niuma-1
    objective: 逆向登录模块
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    app = create_app(
        supervisor,
        bus,
        [config],
        SecurityGate("local-token"),
        resource_manager=resource_manager,
        event_log=event_log,
        pipeline_workspace_root=tmp_path,
    )
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        headers={"x-hermes-token": "local-token"},
        json={"taskbook_path": str(taskbook_path), "source_path": str(source)},
    )

    assert response.status_code == 200
    assert "## Source Context" in backend.calls[0][0]
    assert "login.jsp" in backend.calls[0][0]
    assert "<form>登录</form>" in backend.calls[0][0]


def test_api_reruns_pipeline_step_with_correction(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path / "worker-artifacts")
    backend = FakeWorkerBackend("fixed function list")
    config = worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, backend)})
    resource_manager = ResourceManager(tmp_path / "marvis.db")
    event_log = EventLog(tmp_path / "events")
    taskbook_path = tmp_path / "login.yml"
    taskbook_path.write_text(
        """
title: login module
objective: reverse login module
steps:
  - id: reverse-login
    agent: niuma-1
    objective: reverse login
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    app = create_app(
        supervisor,
        bus,
        [config],
        SecurityGate("local-token"),
        resource_manager=resource_manager,
        event_log=event_log,
        pipeline_workspace_root=tmp_path,
    )
    client = TestClient(app)
    run_response = client.post(
        "/api/runs",
        headers={"x-hermes-token": "local-token"},
        json={"taskbook_path": str(taskbook_path)},
    )
    run_id = run_response.json()["run"]["run_id"]
    resource_manager.update_pipeline_status(run_id, "failed")
    resource_manager.update_step_status(run_id, "reverse-login", "failed")

    response = client.post(
        f"/api/runs/{run_id}/steps/reverse-login/rerun",
        headers={"x-hermes-token": "local-token"},
        json={"taskbook_path": str(taskbook_path), "correction": "parse JSP login guards"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["status"] == "succeeded"
    assert body["steps"][0]["status"] == "succeeded"
    assert "## Correction For This Rerun" in backend.calls[-1][0]
    assert "parse JSP login guards" in backend.calls[-1][0]
    assert [event["type"] for event in body["events"] if event["type"] == "correction_added"] == ["correction_added"]


def test_api_reruns_pipeline_step_using_saved_run_context(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path / "worker-artifacts")
    backend = FakeWorkerBackend("fixed function list")
    config = worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, backend)})
    resource_manager = ResourceManager(tmp_path / "marvis.db")
    event_log = EventLog(tmp_path / "events")
    source = tmp_path / "login.jsp"
    source.write_text("<form>login</form>", encoding="utf-8")
    taskbook_path = tmp_path / "login.yml"
    taskbook_path.write_text(
        """
title: login module
objective: reverse login module
steps:
  - id: reverse-login
    agent: niuma-1
    objective: reverse login
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    app = create_app(
        supervisor,
        bus,
        [config],
        SecurityGate("local-token"),
        resource_manager=resource_manager,
        event_log=event_log,
        pipeline_workspace_root=tmp_path,
    )
    client = TestClient(app)
    run_response = client.post(
        "/api/runs",
        headers={"x-hermes-token": "local-token"},
        json={"taskbook_path": str(taskbook_path), "source_path": str(source)},
    )
    run_id = run_response.json()["run"]["run_id"]
    resource_manager.update_pipeline_status(run_id, "failed")
    resource_manager.update_step_status(run_id, "reverse-login", "failed")

    response = client.post(
        f"/api/runs/{run_id}/steps/reverse-login/rerun",
        headers={"x-hermes-token": "local-token"},
        json={"correction": "use saved run context"},
    )

    assert response.status_code == 200
    assert response.json()["run"]["status"] == "succeeded"
    assert "## Source Context" in backend.calls[-1][0]
    assert "login.jsp" in backend.calls[-1][0]
    assert "use saved run context" in backend.calls[-1][0]


def test_api_runs_quick_compliance_suite(tmp_path):
    suite_root = tmp_path / "suite"
    (suite_root / "taskbooks").mkdir(parents=True)
    (suite_root / "expected").mkdir()
    (suite_root / "taskbooks" / "legacy-login.yml").write_text(
        """
title: 登录模块改造
objective: 输出登录模块逆向文档
steps:
  - id: reverse-login
    agent: niuma-1
    objective: 逆向登录模块
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    (suite_root / "expected" / "legacy-login.assert.yml").write_text(
        """
assert:
  run_status: succeeded
  steps:
    reverse-login:
      status: succeeded
      output_exists:
        - artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path / "worker-artifacts")
    config = worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, FakeWorkerBackend("compliance output"))})
    app = create_app(
        supervisor,
        bus,
        [config],
        SecurityGate("local-token"),
        pipeline_workspace_root=tmp_path,
    )
    client = TestClient(app)

    response = client.post(
        "/api/compliance/run",
        headers={"x-hermes-token": "local-token"},
        json={"suite_path": str(suite_root), "mode": "quick"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["cases"][0]["name"] == "legacy-login"
    assert response.json()["cases"][0]["status"] == "passed"
    report_path = Path(response.json()["report_path"])
    assert report_path.exists()
    assert report_path.parent == tmp_path / "artifacts" / "compliance"

    reports = client.get("/api/compliance/reports", headers={"x-hermes-token": "local-token"})
    assert reports.status_code == 200
    assert reports.json()["reports"][0]["filename"] == report_path.name

    report = client.get(
        f"/api/compliance/reports/{report_path.name}",
        headers={"x-hermes-token": "local-token"},
    )
    assert report.status_code == 200
    assert report.json()["report"]["success"] is True
    assert report.json()["report"]["cases"][0]["name"] == "legacy-login"


def test_api_runs_model_compliance_suite_through_workers(tmp_path):
    suite_root = tmp_path / "suite"
    (suite_root / "taskbooks").mkdir(parents=True)
    (suite_root / "expected").mkdir()
    (suite_root / "taskbooks" / "legacy-login.yml").write_text(
        """
title: 登录模块改造
objective: 输出登录模块逆向文档
steps:
  - id: reverse-login
    agent: niuma-1
    objective: 逆向登录模块
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    (suite_root / "expected" / "legacy-login.assert.yml").write_text(
        """
assert:
  run_status: succeeded
  steps:
    reverse-login:
      status: succeeded
      output_exists:
        - artifacts/runs/{run_id}/reverse-login/function-list.md
""",
        encoding="utf-8",
    )
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path / "worker-artifacts")
    backend = FakeWorkerBackend("model compliance output")
    config = worker_config("niuma-1")
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": WorkerRuntime(config, bus, artifacts, backend)})
    app = create_app(
        supervisor,
        bus,
        [config],
        SecurityGate("local-token"),
        pipeline_workspace_root=tmp_path,
    )
    client = TestClient(app)

    response = client.post(
        "/api/compliance/run",
        headers={"x-hermes-token": "local-token"},
        json={"suite_path": str(suite_root), "mode": "model"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "逆向登录模块" in backend.calls[0][0]
