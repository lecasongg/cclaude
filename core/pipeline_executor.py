from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent_factory.core.event_log import EventLog
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.taskbook import TaskBook, TaskBookStep


@dataclass(frozen=True)
class StepExecutionContext:
    run_id: str
    step: TaskBookStep
    input_paths: list[str]
    output_paths: list[str]
    input_files: dict[str, str]


StepRunner = Callable[[StepExecutionContext], dict[str, str]]


class PipelineExecutor:
    def __init__(
        self,
        resource_manager: ResourceManager,
        event_log: EventLog,
        workspace_root: str | Path,
        step_runner: StepRunner,
    ):
        self.resource_manager = resource_manager
        self.event_log = event_log
        self.workspace_root = Path(workspace_root)
        self.step_runner = step_runner

    def run(self, taskbook: TaskBook) -> str:
        run_id = self.resource_manager.create_pipeline_run(taskbook.title)
        self.event_log.write_event(run_id, "run_created", payload={"title": taskbook.title})
        leases = []
        steps_by_id = {step.step_id: step for step in taskbook.steps}

        try:
            for agent_id in sorted({step.agent for step in taskbook.steps}):
                leases.append(self.resource_manager.acquire_lease(agent_id, run_id, owner="pipeline-executor"))

            for step in taskbook.steps:
                self.resource_manager.create_step_run(
                    run_id,
                    step_id=step.step_id,
                    agent_id=step.agent,
                    objective=step.objective,
                    depends_on=step.depends_on,
                    outputs=[item.path for item in step.outputs],
                    self_check=step.self_check,
                )

            self.resource_manager.update_pipeline_status(run_id, "running")
            completed_steps: set[str] = set()
            for step_id in taskbook.execution_order():
                step = steps_by_id[step_id]
                if not all(dependency in completed_steps for dependency in step.depends_on):
                    self._block_step(run_id, step)
                    continue
                try:
                    self._run_step(run_id, step)
                except Exception as exc:
                    self.resource_manager.update_step_status(run_id, step.step_id, "failed")
                    self.event_log.write_event(
                        run_id,
                        "step_failed",
                        agent_id=step.agent,
                        step_id=step.step_id,
                        payload={"error": str(exc)},
                    )
                    self._block_downstream(run_id, taskbook, failed_step_id=step.step_id)
                    self.resource_manager.update_pipeline_status(run_id, "failed")
                    self.event_log.write_event(run_id, "run_failed", payload={"failed_step_id": step.step_id})
                    return run_id
                completed_steps.add(step.step_id)

            self.resource_manager.update_pipeline_status(run_id, "succeeded")
            self.event_log.write_event(run_id, "run_succeeded")
            return run_id
        finally:
            for lease_id in leases:
                self.resource_manager.release_lease(lease_id)

    def _run_step(self, run_id: str, step: TaskBookStep) -> None:
        self.resource_manager.update_step_status(run_id, step.step_id, "running")
        self.event_log.write_event(run_id, "step_started", agent_id=step.agent, step_id=step.step_id)
        context = self._build_context(run_id, step)
        outputs = self.step_runner(context)
        for output_path in context.output_paths:
            if output_path not in outputs:
                raise RuntimeError(f"step {step.step_id} did not produce declared output: {output_path}")
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(outputs[output_path], encoding="utf-8")
            self.event_log.write_event(
                run_id,
                "artifact_written",
                agent_id=step.agent,
                step_id=step.step_id,
                payload={"path": str(output)},
            )
        self.resource_manager.update_step_status(run_id, step.step_id, "succeeded")
        self.event_log.write_event(run_id, "step_succeeded", agent_id=step.agent, step_id=step.step_id)

    def _build_context(self, run_id: str, step: TaskBookStep) -> StepExecutionContext:
        input_paths = [str(self._resolve_run_path(item.path, run_id)) for item in step.inputs]
        output_paths = [str(self._resolve_run_path(item.path, run_id)) for item in step.outputs]
        input_files = {path: Path(path).read_text(encoding="utf-8") for path in input_paths}
        return StepExecutionContext(
            run_id=run_id,
            step=step,
            input_paths=input_paths,
            output_paths=output_paths,
            input_files=input_files,
        )

    def _resolve_run_path(self, path: str, run_id: str) -> Path:
        return self.workspace_root / path.replace("{run_id}", run_id)

    def _block_downstream(self, run_id: str, taskbook: TaskBook, failed_step_id: str) -> None:
        should_block = False
        for step_id in taskbook.execution_order():
            if step_id == failed_step_id:
                should_block = True
                continue
            if should_block:
                self._block_step(run_id, taskbook.step(step_id))

    def _block_step(self, run_id: str, step: TaskBookStep) -> None:
        self.resource_manager.update_step_status(run_id, step.step_id, "blocked")
        self.event_log.write_event(run_id, "step_blocked", agent_id=step.agent, step_id=step.step_id)
