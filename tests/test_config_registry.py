import json

import pytest

from agent_factory.core.config_registry import ConfigRegistry, ConfigRegistryError, load_config_registry


def test_config_registry_renders_agent_from_defaults_template_and_run_override():
    registry = ConfigRegistry.from_mapping(
        {
            "defaults": {
                "backend_type": "codex_cli",
                "base_url": "http://127.0.0.1:38440/v1",
                "backend_options": {
                    "timeout_seconds": 1800,
                    "extra_args": ["--skip-git-repo-check"],
                },
            },
            "templates": {
                "reverse-engineer": {
                    "provider": "openai",
                    "model": "deepseek-v4-pro",
                    "role": "老系统逆向分析工位",
                    "tags": ["jsp", "sql"],
                    "backend_options": {
                        "extra_args": ["--dangerously-bypass-approvals-and-sandbox"],
                    },
                }
            },
            "agents": {
                "niuma-1": {
                    "extends": "reverse-engineer",
                    "display_name": "牛马1",
                    "api_key_env": "NIUMA_1_API_KEY",
                    "workspace_dir": "agents/niuma-1/workspace",
                }
            },
        }
    )

    rendered = registry.render_agent(
        "niuma-1",
        run_overrides={"model": "deepseek-v4-pro-fast", "backend_options": {"timeout_seconds": 60}},
    )

    assert rendered["worker_id"] == "niuma-1"
    assert rendered["display_name"] == "牛马1"
    assert rendered["provider"] == "openai"
    assert rendered["model"] == "deepseek-v4-pro-fast"
    assert rendered["role"] == "老系统逆向分析工位"
    assert rendered["base_url"] == "http://127.0.0.1:38440/v1"
    assert rendered["backend_type"] == "codex_cli"
    assert rendered["api_key_env"] == "NIUMA_1_API_KEY"
    assert rendered["workspace_dir"] == "agents/niuma-1/workspace"
    assert rendered["tags"] == ["jsp", "sql"]
    assert rendered["backend_options"] == {
        "timeout_seconds": 60,
        "extra_args": ["--dangerously-bypass-approvals-and-sandbox"],
    }


def test_config_registry_rejects_unknown_template():
    registry = ConfigRegistry.from_mapping(
        {
            "templates": {},
            "agents": {
                "niuma-1": {
                    "extends": "missing-template",
                    "display_name": "牛马1",
                    "api_key_env": "NIUMA_1_API_KEY",
                }
            },
        }
    )

    with pytest.raises(ConfigRegistryError, match="unknown template: missing-template"):
        registry.render_agent("niuma-1")


def test_config_registry_validates_required_agent_fields():
    registry = ConfigRegistry.from_mapping(
        {
            "templates": {
                "writer": {
                    "provider": "openai",
                    "model": "deepseek-v4-pro",
                }
            },
            "agents": {
                "niuma-2": {
                    "extends": "writer",
                    "display_name": "牛马2",
                }
            },
        }
    )

    with pytest.raises(ConfigRegistryError, match="missing required field api_key_env for agent niuma-2"):
        registry.validate()


def test_config_registry_rejects_duplicate_agent_ids_in_list_form():
    with pytest.raises(ConfigRegistryError, match="duplicate agent_id: niuma-1"):
        ConfigRegistry.from_mapping(
            {
                "agents": [
                    {"agent_id": "niuma-1", "display_name": "牛马1", "api_key_env": "NIUMA_1_API_KEY"},
                    {"agent_id": "niuma-1", "display_name": "牛马甲", "api_key_env": "NIUMA_A_API_KEY"},
                ]
            }
        )


def test_load_config_registry_reads_json_file(tmp_path):
    config_path = tmp_path / "agents.json"
    config_path.write_text(
        json.dumps(
            {
                "defaults": {"backend_type": "codex_cli"},
                "agents": {
                    "niuma-1": {
                        "display_name": "牛马1",
                        "provider": "openai",
                        "model": "deepseek-v4-pro",
                        "api_key_env": "NIUMA_1_API_KEY",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    registry = load_config_registry(config_path)

    assert registry.render_agent("niuma-1")["backend_type"] == "codex_cli"
