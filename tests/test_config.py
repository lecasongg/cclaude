import json
import os

import pytest

from agent_factory.core.config import ConfigError, apply_runtime_config, load_factory_config, load_runtime_config, save_runtime_config
from agent_factory.core.models import WorkerConfig


def test_worker_config_defaults_backend_type_to_claude_cli():
    config = WorkerConfig(
        worker_id="niuma-1",
        display_name="牛马1",
        provider="anthropic",
        model="claude-sonnet-4-6",
        api_key_env="ANTHROPIC_API_KEY",
        profile_dir="profiles/niuma-1",
        workspace_dir="workspaces/niuma-1",
        skills_dir="skills/niuma-1",
    )
    assert config.backend_type == "claude_cli"
    assert config.backend_options == {}
    assert config.backend_configured is True


def test_load_factory_config_preserves_worker_isolation(tmp_path):
    config_path = tmp_path / "factory.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [
                    {
                        "worker_id": "niuma-1",
                        "display_name": "牛马1",
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "api_key_env": "NIUMA_1_API_KEY",
                        "profile_dir": "profiles/niuma-1",
                        "workspace_dir": "workspaces/niuma-1",
                        "skills_dir": "skills/niuma-1",
                    },
                    {
                        "worker_id": "niuma-2",
                        "display_name": "牛马2",
                        "provider": "anthropic",
                        "model": "claude-sonnet-4-6",
                        "api_key_env": "NIUMA_2_API_KEY",
                        "profile_dir": "profiles/niuma-2",
                        "workspace_dir": "workspaces/niuma-2",
                        "skills_dir": "skills/niuma-2",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    config = load_factory_config(config_path)

    assert config.server.host == "127.0.0.1"
    assert config.server.port == 8846
    assert config.server.token == "local-token"
    assert [worker.worker_id for worker in config.workers] == ["niuma-1", "niuma-2"]
    assert config.workers[0].api_key_env == "NIUMA_1_API_KEY"
    assert config.workers[1].api_key_env == "NIUMA_2_API_KEY"
    assert config.workers[0].profile_dir != config.workers[1].profile_dir
    assert config.workers[0].workspace_dir != config.workers[1].workspace_dir
    assert config.workers[0].skills_dir != config.workers[1].skills_dir
    assert config.workers[0].backend_type == "claude_cli"
    assert config.workers[0].backend_options == {}
    assert config.workers[0].backend_configured is False


def test_load_factory_config_preserves_explicit_worker_backend_type(tmp_path):
    config_path = tmp_path / "factory.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [
                    {
                        "worker_id": "niuma-1",
                        "display_name": "牛马1",
                        "provider": "anthropic",
                        "model": "claude-sonnet-4-6",
                        "api_key_env": "ANTHROPIC_API_KEY",
                        "profile_dir": "profiles/niuma-1",
                        "workspace_dir": "workspaces/niuma-1",
                        "skills_dir": "skills/niuma-1",
                        "backend_type": "claude_cli",
                        "backend_options": {"timeout_seconds": 1800},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    config = load_factory_config(config_path)

    assert config.workers[0].backend_type == "claude_cli"
    assert config.workers[0].backend_options == {"timeout_seconds": 1800}
    assert config.workers[0].backend_configured is True


def test_load_factory_config_rejects_duplicate_worker_ids(tmp_path):
    config_path = tmp_path / "factory.json"
    worker = {
        "worker_id": "niuma-1",
        "display_name": "牛马1",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "api_key_env": "NIUMA_1_API_KEY",
        "profile_dir": "profiles/niuma-1",
        "workspace_dir": "workspaces/niuma-1",
        "skills_dir": "skills/niuma-1",
    }
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [worker, worker],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="duplicate worker_id: niuma-1"):
        load_factory_config(config_path)


def test_runtime_config_round_trips_unicode_and_keys(tmp_path):
    runtime_path = tmp_path / "runtime_config.json"
    data = {
        "model_base_url": "http://smarthse.51vip.biz:53001/v1",
        "workers": {
            "niuma-1": {
                "provider": "smarthse",
                "model": "deepseek-v4-pro",
                "role": "JSP 逆向工位",
                "api_key": "sk-secret",
            }
        },
    }

    save_runtime_config(runtime_path, data)

    assert load_runtime_config(runtime_path) == data


def test_config_loaders_accept_utf8_bom_files(tmp_path):
    config_path = tmp_path / "factory.json"
    config_path.write_text(
        "\ufeff"
        + json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runtime_path = tmp_path / "runtime_config.json"
    runtime_path.write_text("\ufeff{\"workers\": {}}", encoding="utf-8")

    assert load_factory_config(config_path).server.port == 8846
    assert load_runtime_config(runtime_path) == {"workers": {}}


def test_apply_runtime_config_updates_workers_and_environment(tmp_path, monkeypatch):
    config_path = tmp_path / "factory.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [
                    {
                        "worker_id": "niuma-1",
                        "display_name": "牛马1",
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "api_key_env": "NIUMA_1_API_KEY",
                        "profile_dir": "profiles/niuma-1",
                        "workspace_dir": "workspaces/niuma-1",
                        "skills_dir": "skills/niuma-1",
                    },
                    {
                        "worker_id": "niuma-2",
                        "display_name": "牛马2",
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "api_key_env": "NIUMA_2_API_KEY",
                        "profile_dir": "profiles/niuma-2",
                        "workspace_dir": "workspaces/niuma-2",
                        "skills_dir": "skills/niuma-2",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("NIUMA_1_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_URL", raising=False)
    config = load_factory_config(config_path)

    apply_runtime_config(
        config,
        {
            "workers": {
                "niuma-1": {
                    "provider": "relay-a",
                    "model": "claude-opus-4-7",
                    "role": "Opus 文档工位",
                    "base_url": "http://relay-a.local/v1",
                    "api_key": "sk-secret",
                },
                "niuma-2": {
                    "provider": "relay-b",
                    "model": "deepseek-v4-pro",
                    "base_url": "http://relay-b.local/v1",
                },
            },
        },
    )

    assert config.workers[0].provider == "relay-a"
    assert config.workers[0].model == "claude-opus-4-7"
    assert config.workers[0].role == "Opus 文档工位"
    assert config.workers[0].base_url == "http://relay-a.local/v1"
    assert config.workers[1].base_url == "http://relay-b.local/v1"
    assert os.environ["NIUMA_1_API_KEY"] == "sk-secret"
    assert "OPENAI_COMPATIBLE_API_URL" not in os.environ


def test_apply_runtime_config_adds_persisted_dynamic_workers(tmp_path):
    config_path = tmp_path / "factory.json"
    config_path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "workers": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config = load_factory_config(config_path)

    apply_runtime_config(
        config,
        {
            "workers": {
                "niuma-3": {
                    "display_name": "牛马3",
                    "provider": "test",
                    "model": "fake-model",
                    "api_key_env": "NIUMA_3_API_KEY",
                    "profile_dir": "profiles/niuma-3",
                    "workspace_dir": "workspaces/niuma-3",
                    "skills_dir": "skills/niuma-3",
                    "role": "测试工位",
                    "backend_type": "fake",
                    "backend_options": {"response_text": "done"},
                    "enabled": True,
                }
            }
        },
    )

    assert len(config.workers) == 1
    assert config.workers[0].worker_id == "niuma-3"
    assert config.workers[0].display_name == "牛马3"
    assert config.workers[0].backend_type == "fake"
