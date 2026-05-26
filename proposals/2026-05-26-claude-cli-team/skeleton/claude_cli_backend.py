"""Skeleton: ClaudeCliWorkerBackend

完整可运行的最小实现。落地时直接 copy 进 core/worker_runtime.py 末尾，
或保留在独立文件（core/backends/claude_cli.py）由 build_backend 引用。
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from agent_factory.core.models import WorkerConfig


@dataclass
class ClaudeCliWorkerBackend:
    """把一个 niuma 任务交给独立 claude CLI 子进程跑完。

    - 每次 run() 一次 subprocess，运行完即退出（agent 一次性会话）
    - 通过 CLAUDE_CONFIG_DIR / --cwd 隔离 profile 与工作区
    - 通过 stream-json 解析最终 result
    """

    claude_command: list[str] = field(default_factory=lambda: ["claude"])
    timeout_seconds: int = 1800
    extra_args: list[str] = field(default_factory=list)

    async def run(self, prompt: str, config: WorkerConfig) -> str:
        profile_dir = Path(config.profile_dir).resolve()
        workspace_dir = Path(config.workspace_dir).resolve()
        skills_dir = Path(config.skills_dir).resolve()

        profile_dir.mkdir(parents=True, exist_ok=True)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.mkdir(parents=True, exist_ok=True)

        # 把 skills/niuma-N/ 的内容软链到 workspace/.claude/skills 让 claude CLI 发现
        from agent_factory.core.skill_linking import link_worker_skills
        link_worker_skills(skills_dir, workspace_dir)

        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(profile_dir)

        args = [
            *self.claude_command,
            "-p", prompt,
            "--output-format", "stream-json",
            "--cwd", str(workspace_dir),
            "--model", config.model,
            *self.extra_args,
        ]

        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(workspace_dir),
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError(f"claude CLI exceeded {self.timeout_seconds}s, killed")

        if process.returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace")[:400]
            raise RuntimeError(
                f"claude CLI exited {process.returncode}: {stderr_text}"
            )

        events_path = workspace_dir / ".hermes" / "last-events.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)

        last_result_text = ""
        with events_path.open("w", encoding="utf-8") as events_file:
            for line in stdout.decode("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                events_file.write(line + "\n")
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "result":
                    last_result_text = event.get("result", "")
        return last_result_text
