from __future__ import annotations

from pathlib import Path

from agent_factory.core.resource_manager import ResourceManager


def evaluate_run_quality(manager: ResourceManager, workspace_root: str | Path, run_id: str) -> dict:
    workspace_root = Path(workspace_root)
    steps = []
    passed = 0
    failed = 0

    for step in manager.list_step_runs(run_id):
        output_texts = []
        checks = []
        for output_path in step["outputs"]:
            resolved = workspace_root / output_path.replace("{run_id}", run_id)
            exists = resolved.is_file()
            content = resolved.read_text(encoding="utf-8", errors="replace") if exists else ""
            output_texts.append(content)
            status = "passed" if exists and content.strip() else "failed"
            checks.append(
                {
                    "type": "output_exists",
                    "status": status,
                    "path": resolved.relative_to(workspace_root).as_posix(),
                }
            )
            if status == "passed":
                passed += 1
            else:
                failed += 1

        combined = "\n".join(output_texts)
        for item in step["self_check"]:
            term = _extract_required_term(item)
            status = "passed" if term and term in combined else "failed"
            checks.append(
                {
                    "type": "self_check_term",
                    "status": status,
                    "text": item,
                    "term": term,
                }
            )
            if status == "passed":
                passed += 1
            else:
                failed += 1

        step_passed = sum(1 for check in checks if check["status"] == "passed")
        step_failed = sum(1 for check in checks if check["status"] == "failed")
        steps.append(
            {
                "step_id": step["step_id"],
                "agent_id": step["agent_id"],
                "status": step["status"],
                "summary": {
                    "passed": step_passed,
                    "failed": step_failed,
                    "total": step_passed + step_failed,
                },
                "checks": checks,
            }
        )

    total = passed + failed
    score = round((passed / total) * 100) if total else 100
    return {
        "run_id": run_id,
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": total,
            "score": score,
            "status": "passed" if failed == 0 else "failed",
        },
        "steps": steps,
    }


def _extract_required_term(text: str) -> str:
    for marker in ("必须包含", "必须列出", "包含"):
        if marker in text:
            return text.split(marker, 1)[1].strip(" ：:。.")
    return text.strip()
