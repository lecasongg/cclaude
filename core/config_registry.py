from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class ConfigRegistry:
    defaults: dict[str, Any]
    templates: dict[str, dict[str, Any]]
    agents: dict[str, dict[str, Any]]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ConfigRegistry":
        if "workers" in data and "agents" not in data:
            return cls.from_factory_config(data)
        return cls(
            defaults=copy.deepcopy(data.get("defaults", {})),
            templates=copy.deepcopy(data.get("templates", {})),
            agents=_normalize_agents(data.get("agents", {})),
        )

    @classmethod
    def from_factory_config(cls, data: dict[str, Any]) -> "ConfigRegistry":
        defaults = {
            "backend_type": data.get("runtime_mode", ""),
        }
        agents: dict[str, dict[str, Any]] = {}
        for worker in data.get("workers", []):
            if not isinstance(worker, dict):
                raise ConfigRegistryError("worker entries must be objects")
            agent_id = worker.get("worker_id")
            if not agent_id:
                raise ConfigRegistryError("worker entry missing worker_id")
            if agent_id in agents:
                raise ConfigRegistryError(f"duplicate agent_id: {agent_id}")
            agent_data = copy.deepcopy(worker)
            agent_data.pop("worker_id", None)
            agents[agent_id] = agent_data
        return cls(defaults=defaults, templates={}, agents=agents)

    def render_agent(self, agent_id: str, run_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        if agent_id not in self.agents:
            raise ConfigRegistryError(f"unknown agent_id: {agent_id}")

        agent_data = copy.deepcopy(self.agents[agent_id])
        rendered = copy.deepcopy(self.defaults)

        template_name = agent_data.pop("extends", "")
        if template_name:
            template = self.templates.get(template_name)
            if template is None:
                raise ConfigRegistryError(f"unknown template: {template_name}")
            rendered = _deep_merge(rendered, template)

        rendered = _deep_merge(rendered, agent_data)
        if run_overrides:
            rendered = _deep_merge(rendered, run_overrides)
        rendered["worker_id"] = agent_id
        return rendered

    def validate(self) -> None:
        for agent_id in self.agents:
            rendered = self.render_agent(agent_id)
            for field_name in ("display_name", "provider", "model", "api_key_env"):
                if not rendered.get(field_name):
                    raise ConfigRegistryError(f"missing required field {field_name} for agent {agent_id}")


def load_config_registry(path: str | Path) -> ConfigRegistry:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    registry = ConfigRegistry.from_mapping(data)
    registry.validate()
    return registry


def _normalize_agents(raw_agents: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw_agents, dict):
        return copy.deepcopy(raw_agents)
    if not isinstance(raw_agents, list):
        raise ConfigRegistryError("agents must be an object or list")

    agents: dict[str, dict[str, Any]] = {}
    for raw_agent in raw_agents:
        if not isinstance(raw_agent, dict):
            raise ConfigRegistryError("agent entries must be objects")
        agent_id = raw_agent.get("agent_id") or raw_agent.get("worker_id")
        if not agent_id:
            raise ConfigRegistryError("agent entry missing agent_id")
        if agent_id in agents:
            raise ConfigRegistryError(f"duplicate agent_id: {agent_id}")
        agent_data = copy.deepcopy(raw_agent)
        agent_data.pop("agent_id", None)
        agent_data.pop("worker_id", None)
        agents[agent_id] = agent_data
    return agents


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged
