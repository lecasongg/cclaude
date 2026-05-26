import pytest

from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.models import WorkerConfig, TaskStatus
from agent_factory.core.supervisor import HermesSupervisor
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.worker_runtime import FakeWorkerBackend, WorkerRuntime


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


@pytest.mark.asyncio
async def test_supervisor_delegates_to_selected_worker(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path)
    runtime = WorkerRuntime(worker_config("niuma-1"), bus, artifacts, FakeWorkerBackend("分析完成"))
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": runtime})

    result = await supervisor.delegate("niuma-1", "分析 JSP")

    assert result.worker_id == "niuma-1"
    assert result.status == TaskStatus.SUCCEEDED
    assert result.result_text == "分析完成"


@pytest.mark.asyncio
async def test_supervisor_chain_passes_source_artifacts_to_target(tmp_path):
    bus = TaskBus(["niuma-1", "niuma-2"])
    artifacts = ArtifactStore(tmp_path)
    source_runtime = WorkerRuntime(worker_config("niuma-1"), bus, artifacts, FakeWorkerBackend("# 需求清单"))
    target_backend = FakeWorkerBackend("# 需求文档")
    target_runtime = WorkerRuntime(worker_config("niuma-2"), bus, artifacts, target_backend)
    supervisor = HermesSupervisor(
        bus,
        artifacts,
        {"niuma-1": source_runtime, "niuma-2": target_runtime},
    )

    first, second = await supervisor.chain("niuma-1", "niuma-2", "逆向分析 JSP", "根据清单编写需求文档")

    assert first.status == TaskStatus.SUCCEEDED
    assert second.status == TaskStatus.SUCCEEDED
    assert second.parent_task_id == first.task_id
    assert "上游任务: 逆向分析 JSP" in target_backend.calls[0][0]
    assert "上游产物文件路径" in target_backend.calls[0][0]
    assert "# 需求清单" not in target_backend.calls[0][0]


@pytest.mark.asyncio
async def test_supervisor_chain_passes_artifact_file_paths_not_content(tmp_path):
    bus = TaskBus(["niuma-1", "niuma-2"])
    artifacts = ArtifactStore(tmp_path)
    source_runtime = WorkerRuntime(worker_config("niuma-1"), bus, artifacts, FakeWorkerBackend("# 需求清单\n非常长的内容" * 100))
    target_backend = FakeWorkerBackend("# 需求文档")
    target_runtime = WorkerRuntime(worker_config("niuma-2"), bus, artifacts, target_backend)
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": source_runtime, "niuma-2": target_runtime})

    await supervisor.chain("niuma-1", "niuma-2", "逆向 JSP", "写文档")

    target_prompt = target_backend.calls[0][0]
    assert "非常长的内容" not in target_prompt
    assert "result.md" in target_prompt
    assert "请用 Read 工具读取" in target_prompt
