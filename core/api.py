import asyncio
import os
from dataclasses import asdict

from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

from agent_factory.core.config import save_runtime_config
from agent_factory.core.event_log import EventLog
from agent_factory.core.models import TaskRecord, WorkerConfig
from agent_factory.core.pipeline_executor import PipelineExecutor
from agent_factory.core.resource_manager import ResourceManager, ResourceManagerError
from agent_factory.core.security import SecurityGate
from agent_factory.core.supervisor import HermesSupervisor
from agent_factory.core.task_bus import TaskBus
from agent_factory.core.taskbook import TaskBookError, load_taskbook
from agent_factory.core.worker_runtime import ClaudeCliWorkerBackend, CodexCliWorkerBackend, FakeWorkerBackend, OpenAICompatibleWorkerBackend, SubprocessWorkerBackend
from agent_factory.core.worker_step_runner import WorkerRuntimeStepRunner


class DelegateRequest(BaseModel):
    worker_id: str
    prompt: str


class ChainRequest(BaseModel):
    source_worker: str
    target_worker: str
    prompt: str
    next_instruction: str


class FilePathRequest(BaseModel):
    path: str


class TaskBookRunRequest(BaseModel):
    taskbook_path: str


REQUIRED_DOCUMENT_WORKER_ID = "niuma-1"
TASK_MANUAL = "task_manual"
CONVERSION_RULES = "conversion_rules"
DOCUMENT_LABELS = {
    TASK_MANUAL: "任务手册",
    CONVERSION_RULES: "转换规则",
}
DOCUMENT_ORDER = [TASK_MANUAL, CONVERSION_RULES]


class WorkerConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    role: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    persist: bool = True


def task_to_dict(task: TaskRecord) -> dict:
    data = asdict(task)
    data["status"] = task.status.value
    return data


def backend_type_name(backend) -> str:
    if isinstance(backend, ClaudeCliWorkerBackend):
        return "claude_cli"
    if isinstance(backend, CodexCliWorkerBackend):
        return "codex_cli"
    if isinstance(backend, OpenAICompatibleWorkerBackend):
        return "openai_compatible"
    if isinstance(backend, SubprocessWorkerBackend):
        return "subprocess"
    if isinstance(backend, FakeWorkerBackend):
        return "fake"
    return backend.__class__.__name__


def build_file_prompt(files: list[tuple[str, str, int]]) -> dict:
    prompt_parts = [
        "请基于以下源文件内容进行老系统逆向分析。",
        "注意：已读取附件内容，不要再尝试访问本地路径；下面就是文件正文。",
    ]
    file_summaries = []
    for path, content, size in files:
        file_summaries.append({"path": path, "size": size})
        prompt_parts.append(f"\n文件：{path}\n下面就是文件正文：\n```\n{content}\n```")
    return {"files": file_summaries, "prompt": "\n".join(prompt_parts)}


def read_local_files(path_text: str) -> dict:
    path = Path(path_text).expanduser()
    if not path.exists():
        raise HTTPException(status_code=404, detail="path not found")
    paths = [path]
    if path.is_dir():
        paths = [candidate for candidate in sorted(path.rglob("*")) if candidate.is_file()]
    files = [(str(candidate), candidate.read_text(encoding="utf-8", errors="replace"), candidate.stat().st_size) for candidate in paths]
    return build_file_prompt(files)


def document_status(documents: dict) -> dict:
    status = {}
    for kind in DOCUMENT_ORDER:
        document = documents.get(kind) or {}
        status[kind] = {
            "installed": bool(document.get("content")),
            "filename": document.get("filename", ""),
            "size": document.get("size", 0),
        }
    return status


def create_app(
    supervisor: HermesSupervisor,
    bus: TaskBus,
    workers: list[WorkerConfig],
    security: SecurityGate,
    runtime_config_path: Path | None = None,
    runtime_config: dict | None = None,
    resource_manager: ResourceManager | None = None,
    event_log: EventLog | None = None,
    pipeline_workspace_root: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Hermes Local Agent Factory")
    runtime_data = runtime_config if runtime_config is not None else {}

    def authorize(token: str | None) -> None:
        if not security.is_authorized(token):
            raise HTTPException(status_code=401, detail="unauthorized")

    def worker_runtime_entry(worker_id: str) -> dict:
        return runtime_data.setdefault("workers", {}).setdefault(worker_id, {})

    def worker_documents(worker_id: str) -> dict:
        return worker_runtime_entry(worker_id).setdefault("installed_documents", {})

    def build_installed_document_prompt(worker_id: str) -> str:
        if worker_id != REQUIRED_DOCUMENT_WORKER_ID:
            return ""
        documents = worker_documents(worker_id)
        missing = [DOCUMENT_LABELS[kind] for kind in DOCUMENT_ORDER if not documents.get(kind, {}).get("content")]
        if missing:
            raise HTTPException(status_code=400, detail=f"niuma-1 缺少已安装文档：{', '.join(missing)}")
        parts = []
        for kind in DOCUMENT_ORDER:
            document = documents[kind]
            parts.append(f"## {DOCUMENT_LABELS[kind]}\n{document['content']}")
        return "\n\n".join(parts)

    def compose_worker_prompt(worker_id: str, prompt: str) -> str:
        prefix = build_installed_document_prompt(worker_id)
        return f"{prefix}\n\n## 用户任务\n{prompt}" if prefix else prompt

    async def save_installed_document(worker_id: str, kind: str, uploaded: UploadFile) -> dict:
        if kind not in DOCUMENT_LABELS:
            raise HTTPException(status_code=404, detail="document kind not found")
        if not any(worker.worker_id == worker_id for worker in workers):
            raise HTTPException(status_code=404, detail="worker not found")
        content = await uploaded.read()
        documents = worker_documents(worker_id)
        documents[kind] = {
            "filename": uploaded.filename,
            "size": len(content),
            "content": content.decode("utf-8", errors="replace"),
        }
        if runtime_config_path:
            save_runtime_config(runtime_config_path, runtime_data)
        return {"worker_id": worker_id, "installed_documents": document_status(documents)}

    def worker_to_dict(worker: WorkerConfig) -> dict:
        state = bus.worker_state(worker.worker_id)
        runtime = supervisor.runtimes.get(worker.worker_id)
        base_url = worker.base_url
        if not base_url and runtime:
            base_url = getattr(runtime.backend, "api_url", "")
        return {
            "worker_id": worker.worker_id,
            "display_name": worker.display_name,
            "status": state.status,
            "queue_depth": state.queue_depth,
            "current_task_id": state.current_task_id,
            "provider": worker.provider,
            "model": worker.model,
            "backend_type": backend_type_name(runtime.backend) if runtime else getattr(worker, "backend_type", ""),
            "api_key_env": worker.api_key_env,
            "api_key_configured": bool(os.environ.get(worker.api_key_env)),
            "base_url": base_url,
            "role": worker.role,
            "workspace_dir": worker.workspace_dir,
            "skills_dir": worker.skills_dir,
            "installed_documents": document_status(worker_documents(worker.worker_id)),
        }

    def ensure_workers_registered_for_pipeline() -> None:
        if resource_manager is None:
            return
        for worker in workers:
            resource_manager.register_agent(worker.worker_id, display_name=worker.display_name)

    @app.get("/api/health")
    async def health(x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        return {
            "status": "ok",
            "workers_total": len(workers),
            "workers_with_api_key": sum(1 for worker in workers if os.environ.get(worker.api_key_env)),
            "tasks_total": len(bus.list_tasks()),
            "runtime_config_persistence": runtime_config_path is not None,
        }

    @app.get("/api/workers")
    async def list_workers(x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        return {"workers": [worker_to_dict(worker) for worker in workers]}

    @app.post("/api/file-context/path")
    async def file_context_from_path(request: FilePathRequest, x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        return read_local_files(request.path)

    @app.post("/api/file-context/upload")
    async def file_context_from_upload(files: list[UploadFile] = File(...), x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        loaded_files = []
        for uploaded in files:
            content = await uploaded.read()
            loaded_files.append((uploaded.filename, content.decode("utf-8", errors="replace"), len(content)))
        return build_file_prompt(loaded_files)

    @app.get("/api/workers/{worker_id}/installed-documents")
    async def get_installed_documents(worker_id: str, x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        if not any(worker.worker_id == worker_id for worker in workers):
            raise HTTPException(status_code=404, detail="worker not found")
        return {"worker_id": worker_id, "installed_documents": document_status(worker_documents(worker_id))}

    @app.post("/api/workers/{worker_id}/installed-documents/{kind}")
    async def install_document(worker_id: str, kind: str, file: UploadFile = File(...), x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        return await save_installed_document(worker_id, kind, file)

    @app.patch("/api/workers/{worker_id}/config")
    async def update_worker_config(worker_id: str, request: WorkerConfigUpdate, x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        worker = next((candidate for candidate in workers if candidate.worker_id == worker_id), None)
        if worker is None:
            raise HTTPException(status_code=404, detail="worker not found")
        if request.provider is not None:
            worker.provider = request.provider
        if request.model is not None:
            worker.model = request.model
        if request.role is not None:
            worker.role = request.role
        if request.api_key:
            os.environ[worker.api_key_env] = request.api_key
        if request.base_url is not None:
            worker.base_url = request.base_url
        if request.persist and runtime_config_path:
            saved_workers = runtime_data.setdefault("workers", {})
            saved_worker = saved_workers.setdefault(worker_id, {})
            if request.provider is not None:
                saved_worker["provider"] = request.provider
            if request.model is not None:
                saved_worker["model"] = request.model
            if request.role is not None:
                saved_worker["role"] = request.role
            if request.base_url is not None:
                saved_worker["base_url"] = request.base_url
            if request.api_key:
                saved_worker["api_key"] = request.api_key
            save_runtime_config(runtime_config_path, runtime_data)
        notice = "配置已保存，重启后仍会生效。" if request.persist and runtime_config_path else "配置已更新，仅对当前 Worker Server 进程生效。"
        return {"worker": worker_to_dict(worker), "notice": notice}

    @app.get("/api/tasks")
    async def list_tasks(x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        return {"tasks": [task_to_dict(task) for task in bus.list_tasks()]}

    @app.get("/api/runs")
    async def list_runs(x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        if resource_manager is None:
            return {"runs": []}
        return {"runs": resource_manager.list_pipeline_runs()}

    @app.post("/api/runs")
    async def start_run(request: TaskBookRunRequest, x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        if resource_manager is None or event_log is None:
            raise HTTPException(status_code=400, detail="pipeline runtime not configured")
        try:
            taskbook = load_taskbook(request.taskbook_path)
        except (TaskBookError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        ensure_workers_registered_for_pipeline()
        executor = PipelineExecutor(
            resource_manager=resource_manager,
            event_log=event_log,
            workspace_root=pipeline_workspace_root or Path.cwd(),
            step_runner=WorkerRuntimeStepRunner(supervisor.runtimes),
        )
        run_id = await asyncio.to_thread(executor.run, taskbook)
        return {
            "run": resource_manager.get_pipeline_run(run_id),
            "steps": resource_manager.list_step_runs(run_id),
        }

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str, x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        if resource_manager is None:
            raise HTTPException(status_code=404, detail="run not found")
        try:
            return {
                "run": resource_manager.get_pipeline_run(run_id),
                "steps": resource_manager.list_step_runs(run_id),
            }
        except ResourceManagerError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.get("/api/runs/{run_id}/events")
    async def get_run_events(run_id: str, x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        if event_log is None:
            return {"events": []}
        return {"events": event_log.read_events(run_id)}

    @app.get("/api/artifacts/{worker_id}/{task_id}/{filename}")
    async def read_artifact(worker_id: str, task_id: str, filename: str, x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        artifact_id = f"{worker_id}/{task_id}/{filename}"
        return {"artifact_id": artifact_id, "content": supervisor.artifacts.read_text(artifact_id)}

    @app.post("/api/delegate")
    async def delegate(request: DelegateRequest, x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        task = await supervisor.delegate(request.worker_id, compose_worker_prompt(request.worker_id, request.prompt))
        return task_to_dict(task)

    @app.post("/api/chain")
    async def chain(request: ChainRequest, x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        source, target = await supervisor.chain(
            request.source_worker,
            request.target_worker,
            compose_worker_prompt(request.source_worker, request.prompt),
            request.next_instruction,
            handoff_user_prompt=request.prompt,
        )
        return {"source": task_to_dict(source), "target": task_to_dict(target)}

    return app
