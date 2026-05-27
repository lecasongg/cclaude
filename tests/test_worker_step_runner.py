from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.pipeline_executor import StepExecutionContext
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.taskbook import TaskBookPath, TaskBookStep
from agent_factory.core.worker_runtime import FakeWorkerBackend, WorkerRuntime
from agent_factory.core.worker_step_runner import WorkerRuntimeStepRunner
from tests.test_api import worker_config


def test_worker_step_runner_calls_worker_runtime_and_maps_result_to_declared_output(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path / "artifacts")
    backend = FakeWorkerBackend("功能清单：登录、登出")
    config = worker_config("niuma-1")
    runtime = WorkerRuntime(config, bus, artifacts, backend)
    output_path = str(tmp_path / "artifacts" / "runs" / "run-1" / "reverse-login" / "function-list.md")
    runner = WorkerRuntimeStepRunner({"niuma-1": runtime})

    outputs = runner(
        StepExecutionContext(
            run_id="run-1",
            step=TaskBookStep(
                step_id="reverse-login",
                agent="niuma-1",
                objective="逆向登录模块",
                outputs=[TaskBookPath("artifacts/runs/{run_id}/reverse-login/function-list.md")],
                self_check=["必须列出功能清单"],
            ),
            input_paths=[],
            output_paths=[output_path],
            input_files={},
        )
    )

    assert outputs == {output_path: "功能清单：登录、登出"}
    assert backend.calls[0][1].worker_id == "niuma-1"
    assert "逆向登录模块" in backend.calls[0][0]
    assert output_path in backend.calls[0][0]
    assert "必须列出功能清单" in backend.calls[0][0]


def test_worker_step_runner_includes_input_file_content_in_prompt(tmp_path):
    bus = TaskBus(["niuma-2"])
    artifacts = ArtifactStore(tmp_path / "artifacts")
    backend = FakeWorkerBackend("需求文档")
    runtime = WorkerRuntime(worker_config("niuma-2"), bus, artifacts, backend)
    input_path = str(tmp_path / "artifacts" / "runs" / "run-1" / "reverse-login" / "function-list.md")
    output_path = str(tmp_path / "artifacts" / "runs" / "run-1" / "write-requirements" / "requirements.md")

    WorkerRuntimeStepRunner({"niuma-2": runtime})(
        StepExecutionContext(
            run_id="run-1",
            step=TaskBookStep(
                step_id="write-requirements",
                agent="niuma-2",
                objective="编写需求文档",
                depends_on=["reverse-login"],
                inputs=[TaskBookPath("artifacts/runs/{run_id}/reverse-login/function-list.md")],
                outputs=[TaskBookPath("artifacts/runs/{run_id}/write-requirements/requirements.md")],
            ),
            input_paths=[input_path],
            output_paths=[output_path],
            input_files={input_path: "功能清单：登录、登出"},
        )
    )

    prompt = backend.calls[0][0]
    assert input_path in prompt
    assert "功能清单：登录、登出" in prompt
    assert output_path in prompt


def test_worker_step_runner_includes_global_source_context(tmp_path):
    bus = TaskBus(["niuma-1"])
    artifacts = ArtifactStore(tmp_path / "artifacts")
    backend = FakeWorkerBackend("功能清单")
    runtime = WorkerRuntime(worker_config("niuma-1"), bus, artifacts, backend)
    output_path = str(tmp_path / "artifacts" / "runs" / "run-1" / "reverse-login" / "function-list.md")

    WorkerRuntimeStepRunner(
        {"niuma-1": runtime},
        global_context="源文件：login.jsp\n<form>登录</form>",
    )(
        StepExecutionContext(
            run_id="run-1",
            step=TaskBookStep(
                step_id="reverse-login",
                agent="niuma-1",
                objective="逆向登录模块",
                outputs=[TaskBookPath("artifacts/runs/{run_id}/reverse-login/function-list.md")],
            ),
            input_paths=[],
            output_paths=[output_path],
            input_files={},
        )
    )

    prompt = backend.calls[0][0]
    assert "## Source Context" in prompt
    assert "login.jsp" in prompt
    assert "<form>登录</form>" in prompt
