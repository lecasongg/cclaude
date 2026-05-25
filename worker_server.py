from pathlib import Path

import uvicorn
from fastapi.responses import FileResponse

from agent_factory.core.api import create_app
from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.config import apply_runtime_config, load_factory_config, load_runtime_config
from agent_factory.core.security import SecurityGate
from agent_factory.core.supervisor import HermesSupervisor
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.worker_runtime import FakeWorkerBackend, OpenAICompatibleWorkerBackend, SubprocessWorkerBackend, WorkerRuntime, default_mock_command


def build_backend(runtime_mode: str, worker_display_name: str):
    if runtime_mode == "mock-inline":
        return FakeWorkerBackend(f"{worker_display_name} completed task")
    if runtime_mode == "mock-subprocess":
        return SubprocessWorkerBackend(default_mock_command())
    if runtime_mode in {"deepseek", "openai-compatible"}:
        return OpenAICompatibleWorkerBackend()
    raise ValueError(f"unsupported runtime_mode: {runtime_mode}")


def build_app(config_path: str | Path):
    config_path = Path(config_path)
    config = load_factory_config(config_path)
    runtime_config_path = config_path.parent / "runtime_config.json"
    runtime_config = load_runtime_config(runtime_config_path)
    apply_runtime_config(config, runtime_config)
    worker_ids = [worker.worker_id for worker in config.workers if worker.enabled]
    bus = TaskBus(worker_ids)
    artifacts = ArtifactStore(config_path.parent / "artifacts")
    runtimes = {
        worker.worker_id: WorkerRuntime(
            worker,
            bus,
            artifacts,
            build_backend(config.runtime_mode, worker.display_name),
        )
        for worker in config.workers
        if worker.enabled
    }
    supervisor = HermesSupervisor(bus, artifacts, runtimes)
    app = create_app(
        supervisor,
        bus,
        [worker for worker in config.workers if worker.enabled],
        SecurityGate(config.server.token),
        runtime_config_path=runtime_config_path,
        runtime_config=runtime_config,
    )

    @app.get("/")
    async def console():
        return FileResponse(config_path.parent / "web" / "console.html")

    return app


if __name__ == "__main__":
    config_path = Path(__file__).with_name("config.example.json")
    config = load_factory_config(config_path)
    uvicorn.run(build_app(config_path), host=config.server.host, port=config.server.port)
