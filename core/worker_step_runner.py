from __future__ import annotations

import asyncio
from pathlib import Path

from agent_factory.core.pipeline_executor import StepExecutionContext
from agent_factory.core.worker_runtime import WorkerRuntime


MAX_CONTEXT_CHARS = 40000
MAX_INPUT_FILE_CHARS = 30000


class WorkerRuntimeStepRunner:
    def __init__(self, runtimes: dict[str, WorkerRuntime], global_context: str = ""):
        self.runtimes = runtimes
        self.global_context = global_context

    def __call__(self, context: StepExecutionContext) -> dict[str, str]:
        runtime = self.runtimes.get(context.step.agent)
        if runtime is None:
            raise RuntimeError(f"missing runtime for agent: {context.step.agent}")

        prompt = self._build_prompt(context)
        task = runtime.bus.create_task(context.step.agent, prompt, created_by="marvis-pipeline")
        result = _run_blocking(runtime.execute(task.task_id)).result_text
        return self._collect_outputs(context, result)

    def _build_prompt(self, context: StepExecutionContext) -> str:
        parts = [
            "# Marvis TaskBook Step",
            f"run_id: {context.run_id}",
            f"step_id: {context.step.step_id}",
            f"objective: {context.step.objective}",
            "",
            "## Declared Outputs",
            *[f"- {path}" for path in context.output_paths],
        ]
        if context.step.depends_on:
            parts.extend(["", "## Dependencies", *[f"- {dependency}" for dependency in context.step.depends_on]])
        if context.input_files:
            parts.append("")
            parts.append("## Input Files")
            for path, content in context.input_files.items():
                parts.append(f"### {path}")
                parts.append("```")
                parts.append(_truncate_text(content, MAX_INPUT_FILE_CHARS))
                parts.append("```")
        if self.global_context:
            parts.append("")
            parts.append("## Source Context")
            parts.append(_truncate_text(self.global_context, MAX_CONTEXT_CHARS))
        if context.correction:
            parts.append("")
            parts.append("## Correction For This Rerun")
            parts.append(_truncate_text(context.correction, MAX_INPUT_FILE_CHARS))
        if context.step.self_check:
            parts.extend(["", "## Self Check", *[f"- {item}" for item in context.step.self_check]])
        parts.extend(
            [
                "",
                "请严格根据本 step 目标执行。",
                "必须优先写入 Declared Outputs 中列出的文件路径。",
                "如果底层运行环境无法直接写文件，请输出可保存到第一个 declared output 的 Markdown 内容。",
            ]
        )
        return "\n".join(parts)

    def _collect_outputs(self, context: StepExecutionContext, result_text: str) -> dict[str, str]:
        outputs = {}
        for output_path in context.output_paths:
            path = Path(output_path)
            if path.exists():
                outputs[output_path] = path.read_text(encoding="utf-8")
            else:
                outputs[output_path] = result_text
        return outputs


def _run_blocking(awaitable):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("WorkerRuntimeStepRunner cannot run inside an active event loop; run it in a worker thread")


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n\n[TRUNCATED] omitted {omitted} characters to keep the worker prompt within relay limits."
