from pathlib import Path

from agent_factory.core.artifacts import ArtifactStore


def test_artifact_store_writes_worker_task_scoped_text(tmp_path):
    store = ArtifactStore(tmp_path)

    artifact_id = store.write_text("niuma-1", "task-1", "requirements_inventory.md", "# 需求清单")

    assert artifact_id == "niuma-1/task-1/requirements_inventory.md"
    assert store.read_text(artifact_id) == "# 需求清单"
    assert (tmp_path / "niuma-1" / "task-1" / "requirements_inventory.md").read_text(encoding="utf-8") == "# 需求清单"


def test_artifact_store_lists_task_artifacts_without_cross_worker_leakage(tmp_path):
    store = ArtifactStore(tmp_path)

    first = store.write_text("niuma-1", "task-1", "inventory.md", "one")
    store.write_text("niuma-2", "task-1", "inventory.md", "two")

    assert store.list_task_artifacts("niuma-1", "task-1") == [first]


def test_artifact_store_resolves_absolute_path(tmp_path):
    store = ArtifactStore(tmp_path)
    aid = store.write_text("niuma-1", "task-abc", "result.md", "hello")

    resolved = store.resolve_path(aid)

    assert Path(resolved).is_absolute()
    assert Path(resolved).read_text(encoding="utf-8") == "hello"
