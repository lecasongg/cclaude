import os
from pathlib import Path

import uvicorn
from fastapi.responses import FileResponse

from agent_factory.core.api import create_app
from agent_factory.core.artifacts import ArtifactStore
from agent_factory.core.backends import build_backend
from agent_factory.core.config import apply_runtime_config, load_factory_config, load_runtime_config
from agent_factory.core.event_log import EventLog
from agent_factory.core.models import WorkerConfig
from agent_factory.core.resource_manager import ResourceManager
from agent_factory.core.security import SecurityGate
from agent_factory.core.supervisor import HermesSupervisor
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.worker_runtime import WorkerRuntime, default_mock_command


def resolve_config_path(root: str | Path, override: str | None = None) -> Path:
    if override:
        return Path(override)
    root = Path(root)
    for name in ("factory_config.json", "factory_config.example.json", "config.example.json"):
        candidate = root / name
        if candidate.exists():
            return candidate
    return root / "factory_config.example.json"


def apply_legacy_runtime_backend(worker: WorkerConfig, runtime_mode: str) -> WorkerConfig:
    if worker.backend_configured:
        return worker
    worker.backend_options = {}
    if runtime_mode == "mock-inline":
        worker.backend_type = "fake"
        worker.backend_options = {"response_text": f"{worker.display_name} completed task"}
        return worker
    if runtime_mode in {"deepseek", "openai-compatible"}:
        worker.backend_type = "openai_compatible"
        return worker
    if runtime_mode == "mock-subprocess":
        worker.backend_type = "subprocess"
        worker.backend_options = {"command": default_mock_command()}
        return worker
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
    resource_manager = ResourceManager(config_path.parent / "marvis.db")
    event_log = EventLog(config_path.parent / "events")
    runtimes = {
        worker.worker_id: WorkerRuntime(
            worker,
            bus,
            artifacts,
            build_backend(apply_legacy_runtime_backend(worker, config.runtime_mode)),
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
        resource_manager=resource_manager,
        event_log=event_log,
        pipeline_workspace_root=config_path.parent,
    )

    @app.get("/")
    async def console():
        return FileResponse(config_path.parent / "web" / "console.html")

    return app


if __name__ == "__main__":
    config_path = resolve_config_path(Path(__file__).parent, os.environ.get("CCLAUDE_CONFIG_PATH"))
    config = load_factory_config(config_path)
    uvicorn.run(build_app(config_path), host=config.server.host, port=config.server.port)
