from dataclasses import dataclass, field
from enum import StrEnum
from time import time


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkerConfig:
    worker_id: str
    display_name: str
    provider: str
    model: str
    api_key_env: str
    profile_dir: str
    workspace_dir: str
    skills_dir: str
    base_url: str = ""
    role: str = "通用交付工位"
    enabled: bool = True


@dataclass
class TaskRecord:
    task_id: str
    worker_id: str
    prompt: str
    status: TaskStatus = TaskStatus.QUEUED
    parent_task_id: str = ""
    created_by: str = "user"
    created_at: float = field(default_factory=time)
    started_at: float | None = None
    finished_at: float | None = None
    result_text: str = ""
    error: str = ""
    artifact_ids: list[str] = field(default_factory=list)


@dataclass
class WorkerState:
    worker_id: str
    status: str = "idle"
    current_task_id: str = ""
    queue_depth: int = 0
