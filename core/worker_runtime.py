import asyncio
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib import error, request

from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.models import TaskRecord, WorkerConfig
from agent_factory.core.task_bus import TaskBus


@dataclass
class FakeWorkerBackend:
    response_text: str
    calls: list[tuple[str, WorkerConfig]] = field(default_factory=list)

    async def run(self, prompt: str, config: WorkerConfig) -> str:
        self.calls.append((prompt, config))
        return self.response_text


@dataclass
class SubprocessWorkerBackend:
    command: list[str]
    timeout_seconds: int = 600

    async def run(self, prompt: str, config: WorkerConfig) -> str:
        Path(config.profile_dir).mkdir(parents=True, exist_ok=True)
        Path(config.workspace_dir).mkdir(parents=True, exist_ok=True)
        Path(config.skills_dir).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"{config.worker_id}-") as temp_dir:
            prompt_path = Path(temp_dir) / "prompt.txt"
            result_path = Path(temp_dir) / "result.md"
            prompt_path.write_text(prompt, encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "NIUMA_WORKER_ID": config.worker_id,
                    "NIUMA_PROVIDER": config.provider,
                    "NIUMA_MODEL": config.model,
                    "NIUMA_API_KEY_ENV": config.api_key_env,
                    "NIUMA_PROFILE_DIR": config.profile_dir,
                    "NIUMA_WORKSPACE_DIR": config.workspace_dir,
                    "NIUMA_SKILLS_DIR": config.skills_dir,
                }
            )
            completed = subprocess.run(
                [*self.command, str(prompt_path), str(result_path)],
                cwd=config.workspace_dir,
                env=env,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError((completed.stderr or completed.stdout or f"worker exited {completed.returncode}").strip())
            if result_path.exists():
                return result_path.read_text(encoding="utf-8")
            return completed.stdout.strip()


@dataclass
class OpenAICompatibleWorkerBackend:
    api_url: str = "https://api.deepseek.com/chat/completions"
    timeout_seconds: int = 600

    def completion_url(self, base_url: str | None = None) -> str:
        configured_url = (base_url or os.environ.get("OPENAI_COMPATIBLE_API_URL") or os.environ.get("DEEPSEEK_API_URL", self.api_url)).rstrip("/")
        if configured_url.endswith("/chat/completions"):
            return configured_url
        if configured_url.endswith("/v1"):
            return f"{configured_url}/chat/completions"
        if configured_url == "https://api.deepseek.com":
            return f"{configured_url}/chat/completions"
        return f"{configured_url}/v1/chat/completions"

    def configure_api_url(self, base_url: str | None = None) -> None:
        self.api_url = self.completion_url(base_url)
        self.configure_api_url()

    async def run(self, prompt: str, config: WorkerConfig) -> str:
        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            raise RuntimeError(f"missing API key environment variable: {config.api_key_env}")
        payload = {
            "model": config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"你是 {config.display_name}，独立工位 {config.worker_id}。\n"
                        f"固定角色：{config.role}。\n"
                        "请只根据用户提供的任务和上游产物输出，不要编造日期、仓库、账号、密码、联系人、内部系统或不存在的附件。\n"
                        "如果信息不足，请明确写出“信息不足，以下为基于现有输入的推测”。\n"
                        "如果用户只是问候或闲聊，请简短自然回复，不要强行生成交接文档。\n"
                        "正式任务结果请写成可交接的 Markdown 产物。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        api_url = self.completion_url(config.base_url)
        req = request.Request(
            api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise RuntimeError(f"Model provider returned HTTP {exc.code} from {api_url}: {detail[:200]}") from exc
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model provider returned non-JSON response from {api_url}: {raw_body[:200]}") from exc
        return body["choices"][0]["message"]["content"]

DeepSeekWorkerBackend = OpenAICompatibleWorkerBackend


@dataclass
class ClaudeCliWorkerBackend:
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

        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(profile_dir)

        args = [
            *self.claude_command,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--cwd",
            str(workspace_dir),
            "--model",
            config.model,
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
            raise RuntimeError(f"claude CLI exited {process.returncode}: {stderr_text}")

        last_result_text = ""
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "result":
                last_result_text = event.get("result", "")
        return last_result_text


class WorkerRuntime:
    def __init__(
        self,
        config: WorkerConfig,
        bus: TaskBus,
        artifacts: ArtifactStore,
        backend: FakeWorkerBackend | SubprocessWorkerBackend | OpenAICompatibleWorkerBackend | ClaudeCliWorkerBackend,
    ):
        self.config = config
        self.bus = bus
        self.artifacts = artifacts
        self.backend = backend

    async def execute(self, task_id: str) -> TaskRecord:
        task = self.bus.get_task(task_id)
        if task.worker_id != self.config.worker_id:
            raise ValueError(f"task {task_id} does not belong to worker {self.config.worker_id}")

        self.bus.mark_running(task_id)
        try:
            result_text = await self.backend.run(task.prompt, self.config)
        except Exception as exc:
            return self.bus.mark_failed(task_id, str(exc))

        artifact_id = self.artifacts.write_text(
            self.config.worker_id,
            task_id,
            "result.md",
            result_text,
        )
        return self.bus.mark_succeeded(task_id, result_text, [artifact_id])


def default_mock_command() -> list[str]:
    return [sys.executable, str(Path(__file__).resolve().parents[1] / "mock_worker.py")]
