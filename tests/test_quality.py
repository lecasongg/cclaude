from agent_factory.core.quality import evaluate_run_quality
from agent_factory.core.resource_manager import ResourceManager


def test_evaluate_run_quality_checks_outputs_and_self_check_terms(tmp_path):
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="牛马1")
    run_id = manager.create_pipeline_run("登录模块改造")
    manager.create_step_run(
        run_id,
        "reverse-login",
        "niuma-1",
        "逆向登录模块",
        outputs=["artifacts/runs/{run_id}/reverse-login/function-list.md"],
        self_check=["必须包含功能清单", "必须包含异常流程"],
    )
    manager.update_step_status(run_id, "reverse-login", "succeeded")
    output = tmp_path / "artifacts" / "runs" / run_id / "reverse-login" / "function-list.md"
    output.parent.mkdir(parents=True)
    output.write_text("功能清单：登录、登出", encoding="utf-8")

    report = evaluate_run_quality(manager, tmp_path, run_id)

    assert report["run_id"] == run_id
    checks = report["steps"][0]["checks"]
    assert checks[0]["status"] == "passed"
    assert checks[0]["type"] == "output_exists"
    assert checks[1]["status"] == "passed"
    assert checks[1]["type"] == "self_check_term"
    assert checks[1]["term"] == "功能清单"
    assert checks[2]["status"] == "failed"
    assert checks[2]["term"] == "异常流程"
    assert checks[0]["path"] == f"artifacts/runs/{run_id}/reverse-login/function-list.md"
    assert report["steps"][0]["summary"] == {"passed": 2, "failed": 1, "total": 3}
    assert report["summary"] == {"passed": 2, "failed": 1, "total": 3, "score": 67, "status": "failed"}


def test_evaluate_run_quality_reports_missing_output(tmp_path):
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="牛马1")
    run_id = manager.create_pipeline_run("登录模块改造")
    manager.create_step_run(
        run_id,
        "reverse-login",
        "niuma-1",
        "逆向登录模块",
        outputs=["artifacts/runs/{run_id}/reverse-login/function-list.md"],
    )

    report = evaluate_run_quality(manager, tmp_path, run_id)

    assert report["summary"] == {"passed": 0, "failed": 1, "total": 1, "score": 0, "status": "failed"}
    assert report["steps"][0]["checks"][0]["status"] == "failed"


def test_evaluate_run_quality_scores_empty_checklist_as_passed(tmp_path):
    manager = ResourceManager(tmp_path / "marvis.db")
    manager.register_agent("niuma-1", display_name="鐗涢┈1")
    run_id = manager.create_pipeline_run("empty")

    report = evaluate_run_quality(manager, tmp_path, run_id)

    assert report["summary"] == {"passed": 0, "failed": 0, "total": 0, "score": 100, "status": "passed"}
    assert report["steps"] == []
