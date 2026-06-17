from pathlib import Path


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def write_text(self, worker_id: str, task_id: str, filename: str, content: str) -> str:
        artifact_path = self.root / worker_id / task_id / filename
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(content, encoding="utf-8")
        return f"{worker_id}/{task_id}/{filename}"

    def read_text(self, artifact_id: str) -> str:
        return (self.root / artifact_id).read_text(encoding="utf-8")

    def resolve_path(self, artifact_id: str) -> str:
        return str((self.root / artifact_id).resolve())

    def list_task_artifacts(self, worker_id: str, task_id: str) -> list[str]:
        task_dir = self.root / worker_id / task_id
        if not task_dir.exists():
            return []
        return [f"{worker_id}/{task_id}/{path.name}" for path in sorted(task_dir.iterdir()) if path.is_file()]
