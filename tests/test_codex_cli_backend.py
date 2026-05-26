import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent_factory.core.models import WorkerConfig
from agent_factory.core.worker_runtime import CodexCliWorkerBackend


def make_config(tmp_path):
    return WorkerConfig(
        worker_id="niuma-1",
        display_name="niuma-1",
        provider="openai",
        model="gpt-5-codex",
        api_key_env="NIUMA_1_API_KEY",
        profile_dir=str(tmp_path / "profiles/niuma-1"),
        workspace_dir=str(tmp_path / "workspaces/niuma-1"),
        skills_dir=str(tmp_path / "skills/niuma-1"),
    )


def test_codex_cli_default_extra_args_match_current_exec_cli():
    backend = CodexCliWorkerBackend(extra_args=["-s", "workspace-write", "--skip-git-repo-check"])

    assert "-a" not in backend.extra_args
    assert "--ask-for-approval" not in backend.extra_args


@pytest.mark.asyncio
async def test_codex_cli_backend_invokes_codex_exec_with_isolated_home_and_workspace(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    captured = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env", {})
        captured["cwd"] = kwargs.get("cwd")

        output_path = Path(args[args.index("-o") + 1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("created hello.md", encoding="utf-8")

        process = AsyncMock()
        process.communicate.return_value = (b'{"type":"done"}\n', b"")
        process.returncode = 0
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await CodexCliWorkerBackend(codex_command=["codex"]).run("write hello", config)

    assert result == "created hello.md"
    assert Path(captured["args"][0]).stem == "codex"
    assert captured["args"][1] == "exec"
    assert "--json" in captured["args"]
    assert "--cd" in captured["args"]
    assert str((tmp_path / "workspaces/niuma-1").resolve()) in captured["args"]
    assert "--add-dir" in captured["args"]
    assert str((tmp_path / "artifacts").resolve()) in captured["args"]
    assert "-o" in captured["args"]
    assert captured["env"]["CODEX_HOME"] == str((tmp_path / "profiles/niuma-1").resolve())
    assert captured["cwd"] == str((tmp_path / "workspaces/niuma-1").resolve())


@pytest.mark.asyncio
async def test_codex_cli_backend_raises_on_nonzero_exit(tmp_path, monkeypatch):
    config = make_config(tmp_path)

    async def fake_create_subprocess_exec(*args, **kwargs):
        process = AsyncMock()
        process.communicate.return_value = (b"", b"auth failed")
        process.returncode = 1
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    with pytest.raises(RuntimeError, match="codex CLI exited 1: auth failed"):
        await CodexCliWorkerBackend().run("hi", config)


@pytest.mark.asyncio
async def test_codex_cli_backend_kills_on_timeout(tmp_path, monkeypatch):
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

    with pytest.raises(RuntimeError, match="exceeded"):
        await CodexCliWorkerBackend(timeout_seconds=1).run("hi", config)

    assert killed["called"]
