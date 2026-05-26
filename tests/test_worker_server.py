import json

from fastapi.testclient import TestClient

from agent_factory.worker_server import build_app


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
