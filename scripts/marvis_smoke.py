from __future__ import annotations

import json
import shutil
import sys
import tempfile
import types
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if "agent_factory" not in sys.modules:
    pkg = types.ModuleType("agent_factory")
    pkg.__path__ = [str(ROOT)]
    sys.modules["agent_factory"] = pkg

from agent_factory.worker_server import build_app


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="marvis-smoke-"))
    try:
        config_path = workspace / "factory_config.json"
        taskbook_path = workspace / "taskbooks" / "legacy-smoke.yml"
        source_path = workspace / "source" / "login.jsp"
        _write_config(config_path)
        _write_taskbook(taskbook_path)
        source_path.parent.mkdir(parents=True)
        source_path.write_text("<form id='login'>login</form>\nselect * from users where id = ?", encoding="utf-8")

        client = TestClient(build_app(config_path))
        headers = {"x-hermes-token": "local-token"}
        health = _ok(client.get("/api/workers/health-summary", headers=headers))
        _assert(health["summary"]["total"] == 2, "expected two smoke workers")

        run_body = _ok(
            client.post(
                "/api/runs",
                headers=headers,
                json={"taskbook_path": str(taskbook_path), "source_path": str(source_path)},
            )
        )
        run_id = run_body["run"]["run_id"]
        _assert(run_body["run"]["status"] == "succeeded", "run did not succeed")
        _assert([step["status"] for step in run_body["steps"]] == ["succeeded", "succeeded", "succeeded"], "steps did not all succeed")

        artifacts = _ok(client.get(f"/api/runs/{run_id}/artifacts", headers=headers))["artifacts"]
        _assert(len(artifacts) == 3, "expected three step artifacts")
        _assert({artifact["step_id"] for artifact in artifacts} == {"reverse-module", "write-requirements", "write-test-plan"}, "artifact step index mismatch")

        quality = _ok(client.get(f"/api/runs/{run_id}/quality", headers=headers))
        _assert(quality["summary"]["status"] == "passed", "quality gate failed")

        manifest = _ok(client.get(f"/api/runs/{run_id}/manifest", headers=headers))
        _assert(manifest["manifest_version"] == 1, "manifest version mismatch")
        _assert(manifest["quality"]["summary"]["status"] == "passed", "manifest quality failed")

        rerun_body = _ok(
            client.post(
                f"/api/runs/{run_id}/steps/write-requirements/rerun",
                headers=headers,
                json={"correction": "tighten acceptance criteria"},
            )
        )
        _assert(rerun_body["run"]["status"] == "succeeded", "rerun did not succeed")
        _assert(any(event["type"] == "correction_added" for event in rerun_body["events"]), "rerun correction event missing")

        print(json.dumps({"status": "ok", "run_id": run_id, "workspace": str(workspace)}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        print(f"workspace preserved: {workspace}", file=sys.stderr)
        return 1
    finally:
        if "--keep" not in sys.argv:
            shutil.rmtree(workspace, ignore_errors=True)


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
                "runtime_mode": "mock-inline",
                "workers": [
                    _worker("niuma-1"),
                    _worker("niuma-2"),
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _worker(worker_id: str) -> dict:
    return {
        "worker_id": worker_id,
        "display_name": worker_id,
        "provider": "test",
        "model": "fake-model",
        "api_key_env": f"{worker_id.upper().replace('-', '_')}_API_KEY",
        "profile_dir": f"profiles/{worker_id}",
        "workspace_dir": f"workspaces/{worker_id}",
        "skills_dir": f"skills/{worker_id}",
        "backend_type": "fake",
        "backend_options": {
            "response_text": (
                "function inventory\nentry file\nSQL dependency\nmain flow\n"
                "exception flow\nacceptance criteria\nhappy path case\n"
                "exception case\ntest data\npass/fail decision\npending questions"
            )
        },
    }


def _write_taskbook(path: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        """
title: smoke legacy modernization
objective: verify old-system modernization pipeline
steps:
  - id: reverse-module
    agent: niuma-1
    objective: reverse legacy module
    outputs:
      - path: artifacts/runs/{run_id}/reverse-module/function-list.md
    self_check:
      - function inventory
      - entry file
      - SQL dependency
  - id: write-requirements
    agent: niuma-2
    depends_on:
      - reverse-module
    objective: write requirements
    inputs:
      - path: artifacts/runs/{run_id}/reverse-module/function-list.md
    outputs:
      - path: artifacts/runs/{run_id}/write-requirements/requirements.md
    self_check:
      - main flow
      - exception flow
      - acceptance criteria
  - id: write-test-plan
    agent: niuma-2
    depends_on:
      - write-requirements
    objective: write test plan
    inputs:
      - path: artifacts/runs/{run_id}/write-requirements/requirements.md
    outputs:
      - path: artifacts/runs/{run_id}/write-test-plan/test-plan.md
    self_check:
      - happy path case
      - exception case
      - test data
      - pass/fail decision
""",
        encoding="utf-8",
    )


def _ok(response):
    if response.status_code != 200:
        raise AssertionError(f"{response.status_code}: {response.text}")
    return response.json()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
