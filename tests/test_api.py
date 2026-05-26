import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from agent_factory.core.api import create_app
from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.models import WorkerConfig
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

    assert "installDocument($event, 'conversion_rules')" in html
    assert "installDocument($event, 'task_manual')" in html
    assert "@change=\"installDocument\"" not in html


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
            "workspace_dir": "workspaces/niuma-2",
            "skills_dir": "skills/niuma-2",
            "installed_documents": {
                "task_manual": {"installed": False, "filename": "", "size": 0},
                "conversion_rules": {"installed": False, "filename": "", "size": 0},
            },
        },
    ]


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
            "base_url": "http://smarthse.51vip.biz:53001/v1",
            "api_key": "sk-secret",
        },
    )

    assert response.status_code == 200
    assert response.json()["worker"]["provider"] == "smarthse"
    assert response.json()["worker"]["model"] == "deepseek-v4-pro"
    assert response.json()["worker"]["role"] == "JSP 逆向工位"
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
