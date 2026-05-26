import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from agent_factory.core.models import WorkerConfig
from agent_factory.core.worker_runtime import ClaudeCliWorkerBackend


def make_config(tmp_path):
    return WorkerConfig(
        worker_id="niuma-1",
        display_name="牛马1",
        provider="anthropic",
        model="claude-sonnet-4-6",
        api_key_env="ANTHROPIC_API_KEY",
        profile_dir=str(tmp_path / "profiles/niuma-1"),
        workspace_dir=str(tmp_path / "workspaces/niuma-1"),
        skills_dir=str(tmp_path / "skills/niuma-1"),
    )


@pytest.mark.asyncio
async def test_claude_cli_backend_invokes_claude_with_isolated_profile_and_cwd(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    captured = {}
    result_event = json.dumps({"type": "result", "result": "任务完成"}, ensure_ascii=False)

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env", {})
        captured["cwd"] = kwargs.get("cwd")

        process = AsyncMock()
        process.communicate.return_value = (result_event.encode("utf-8"), b"")
        process.returncode = 0
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    backend = ClaudeCliWorkerBackend(claude_command=["claude"])
    result = await backend.run("分析 JSP", config)

    assert result == "任务完成"
    assert "claude" in captured["args"]
    assert "-p" in captured["args"]
    assert "分析 JSP" in captured["args"]
    assert "--cwd" in captured["args"]
    assert captured["env"]["CLAUDE_CONFIG_DIR"] == str(tmp_path / "profiles/niuma-1")
    assert captured["cwd"] == str(tmp_path / "workspaces/niuma-1")
    events_path = tmp_path / "workspaces/niuma-1/.hermes/last-events.jsonl"
    assert events_path.read_text(encoding="utf-8") == result_event + "\n"


@pytest.mark.asyncio
async def test_claude_cli_backend_raises_on_nonzero_exit(tmp_path, monkeypatch):
    config = make_config(tmp_path)

    async def fake_create_subprocess_exec(*args, **kwargs):
        process = AsyncMock()
        process.communicate.return_value = (b"", b"auth error")
        process.returncode = 1
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    backend = ClaudeCliWorkerBackend()

    with pytest.raises(RuntimeError, match="exited 1"):
        await backend.run("hi", config)


@pytest.mark.asyncio
async def test_claude_cli_backend_raises_when_result_event_missing(tmp_path, monkeypatch):
    config = make_config(tmp_path)

    async def fake_create_subprocess_exec(*args, **kwargs):
        process = AsyncMock()
        event = json.dumps({"type": "assistant", "message": {"content": "still working"}})
        process.communicate.return_value = (event.encode("utf-8"), b"")
        process.returncode = 0
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    backend = ClaudeCliWorkerBackend()

    with pytest.raises(RuntimeError, match="missing result event.*still working"):
        await backend.run("hi", config)


@pytest.mark.asyncio
async def test_claude_cli_backend_kills_on_timeout(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    killed = {"called": False}

    async def fake_create_subprocess_exec(*args, **kwargs):
        process = AsyncMock()

        async def slow_communicate():
            await asyncio.sleep(10)
            return (b"", b"")

        process.communicate = slow_communicate
        process.kill = lambda: killed.update(called=True)
        process.wait = AsyncMock()
        process.returncode = -9
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    backend = ClaudeCliWorkerBackend(timeout_seconds=1)

    with pytest.raises(RuntimeError, match="exceeded"):
        await backend.run("hi", config)

    assert killed["called"]
