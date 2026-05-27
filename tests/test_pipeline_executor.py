import textwrap

from agent_factory.core.event_log import EventLog
from agent_factory.core.pipeline_executor import PipelineExecutor, StepExecutionContext
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.taskbook import load_taskbook


def test_pipeline_executor_runs_steps_with_file_level_handoff(tmp_path):
    taskbook = _write_taskbook(tmp_path)
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="牛马1")
    manager.register_agent("niuma-2", display_name="牛马2")
    seen_contexts: list[StepExecutionContext] = []

    def runner(context: StepExecutionContext) -> dict[str, str]:
        seen_contexts.append(context)
        if context.step.step_id == "reverse-login":
            return {context.output_paths[0]: "功能清单：登录、登出"}
        return {context.output_paths[0]: "需求文档基于：" + context.input_files[context.input_paths[0]]}

    executor = PipelineExecutor(
        resource_manager=manager,
        event_log=EventLog(tmp_path / "events"),
        workspace_root=tmp_path,
        step_runner=runner,
    )

    run_id = executor.run(taskbook)

    first_output = tmp_path / "artifacts" / "runs" / run_id / "reverse-login" / "function-list.md"
    second_output = tmp_path / "artifacts" / "runs" / run_id / "write-requirements" / "requirements.md"
    assert first_output.read_text(encoding="utf-8") == "功能清单：登录、登出"
    assert second_output.read_text(encoding="utf-8") == "需求文档基于：功能清单：登录、登出"
    assert [context.step.step_id for context in seen_contexts] == ["reverse-login", "write-requirements"]
    assert manager.get_pipeline_run(run_id)["status"] == "succeeded"
    assert manager.get_step_run(run_id, "write-requirements")["status"] == "succeeded"


def test_pipeline_executor_stops_downstream_after_step_failure(tmp_path):
    taskbook = _write_taskbook(tmp_path)
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="牛马1")
    manager.register_agent("niuma-2", display_name="牛马2")

    def runner(context: StepExecutionContext) -> dict[str, str]:
        if context.step.step_id == "reverse-login":
            raise RuntimeError("legacy parser failed")
        return {context.output_paths[0]: "should not run"}

    event_log = EventLog(tmp_path / "events")
    executor = PipelineExecutor(
        resource_manager=manager,
        event_log=event_log,
        workspace_root=tmp_path,
        step_runner=runner,
    )

    run_id = executor.run(taskbook)

    assert manager.get_pipeline_run(run_id)["status"] == "failed"
    assert manager.get_step_run(run_id, "reverse-login")["status"] == "failed"
    assert manager.get_step_run(run_id, "write-requirements")["status"] == "blocked"
    assert [event["type"] for event in event_log.read_events(run_id)] == [
        "run_created",
        "step_started",
        "step_failed",
        "step_blocked",
        "run_failed",
    ]


def test_pipeline_executor_reruns_failed_step_with_correction_and_downstream(tmp_path):
    taskbook = _write_taskbook(tmp_path)
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="鐗涢┈1")
    manager.register_agent("niuma-2", display_name="鐗涢┈2")
    calls: list[StepExecutionContext] = []

    def runner(context: StepExecutionContext) -> dict[str, str]:
        calls.append(context)
        if context.step.step_id == "reverse-login" and not context.correction:
            raise RuntimeError("legacy parser failed")
        if context.step.step_id == "reverse-login":
            return {context.output_paths[0]: "fixed function list"}
        return {context.output_paths[0]: "requirements from " + context.input_files[context.input_paths[0]]}

    event_log = EventLog(tmp_path / "events")
    executor = PipelineExecutor(
        resource_manager=manager,
        event_log=event_log,
        workspace_root=tmp_path,
        step_runner=runner,
    )
    run_id = executor.run(taskbook)

    executor.rerun_from_step(run_id, taskbook, "reverse-login", correction="parse JSP login guards")

    assert manager.get_pipeline_run(run_id)["status"] == "succeeded"
    assert manager.get_step_run(run_id, "reverse-login")["status"] == "succeeded"
    assert manager.get_step_run(run_id, "write-requirements")["status"] == "succeeded"
    assert calls[1].step.step_id == "reverse-login"
    assert calls[1].correction == "parse JSP login guards"
    assert calls[2].step.step_id == "write-requirements"
    assert (tmp_path / "artifacts" / "runs" / run_id / "write-requirements" / "requirements.md").read_text(
        encoding="utf-8"
    ) == "requirements from fixed function list"
    event_types = [event["type"] for event in event_log.read_events(run_id)]
    assert "step_rerun_requested" in event_types
    assert "correction_added" in event_types
    assert event_types[-1] == "run_succeeded"


def _write_taskbook(tmp_path):
    taskbook_path = tmp_path / "login.yml"
    taskbook_path.write_text(
        textwrap.dedent(
            """
            title: 登录模块改造
            objective: 输出登录模块逆向文档和需求文档
            steps:
              - id: reverse-login
                agent: niuma-1
                objective: 逆向登录模块
                outputs:
                  - path: artifacts/runs/{run_id}/reverse-login/function-list.md
              - id: write-requirements
                agent: niuma-2
                depends_on:
                  - reverse-login
                objective: 编写需求文档
                inputs:
                  - path: artifacts/runs/{run_id}/reverse-login/function-list.md
                outputs:
                  - path: artifacts/runs/{run_id}/write-requirements/requirements.md
            """
        ),
        encoding="utf-8",
    )
    return load_taskbook(taskbook_path)
