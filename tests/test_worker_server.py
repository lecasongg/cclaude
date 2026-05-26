import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from agent_factory.worker_server import build_app, resolve_config_path


def test_resolve_config_path_prefers_factory_config(tmp_path):
    legacy = tmp_path / "config.example.json"
    factory_example = tmp_path / "factory_config.example.json"
    factory = tmp_path / "factory_config.json"
    legacy.write_text("{}", encoding="utf-8")
    factory_example.write_text("{}", encoding="utf-8")
    factory.write_text("{}", encoding="utf-8")

    assert resolve_config_path(tmp_path) == factory


def test_resolve_config_path_uses_factory_example_before_legacy(tmp_path):
    legacy = tmp_path / "config.example.json"
    factory_example = tmp_path / "factory_config.example.json"
    legacy.write_text("{}", encoding="utf-8")
    factory_example.write_text("{}", encoding="utf-8")

    assert resolve_config_path(tmp_path) == factory_example


def test_resolve_config_path_honors_override(tmp_path):
    override = tmp_path / "custom.json"

    assert resolve_config_path(tmp_path, str(override)) == override


def test_worker_server_build_app_uses_worker_backend_type(tmp_path):
    config_path = tmp_path / "factory.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "runtime_mode": "mock-inline",
                "workers": [
                    {
                        "worker_id": "legacy",
                        "display_name": "legacy",
                        "provider": "test",
                        "model": "test-model",
                        "api_key_env": "LEGACY_API_KEY",
                        "profile_dir": "p",
                        "workspace_dir": "w",
                        "skills_dir": "s",
                        "backend_type": "fake",
                        "backend_options": {"response_text": "factory backend"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(build_app(config_path))

    response = client.post(
        "/api/delegate",
        headers={"x-hermes-token": "local-token"},
        json={"worker_id": "legacy", "prompt": "hello"},
    )

    assert response.status_code == 200
    assert response.json()["result_text"] == "factory backend"


def test_worker_server_build_app_maps_legacy_openai_runtime_mode(tmp_path):
    config_path = tmp_path / "factory.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "runtime_mode": "openai-compatible",
                "workers": [
                    {
                        "worker_id": "legacy",
                        "display_name": "legacy",
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "api_key_env": "LEGACY_API_KEY",
                        "profile_dir": "p",
                        "workspace_dir": "w",
                        "skills_dir": "s",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(build_app(config_path))

    response = client.get("/api/workers", headers={"x-hermes-token": "local-token"})

    assert response.status_code == 200
    assert response.json()["workers"][0]["base_url"] == "https://api.deepseek.com/chat/completions"


def test_worker_server_build_app_from_factory_config_example(tmp_path):
    repo_root = Path(__file__).parents[1]
    shutil.copy(repo_root / "factory_config.example.json", tmp_path / "factory_config.example.json")
    shutil.copytree(repo_root / "web", tmp_path / "web")

    client = TestClient(build_app(tmp_path / "factory_config.example.json"))

    response = client.get("/api/workers", headers={"x-hermes-token": "local-token"})

    assert response.status_code == 200
    workers = response.json()["workers"]
    assert workers[0]["worker_id"] == "niuma-1"
    assert workers[0]["backend_type"] == "claude_cli"
