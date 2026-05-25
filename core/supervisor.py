from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.models import TaskRecord
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.worker_runtime import WorkerRuntime


class HermesSupervisor:
    def __init__(self, bus: TaskBus, artifacts: ArtifactStore, runtimes: dict[str, WorkerRuntime]):
        self.bus = bus
        self.artifacts = artifacts
        self.runtimes = runtimes

    async def delegate(self, worker_id: str, prompt: str, created_by: str = "hermes") -> TaskRecord:
        task = self.bus.create_task(worker_id, prompt, created_by=created_by)
        return await self.runtimes[worker_id].execute(task.task_id)

    async def chain(
        self,
        source_worker: str,
        target_worker: str,
        prompt: str,
        next_instruction: str,
    ) -> tuple[TaskRecord, TaskRecord]:
        first = await self.delegate(source_worker, prompt)
        artifact_texts = [self.artifacts.read_text(artifact_id) for artifact_id in first.artifact_ids]
        handoff_prompt = (
            f"{next_instruction}\n\n"
            f"上游任务: {prompt}\n\n"
            "上游产物:\n"
            + "\n\n---\n\n".join(artifact_texts)
        )
        second = self.bus.create_task(
            target_worker,
            handoff_prompt,
            created_by="hermes",
            parent_task_id=first.task_id,
        )
        second = await self.runtimes[target_worker].execute(second.task_id)
        return first, second
