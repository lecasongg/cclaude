import pytest

from agent_factory.core.backends import BackendError, build_backend
from agent_factory.core.models import WorkerConfig
from agent_factory.core.worker_runtime import (
    ClaudeCliWorkerBackend,
    CodexCliWorkerBackend,
    FakeWorkerBackend,
    OpenAICompatibleWorkerBackend,
    SubprocessWorkerBackend,
)


def base_config(backend_type, **opts):
    return WorkerConfig(
        worker_id="niuma-1",
        display_name="x",
        provider="x",
        model="x",
        api_key_env="X",
        profile_dir="p",
        workspace_dir="w",
        skills_dir="s",
        backend_type=backend_type,
        backend_options=opts,
    )


def test_build_backend_returns_claude_cli_by_default():
    config = base_config("claude_cli")
    assert isinstance(build_backend(config), ClaudeCliWorkerBackend)


def test_build_backend_returns_openai_compatible():
    config = base_config("openai_compatible")
    assert isinstance(build_backend(config), OpenAICompatibleWorkerBackend)


def test_build_backend_returns_codex_cli():
    config = base_config("codex_cli")
    assert isinstance(build_backend(config), CodexCliWorkerBackend)


def test_build_backend_returns_fake_with_options():
    config = base_config("fake", response_text="hi")
    backend = build_backend(config)
    assert isinstance(backend, FakeWorkerBackend)
    assert backend.response_text == "hi"


def test_build_backend_rejects_unknown_type():
    config = base_config("unknown")
    with pytest.raises(BackendError):
        build_backend(config)
