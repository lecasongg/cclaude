from agent_factory.core.models import WorkerConfig
from agent_factory.core.worker_runtime import (
    ClaudeCliWorkerBackend,
    FakeWorkerBackend,
    OpenAICompatibleWorkerBackend,
    SubprocessWorkerBackend,
)


class BackendError(ValueError):
    pass


def build_backend(config: WorkerConfig):
    backend_type = config.backend_type
    options = dict(config.backend_options)
    if backend_type == "claude_cli":
        return ClaudeCliWorkerBackend(**options)
    if backend_type == "openai_compatible":
        return OpenAICompatibleWorkerBackend(**options)
    if backend_type == "subprocess":
        return SubprocessWorkerBackend(**options)
    if backend_type == "fake":
        return FakeWorkerBackend(**options)
    raise BackendError(f"unknown backend_type: {backend_type}")
