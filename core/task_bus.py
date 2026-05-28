from time import time
from uuid import uuid4

from agent_factory.core.models import TaskRecord, TaskStatus, WorkerState


class TaskBus:
    def __init__(self, worker_ids: list[str]):
        self._tasks: dict[str, TaskRecord] = {}
        self._worker_ids = list(worker_ids)
        self._current_task_by_worker: dict[str, str] = {worker_id: "" for worker_id in worker_ids}

    def register_worker(self, worker_id: str) -> None:
        if worker_id not in self._worker_ids:
            self._worker_ids.append(worker_id)
        self._current_task_by_worker.setdefault(worker_id, "")

    def create_task(
        self,
        worker_id: str,
        prompt: str,
        created_by: str = "user",
        parent_task_id: str = "",
    ) -> TaskRecord:
        task = TaskRecord(
            task_id=f"task-{uuid4().hex}",
            worker_id=worker_id,
            prompt=prompt,
            created_by=created_by,
            parent_task_id=parent_task_id,
        )
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> TaskRecord:
        return self._tasks[task_id]

    def next_queued_task(self, worker_id: str) -> TaskRecord | None:
        for task in self._tasks.values():
            if task.worker_id == worker_id and task.status == TaskStatus.QUEUED:
                return task
        return None

    def mark_running(self, task_id: str) -> TaskRecord:
        task = self._tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.started_at = time()
        self._current_task_by_worker[task.worker_id] = task.task_id
        return task

    def mark_succeeded(self, task_id: str, result_text: str, artifact_ids: list[str] | None = None) -> TaskRecord:
        task = self._tasks[task_id]
        task.status = TaskStatus.SUCCEEDED
        task.result_text = result_text
        task.artifact_ids = list(artifact_ids or [])
        task.finished_at = time()
        self._current_task_by_worker[task.worker_id] = ""
        return task

    def mark_failed(self, task_id: str, error: str) -> TaskRecord:
        task = self._tasks[task_id]
        task.status = TaskStatus.FAILED
        task.error = error
        task.finished_at = time()
        self._current_task_by_worker[task.worker_id] = ""
        return task

    def list_tasks(self) -> list[TaskRecord]:
        return sorted(self._tasks.values(), key=lambda task: task.created_at, reverse=True)

    def worker_state(self, worker_id: str) -> WorkerState:
        current_task_id = self._current_task_by_worker.get(worker_id, "")
        queue_depth = sum(
            1
            for task in self._tasks.values()
            if task.worker_id == worker_id and task.status == TaskStatus.QUEUED
        )
        return WorkerState(
            worker_id=worker_id,
            status="running" if current_task_id else "idle",
            current_task_id=current_task_id,
            queue_depth=queue_depth,
        )
