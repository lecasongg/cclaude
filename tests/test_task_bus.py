from agent_factory.core.models import TaskRecord, TaskStatus, WorkerConfig, WorkerState
from agent_factory.core.task_bus import TaskBus


def test_worker_config_requires_independent_identity_and_paths():
    config = WorkerConfig(
        worker_id="niuma-1",
        display_name="牛马1",
        provider="deepseek",
        model="deepseek-chat",
        api_key_env="NIUMA_1_API_KEY",
        profile_dir="profiles/niuma-1",
        workspace_dir="workspaces/niuma-1",
        skills_dir="skills/niuma-1",
    )

    assert config.worker_id == "niuma-1"
    assert config.api_key_env == "NIUMA_1_API_KEY"
    assert config.profile_dir != config.workspace_dir
    assert config.skills_dir == "skills/niuma-1"
    assert config.enabled is True


def test_task_record_defaults_to_queued_with_independent_artifact_lists():
    first = TaskRecord(task_id="task-1", worker_id="niuma-1", prompt="分析 JSP")
    second = TaskRecord(task_id="task-2", worker_id="niuma-2", prompt="编写需求")

    first.artifact_ids.append("artifact-1")

    assert first.status == TaskStatus.QUEUED
    assert first.created_by == "user"
    assert first.result_text == ""
    assert first.error == ""
    assert first.artifact_ids == ["artifact-1"]
    assert second.artifact_ids == []


def test_worker_state_tracks_current_task_and_queue_depth():
    state = WorkerState(worker_id="niuma-1", status="running", current_task_id="task-1", queue_depth=2)

    assert state.worker_id == "niuma-1"
    assert state.status == "running"
    assert state.current_task_id == "task-1"
    assert state.queue_depth == 2


def test_task_bus_creates_tasks_and_reports_worker_queue_depth():
    bus = TaskBus(["niuma-1", "niuma-2"])

    first = bus.create_task("niuma-1", "分析 JSP", created_by="hermes")
    second = bus.create_task("niuma-1", "输出清单")
    other = bus.create_task("niuma-2", "编写需求")

    assert first.task_id != second.task_id
    assert first.created_by == "hermes"
    assert bus.next_queued_task("niuma-1").task_id == first.task_id
    assert bus.worker_state("niuma-1").queue_depth == 2
    assert bus.worker_state("niuma-2").queue_depth == 1
    assert other.worker_id == "niuma-2"


def test_task_bus_tracks_running_and_completed_state():
    bus = TaskBus(["niuma-1"])
    task = bus.create_task("niuma-1", "分析 JSP")

    bus.mark_running(task.task_id)
    running = bus.get_task(task.task_id)

    assert running.status == TaskStatus.RUNNING
    assert running.started_at is not None
    assert bus.worker_state("niuma-1").status == "running"
    assert bus.worker_state("niuma-1").current_task_id == task.task_id

    bus.mark_succeeded(task.task_id, "完成", ["artifact-1"])
    completed = bus.get_task(task.task_id)

    assert completed.status == TaskStatus.SUCCEEDED
    assert completed.result_text == "完成"
    assert completed.artifact_ids == ["artifact-1"]
    assert completed.finished_at is not None
    assert bus.worker_state("niuma-1").status == "idle"
    assert bus.worker_state("niuma-1").current_task_id == ""
