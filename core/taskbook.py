from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


class TaskBookError(ValueError):
    pass


@dataclass(frozen=True)
class TaskBookPath:
    path: str


@dataclass(frozen=True)
class TaskBookStep:
    step_id: str
    agent: str
    objective: str
    depends_on: list[str] = field(default_factory=list)
    inputs: list[TaskBookPath] = field(default_factory=list)
    outputs: list[TaskBookPath] = field(default_factory=list)
    self_check: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TaskBook:
    title: str
    objective: str
    steps: list[TaskBookStep]
    agents: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    taskbook_version: int = 1

    def step(self, step_id: str) -> TaskBookStep:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        raise TaskBookError(f"unknown step: {step_id}")

    def execution_order(self) -> list[str]:
        steps_by_id = {step.step_id: step for step in self.steps}
        remaining = set(steps_by_id)
        order: list[str] = []

        while remaining:
            ready = [
                step.step_id
                for step in self.steps
                if step.step_id in remaining and all(dependency in order for dependency in step.depends_on)
            ]
            if not ready:
                raise TaskBookError("cycle detected in taskbook dependencies")
            for step_id in ready:
                remaining.remove(step_id)
                order.append(step_id)
        return order


def load_taskbook(path: str | Path) -> TaskBook:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise TaskBookError("taskbook root must be a mapping")
    taskbook = _taskbook_from_mapping(data)
    validate_taskbook(taskbook)
    return taskbook


def validate_taskbook(taskbook: TaskBook) -> None:
    if not taskbook.title:
        raise TaskBookError("missing required field title")
    if not taskbook.objective:
        raise TaskBookError("missing required field objective")
    if not taskbook.steps:
        raise TaskBookError("taskbook must contain at least one step")

    seen: set[str] = set()
    for step in taskbook.steps:
        if step.step_id in seen:
            raise TaskBookError(f"duplicate step id: {step.step_id}")
        seen.add(step.step_id)
        if not step.agent:
            raise TaskBookError(f"missing agent for step {step.step_id}")
        if not step.objective:
            raise TaskBookError(f"missing objective for step {step.step_id}")
        if not step.outputs:
            raise TaskBookError(f"missing outputs for step {step.step_id}")
        for output in step.outputs:
            if not _valid_artifact_output_path(output.path):
                raise TaskBookError(f"invalid output path for step {step.step_id}: {output.path}")

    for step in taskbook.steps:
        for dependency in step.depends_on:
            if dependency not in seen:
                raise TaskBookError(f"unknown dependency {dependency} for step {step.step_id}")

    taskbook.execution_order()


def _taskbook_from_mapping(data: dict[str, Any]) -> TaskBook:
    return TaskBook(
        taskbook_version=int(data.get("taskbook_version", 1)),
        title=str(data.get("title", "")),
        objective=str(data.get("objective", "")),
        agents=list(data.get("agents", [])),
        constraints=list(data.get("constraints", [])),
        steps=[_step_from_mapping(raw_step) for raw_step in data.get("steps", [])],
    )


def _step_from_mapping(data: dict[str, Any]) -> TaskBookStep:
    if not isinstance(data, dict):
        raise TaskBookError("step entries must be mappings")
    return TaskBookStep(
        step_id=str(data.get("id", "")),
        agent=str(data.get("agent", "")),
        objective=str(data.get("objective", "")),
        depends_on=list(data.get("depends_on", [])),
        inputs=_paths_from_list(data.get("inputs", [])),
        outputs=_paths_from_list(data.get("outputs", [])),
        self_check=list(data.get("self_check", [])),
    )


def _paths_from_list(values: Any) -> list[TaskBookPath]:
    paths = []
    for value in values or []:
        if isinstance(value, str):
            paths.append(TaskBookPath(value))
        elif isinstance(value, dict) and "path" in value:
            paths.append(TaskBookPath(str(value["path"])))
        else:
            raise TaskBookError("path entries must be strings or objects with path")
    return paths


def _valid_artifact_output_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return False
    parts = PurePosixPath(normalized).parts
    if ".." in parts:
        return False
    return normalized.startswith("artifacts/runs/")
