import json
from urllib import error

import pytest

from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.models import WorkerConfig, TaskStatus
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.worker_runtime import FakeWorkerBackend, OpenAICompatibleWorkerBackend, SubprocessWorkerBackend, WorkerRuntime


def worker_config(worker_id="niuma-1", root=None):
    base = root or "."
    return WorkerConfig(
        worker_id=worker_id,
        display_name="牛马1",
        provider="deepseek",
        model="deepseek-chat",
        api_key_env="NIUMA_1_API_KEY",
        profile_dir=str(base / f"profiles/{worker_id}") if root else f"profiles/{worker_id}",
        workspace_dir=str(base / f"workspaces/{worker_id}") if root else f"workspaces/{worker_id}",
        skills_dir=str(base / f"skills/{worker_id}") if root else f"skills/{worker_id}",
    )


@pytest.mark.asyncio
async def test_worker_runtime_executes_task_and_writes_artifact(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path)
    backend = FakeWorkerBackend("需求清单内容")
    runtime = WorkerRuntime(worker_config(), bus, artifacts, backend)
    task = bus.create_task("niuma-1", "分析 JSP")

    result = await runtime.execute(task.task_id)

    assert result.status == TaskStatus.SUCCEEDED
    assert result.result_text == "需求清单内容"
    assert len(result.artifact_ids) == 1
    assert artifacts.read_text(result.artifact_ids[0]) == "需求清单内容"
    assert backend.calls == [("分析 JSP", worker_config())]


@pytest.mark.asyncio
async def test_worker_runtime_refuses_other_worker_task(tmp_path):
    bus = TaskBus(["niuma-1", "niuma-2"])
    artifacts = ArtifactStore(tmp_path)
    runtime = WorkerRuntime(worker_config("niuma-1"), bus, artifacts, FakeWorkerBackend("ignored"))
    task = bus.create_task("niuma-2", "编写需求")

    with pytest.raises(ValueError, match="task task-.* does not belong to worker niuma-1"):
        await runtime.execute(task.task_id)


@pytest.mark.asyncio
async def test_subprocess_worker_backend_runs_in_independent_workspace(tmp_path):
    worker_script = tmp_path / "worker.py"
    worker_script.write_text(
        """
import os
import sys
from pathlib import Path
prompt = Path(sys.argv[1]).read_text(encoding='utf-8')
Path(sys.argv[2]).write_text(os.getcwd() + '\\n' + os.environ['NIUMA_WORKER_ID'] + '\\n' + prompt, encoding='utf-8')
""".strip(),
        encoding="utf-8",
    )
    config = worker_config("niuma-1", tmp_path)
    backend = SubprocessWorkerBackend(["python", str(worker_script)])

    result = await backend.run("分析 JSP", config)

    assert config.workspace_dir in result
    assert "niuma-1" in result
    assert "分析 JSP" in result


@pytest.mark.asyncio
async def test_openai_compatible_backend_posts_chat_completion(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "真实模型输出"}}]}).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    monkeypatch.delenv("DEEPSEEK_API_URL", raising=False)
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_URL", raising=False)
    monkeypatch.setattr("agent_factory.core.worker_runtime.request.urlopen", fake_urlopen)
    backend = OpenAICompatibleWorkerBackend()

    result = await backend.run("分析 JSP", worker_config())

    assert result == "真实模型输出"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["body"]["model"] == "deepseek-chat"
    assert captured["body"]["messages"][0]["content"] == (
        "你是 牛马1，独立工位 niuma-1。\n"
        "固定角色：通用交付工位。\n"
        "请只根据用户提供的任务和上游产物输出，不要编造日期、仓库、账号、密码、联系人、内部系统或不存在的附件。\n"
        "如果信息不足，请明确写出“信息不足，以下为基于现有输入的推测”。\n"
        "如果用户只是问候或闲聊，请简短自然回复，不要强行生成交接文档。\n"
        "正式任务结果请写成可交接的 Markdown 产物。"
    )
    assert captured["timeout"] == 600


@pytest.mark.asyncio
async def test_openai_compatible_backend_uses_worker_role_in_system_prompt(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "角色输出"}}]}).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    config = worker_config()
    config.role = "JSP/JS/SQL 老系统逆向分析工位"
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    monkeypatch.setattr("agent_factory.core.worker_runtime.request.urlopen", fake_urlopen)

    await OpenAICompatibleWorkerBackend().run("分析 JSP", config)

    assert "固定角色：JSP/JS/SQL 老系统逆向分析工位。" in captured["body"]["messages"][0]["content"]

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "代理输出"}}]}).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return FakeResponse()

    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "http://smarthse.51vip.biz:53001")
    monkeypatch.setattr("agent_factory.core.worker_runtime.request.urlopen", fake_urlopen)

    result = await OpenAICompatibleWorkerBackend().run("测试代理", worker_config())

    assert result == "代理输出"
    assert captured["url"] == "http://smarthse.51vip.biz:53001/v1/chat/completions"


@pytest.mark.asyncio
async def test_openai_compatible_backend_uses_worker_base_url_instead_of_global_url(monkeypatch):
    captured = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "代理输出"}}]}).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured.append(req.full_url)
        return FakeResponse()

    niuma_1 = worker_config("niuma-1")
    niuma_1.base_url = "http://relay-a.local/v1"
    niuma_2 = worker_config("niuma-2")
    niuma_2.api_key_env = "NIUMA_2_API_KEY"
    niuma_2.base_url = "http://relay-b.local/v1"
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-1")
    monkeypatch.setenv("NIUMA_2_API_KEY", "sk-2")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "http://global-relay.local/v1")
    monkeypatch.setattr("agent_factory.core.worker_runtime.request.urlopen", fake_urlopen)
    backend = OpenAICompatibleWorkerBackend()

    await backend.run("测试代理", niuma_1)
    await backend.run("测试代理", niuma_2)

    assert captured == [
        "http://relay-a.local/v1/chat/completions",
        "http://relay-b.local/v1/chat/completions",
    ]


def test_openai_compatible_backend_configure_api_url_sets_completion_url():
    backend = OpenAICompatibleWorkerBackend()

    backend.configure_api_url("http://relay.local/v1")

    assert backend.api_url == "http://relay.local/v1/chat/completions"


@pytest.mark.asyncio
async def test_openai_compatible_backend_reports_http_error_body(monkeypatch):
    def fake_urlopen(req, timeout):
        raise error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)

    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_URL", "http://smarthse.51vip.biz:53001")
    monkeypatch.setattr("agent_factory.core.worker_runtime.request.urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="Model provider returned HTTP 503"):
        await OpenAICompatibleWorkerBackend().run("测试代理", worker_config())


    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return b"<html>not found</html>"

    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_URL", "http://smarthse.51vip.biz:53001")
    monkeypatch.setattr("agent_factory.core.worker_runtime.request.urlopen", lambda req, timeout: FakeResponse())

    with pytest.raises(RuntimeError, match="Model provider returned non-JSON response"):
        await OpenAICompatibleWorkerBackend().run("测试代理", worker_config())
