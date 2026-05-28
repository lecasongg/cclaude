import os
from dataclasses import dataclass
from json import dumps, loads
from pathlib import Path

from agent_factory.core.models import WorkerConfig


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    token: str


@dataclass(frozen=True)
class FactoryConfig:
    server: ServerConfig
    workers: list[WorkerConfig]
    runtime_mode: str = "mock-subprocess"


def load_factory_config(path: str | Path) -> FactoryConfig:
    data = loads(Path(path).read_text(encoding="utf-8"))
    server_data = data["server"]
    workers = [_load_worker_config(worker_data) for worker_data in data["workers"]]
    seen: set[str] = set()
    for worker in workers:
        if worker.worker_id in seen:
            raise ConfigError(f"duplicate worker_id: {worker.worker_id}")
        seen.add(worker.worker_id)
    return FactoryConfig(
        server=ServerConfig(
            host=server_data["host"],
            port=server_data["port"],
            token=server_data["token"],
        ),
        workers=workers,
        runtime_mode=data.get("runtime_mode", "mock-subprocess"),
    )


def _load_worker_config(worker_data: dict) -> WorkerConfig:
    worker = WorkerConfig(**worker_data)
    worker.backend_configured = "backend_type" in worker_data
    return worker


def load_runtime_config(path: str | Path) -> dict:
    runtime_path = Path(path)
    if not runtime_path.exists():
        return {}
    return loads(runtime_path.read_text(encoding="utf-8"))


def save_runtime_config(path: str | Path, data: dict) -> None:
    runtime_path = Path(path)
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = runtime_path.with_suffix(f"{runtime_path.suffix}.tmp")
    temp_path.write_text(dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(runtime_path)


def apply_runtime_config(config: FactoryConfig, runtime_data: dict) -> None:
    worker_data_by_id = runtime_data.get("workers", {})
    existing_worker_ids = {worker.worker_id for worker in config.workers}
    for worker_id, worker_data in worker_data_by_id.items():
        if worker_id in existing_worker_ids or worker_data.get("enabled") is False:
            continue
        config.workers.append(
            WorkerConfig(
                worker_id=worker_id,
                display_name=worker_data.get("display_name", worker_id),
                provider=worker_data.get("provider", "test"),
                model=worker_data.get("model", "fake-model"),
                api_key_env=worker_data.get("api_key_env", f"{worker_id.upper().replace('-', '_')}_API_KEY"),
                profile_dir=worker_data.get("profile_dir", f"profiles/{worker_id}"),
                workspace_dir=worker_data.get("workspace_dir", f"workspaces/{worker_id}"),
                skills_dir=worker_data.get("skills_dir", f"skills/{worker_id}"),
                base_url=worker_data.get("base_url", ""),
                role=worker_data.get("role", "通用交付工位"),
                backend_type=worker_data.get("backend_type", "fake"),
                backend_options=worker_data.get("backend_options", {}),
                backend_configured=True,
            )
        )
    default_base_url = runtime_data.get("model_base_url", "")
    for worker in config.workers:
        worker_data = worker_data_by_id.get(worker.worker_id, {})
        if "provider" in worker_data:
            worker.provider = worker_data["provider"]
        if "model" in worker_data:
            worker.model = worker_data["model"]
        if "base_url" in worker_data:
            worker.base_url = worker_data["base_url"]
        elif default_base_url:
            worker.base_url = default_base_url
        if "role" in worker_data:
            worker.role = worker_data["role"]
        if worker_data.get("api_key"):
            os.environ[worker.api_key_env] = worker_data["api_key"]
