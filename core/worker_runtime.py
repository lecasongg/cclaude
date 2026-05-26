import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib import error, request

from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.models import TaskRecord, WorkerConfig
from agent_factory.core.skill_linking import link_worker_skills
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

    def resolved_claude_command(self) -> list[str]:
        if self.claude_command != ["claude"]:
            return self.claude_command
        candidates = ["claude.cmd", "claude.exe", "claude"] if os.name == "nt" else ["claude"]
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return [resolved]
        return self.claude_command

    async def run(self, prompt: str, config: WorkerConfig) -> str:
        profile_dir = Path(config.profile_dir).resolve()
        workspace_dir = Path(config.workspace_dir).resolve()
        skills_dir = Path(config.skills_dir).resolve()
        artifacts_dir = workspace_dir.parent.parent / "artifacts"

        profile_dir.mkdir(parents=True, exist_ok=True)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        link_worker_skills(skills_dir, workspace_dir)

        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(profile_dir)
        api_key = os.environ.get(config.api_key_env)
        if config.base_url and not api_key:
            raise RuntimeError(f"missing API key environment variable: {config.api_key_env}")
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        if config.base_url:
            env["ANTHROPIC_BASE_URL"] = config.base_url

        args = [
            *self.resolved_claude_command(),
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--add-dir",
            str(artifacts_dir),
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

        stdout_text = stdout.decode("utf-8", errors="replace")
        events_path = workspace_dir / ".hermes" / "last-events.jsonl"
        event_lines = _write_event_stream(stdout_text, events_path)

        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            if not detail:
                detail = _event_error_detail(event_lines)
            raise RuntimeError(f"claude CLI exited {process.returncode}: {detail[:400]}")

        last_result_text = None
        for line in event_lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "result":
                last_result_text = event.get("result", "")
        if last_result_text is None:
            stdout_tail = stdout_text[-1000:].strip()
            raise RuntimeError(f"claude CLI missing result event in stream-json output: {stdout_tail}")
        return last_result_text


@dataclass
class CodexCliWorkerBackend:
    codex_command: list[str] = field(default_factory=lambda: ["codex"])
    timeout_seconds: int = 1800
    extra_args: list[str] = field(default_factory=list)

    def resolved_codex_command(self) -> list[str]:
        if self.codex_command != ["codex"]:
            return self.codex_command
        candidates = ["codex.cmd", "codex.exe", "codex"] if os.name == "nt" else ["codex"]
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return [resolved]
        return self.codex_command

    async def run(self, prompt: str, config: WorkerConfig) -> str:
        profile_dir = Path(config.profile_dir).resolve()
        workspace_dir = Path(config.workspace_dir).resolve()
        skills_dir = Path(config.skills_dir).resolve()
        artifacts_dir = workspace_dir.parent.parent / "artifacts"

        profile_dir.mkdir(parents=True, exist_ok=True)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        hermes_dir = workspace_dir / ".hermes"
        hermes_dir.mkdir(parents=True, exist_ok=True)
        output_path = hermes_dir / "last-message.md"

        env = os.environ.copy()
        env["CODEX_HOME"] = str(profile_dir)
        api_key = os.environ.get(config.api_key_env)
        if config.base_url and not api_key:
            raise RuntimeError(f"missing API key environment variable: {config.api_key_env}")
        if api_key:
            env["OPENAI_API_KEY"] = api_key
        if config.base_url:
            _write_codex_profile_config(profile_dir, config)

        args = [
            *self.resolved_codex_command(),
            "exec",
            "--json",
            "--cd",
            str(workspace_dir),
            "--add-dir",
            str(artifacts_dir),
            "-m",
            config.model,
            "-o",
            str(output_path),
            *self.extra_args,
            prompt,
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
            raise RuntimeError(f"codex CLI exceeded {self.timeout_seconds}s, killed")

        stdout_text = stdout.decode("utf-8", errors="replace")
        events_path = workspace_dir / ".hermes" / "last-events.jsonl"
        event_lines = _write_event_stream(stdout_text, events_path)

        if process.returncode != 0:
            detail = _codex_event_error_detail(event_lines) or stderr.decode("utf-8", errors="replace").strip() or stdout_text[-1000:].strip()
            raise RuntimeError(f"codex CLI exited {process.returncode}: {detail[:400]}")

        if output_path.exists():
            return output_path.read_text(encoding="utf-8").strip()
        return stdout_text.strip()


class WorkerRuntime:
    def __init__(
        self,
        config: WorkerConfig,
        bus: TaskBus,
        artifacts: ArtifactStore,
        backend: FakeWorkerBackend | SubprocessWorkerBackend | OpenAICompatibleWorkerBackend | ClaudeCliWorkerBackend | CodexCliWorkerBackend,
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


def _write_event_stream(stdout_text: str, events_path: Path) -> list[str]:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    event_lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
    with events_path.open("w", encoding="utf-8") as events_file:
        for line in event_lines:
            events_file.write(line + "\n")
    return event_lines


def _event_error_detail(event_lines: list[str]) -> str:
    for line in reversed(event_lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        result = event.get("result")
        if isinstance(result, str) and result.strip():
            return result.strip()
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
        detail = "\n".join(part for part in text_parts if part).strip()
        if detail:
            return detail
    return ""


def _write_codex_profile_config(profile_dir: Path, config: WorkerConfig) -> None:
    config_path = profile_dir / "config.toml"
    catalog_path = profile_dir / "models_catalog.json"
    content = "\n".join(
        [
            'model_provider = "niuma_relay"',
            f'model = "{_toml_string(config.model)}"',
            "",
            "[model_providers.niuma_relay]",
            'name = "niuma_relay"',
            f'base_url = "{_toml_string(config.base_url)}"',
            'wire_api = "responses"',
            "requires_openai_auth = true",
            "",
        ]
    )
    config_path.write_text(content, encoding="utf-8")
    catalog = {
        "models": [
            {
                "slug": config.model,
                "display_name": config.model,
                "description": "Niuma relay model exposed through a Responses-compatible bridge.",
                "default_reasoning_level": "medium",
                "supported_reasoning_levels": [
                    {"effort": "low", "description": "Fast responses with lighter reasoning"},
                    {"effort": "medium", "description": "Balanced speed and reasoning"},
                    {"effort": "high", "description": "Greater reasoning depth"},
                ],
                "wire_api": "responses",
                "supported_in_api": True,
            }
        ]
    }
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


def _toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _codex_event_error_detail(event_lines: list[str]) -> str:
    for line in reversed(event_lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = event.get("message")
        if event.get("type") == "error" and isinstance(message, str) and message.strip():
            return message.strip()
        error_data = event.get("error")
        if isinstance(error_data, dict):
            message = error_data.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
    return ""
