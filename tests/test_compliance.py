import textwrap
import json

import marvisctl
from agent_factory.core.compliance import (
    ComplianceSuite,
    compare_compliance_baseline,
    list_compliance_baselines,
    list_compliance_reports,
    read_compliance_report,
    write_compliance_baseline,
)
from agent_factory.core.pipeline_executor import StepExecutionContext


def test_compliance_quick_suite_runs_taskbook_and_asserts_outputs(tmp_path):
    suite_root = _write_suite(tmp_path)

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is True
    assert result.errors == []
    assert result.cases[0]["name"] == "legacy-login"
    assert result.cases[0]["status"] == "passed"
    assert result.cases[0]["errors"] == []


def test_compliance_quick_suite_writes_report(tmp_path):
    suite_root = _write_suite(tmp_path)
    report_dir = tmp_path / "reports"

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace", report_dir=report_dir)

    report_path = __import__("pathlib").Path(result.report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result.success is True
    assert report_path.exists()
    assert report["success"] is True
    assert report["mode"] == "quick"
    assert report["cases"][0]["name"] == "legacy-login"


def test_compliance_report_helpers_list_and_read_reports(tmp_path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    report = report_dir / "compliance-quick-20260101T000000Z-passed.json"
    report.write_text('{"success": true, "cases": []}', encoding="utf-8")

    listed = list_compliance_reports(report_dir)
    read = read_compliance_report(report_dir, report.name)

    assert listed[0]["filename"] == report.name
    assert read["report"]["success"] is True


def test_compliance_baseline_helpers_detect_regression(tmp_path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    baseline_report = report_dir / "compliance-model-20260101T000000Z-passed.json"
    baseline_report.write_text(
        json.dumps({"success": True, "mode": "model", "cases": [{"name": "legacy-login", "status": "passed"}]}),
        encoding="utf-8",
    )
    current_report = report_dir / "compliance-model-20260102T000000Z-failed.json"
    current_report.write_text(
        json.dumps({"success": False, "mode": "model", "cases": [{"name": "legacy-login", "status": "failed"}]}),
        encoding="utf-8",
    )

    baseline_path = write_compliance_baseline(report_dir, "moon-bridge-deepseek", baseline_report.name)
    comparison = compare_compliance_baseline(report_dir, "moon-bridge-deepseek", current_report.name)

    assert baseline_path.exists()
    assert list_compliance_baselines(report_dir)[0]["name"] == "moon-bridge-deepseek"
    assert comparison["passed"] is False
    assert comparison["regressions"] == [{"name": "legacy-login", "baseline": "passed", "current": "failed"}]


def test_compliance_baseline_rejects_unsafe_names(tmp_path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    report = report_dir / "compliance-model-20260101T000000Z-passed.json"
    report.write_text(json.dumps({"success": True, "mode": "model", "cases": []}), encoding="utf-8")

    try:
        write_compliance_baseline(report_dir, "../escape", report.name)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("unsafe baseline name should be rejected")


def test_compliance_quick_suite_reports_failed_assertion(tmp_path):
    suite_root = _write_suite(tmp_path, expected_output="artifacts/runs/{run_id}/missing.md")

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is False
    assert "missing expected output" in result.errors[0]
    assert result.cases[0]["status"] == "failed"


def test_compliance_supports_expected_failure_cases(tmp_path):
    suite_root = _write_suite(tmp_path, expected_output="artifacts/runs/{run_id}/missing.md", expected_result="failed")

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is True
    assert result.errors == []
    assert result.cases[0]["status"] == "passed"
    assert result.cases[0]["expected_result"] == "failed"
    assert "missing expected output" in result.cases[0]["errors"][0]


def test_marvisctl_runs_quick_compliance_suite(tmp_path, capsys):
    suite_root = _write_suite(tmp_path)
    report_dir = tmp_path / "reports"

    assert marvisctl.main(["compliance", "run", "--suite", str(suite_root), "--mode", "quick", "--report-dir", str(report_dir)]) == 0

    output = capsys.readouterr().out
    assert "compliance ok (quick)" in output
    assert "report:" in output
    assert list(report_dir.glob("compliance-quick-*-passed.json"))


def test_marvisctl_runs_model_compliance_suite_with_configured_backend(tmp_path, capsys):
    suite_root = _write_suite(tmp_path, output_contains=["model compliance output"])
    config_path = tmp_path / "factory_config.json"
    config_path.write_text(
        textwrap.dedent(
            """
            {
              "server": {"host": "127.0.0.1", "port": 8846, "token": "local-token"},
              "runtime_mode": "mock-inline",
              "workers": [
                {
                  "worker_id": "niuma-1",
                  "display_name": "niuma-1",
                  "provider": "test",
                  "model": "fake-model",
                  "api_key_env": "NIUMA_1_API_KEY",
                  "profile_dir": "profiles/niuma-1",
                  "workspace_dir": "workspaces/niuma-1",
                  "skills_dir": "skills/niuma-1",
                  "backend_type": "fake",
                  "backend_options": {"response_text": "model compliance output"}
                }
              ]
            }
            """
        ),
        encoding="utf-8",
    )

    assert marvisctl.main(
        ["compliance", "run", "--suite", str(suite_root), "--mode", "model", "--config", str(config_path)]
    ) == 0

    assert "compliance ok (model)" in capsys.readouterr().out


def test_repository_compliance_suite_runs(tmp_path):
    suite_root = __import__("pathlib").Path(__file__).parents[1] / "tests" / "compliance"

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is True
    assert {case["name"] for case in result.cases} == {
        "forbidden-write-contract",
        "legacy-login",
        "legacy-modernization",
        "missing-input-contract",
        "restart-recovery-contract",
        "correction-loop-contract",
    }
    assert all(case["status"] == "passed" for case in result.cases)


def test_compliance_suite_can_run_with_custom_step_runner(tmp_path):
    suite_root = _write_suite(tmp_path)
    calls = []

    def runner(context: StepExecutionContext) -> dict[str, str]:
        calls.append(context.step.step_id)
        return {output_path: "real worker output" for output_path in context.output_paths}

    result = ComplianceSuite(suite_root).run_with_runner(tmp_path / "workspace", runner)

    assert result.success is True
    assert calls == ["reverse-login"]


def test_compliance_asserts_output_content_contains(tmp_path):
    suite_root = _write_suite(tmp_path, output_contains=["real worker output"])

    def runner(context: StepExecutionContext) -> dict[str, str]:
        return {output_path: "wrong content" for output_path in context.output_paths}

    result = ComplianceSuite(suite_root).run_with_runner(tmp_path / "workspace", runner)

    assert result.success is False
    assert "missing expected content" in result.errors[0]


def test_compliance_asserts_dependency_order(tmp_path):
    suite_root = _write_two_step_suite(tmp_path, depends_after={"write-requirements": ["reverse-login"]})

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is True


def test_compliance_asserts_forbidden_paths_are_unchanged(tmp_path):
    suite_root = _write_suite(tmp_path, forbidden_modified=["shared/references/login.jsp"])
    workspace = tmp_path / "workspace"
    protected = workspace / "legacy-login" / "shared" / "references" / "login.jsp"
    protected.parent.mkdir(parents=True)
    protected.write_text("original", encoding="utf-8")

    def runner(context: StepExecutionContext) -> dict[str, str]:
        protected.write_text("modified", encoding="utf-8")
        return {output_path: "real worker output" for output_path in context.output_paths}

    result = ComplianceSuite(suite_root).run_with_runner(workspace, runner)

    assert result.success is False
    assert "forbidden path modified" in result.errors[0]


def test_compliance_installs_case_fixtures_before_run(tmp_path):
    suite_root = _write_suite(tmp_path, input_exists=["shared/references/login.jsp"])
    fixture = suite_root / "fixtures" / "legacy-login" / "shared" / "references" / "login.jsp"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("<form>login</form>", encoding="utf-8")

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is True
    installed = tmp_path / "workspace" / "legacy-login" / "shared" / "references" / "login.jsp"
    assert installed.read_text(encoding="utf-8") == "<form>login</form>"


def test_compliance_can_assert_restart_recovery_contract(tmp_path):
    suite_root = _write_suite(
        tmp_path,
        expected_output=None,
        expected_run_status="blocked",
        expected_step_status="blocked",
        reconcile_on_startup=True,
    )

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is True
    assert result.cases[0]["status"] == "passed"


def test_compliance_can_assert_correction_loop_contract(tmp_path):
    suite_root = _write_correction_suite(tmp_path)

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is True
    assert result.cases[0]["status"] == "passed"


def _write_suite(
    tmp_path,
    expected_output="artifacts/runs/{run_id}/reverse-login/function-list.md",
    output_contains=None,
    forbidden_modified=None,
    input_exists=None,
    reconcile_on_startup=False,
    expected_run_status="succeeded",
    expected_step_status="succeeded",
    expected_result="passed",
):
    suite_root = tmp_path / "suite"
    (suite_root / "taskbooks").mkdir(parents=True)
    (suite_root / "expected").mkdir(parents=True)
    (suite_root / "taskbooks" / "legacy-login.yml").write_text(
        textwrap.dedent(
            """
            title: 登录模块改造
            objective: 输出登录模块逆向文档
            steps:
              - id: reverse-login
                agent: niuma-1
                objective: 逆向登录模块
                outputs:
                  - path: artifacts/runs/{run_id}/reverse-login/function-list.md
            """
        ),
        encoding="utf-8",
    )
    contains_yaml = ""
    if output_contains:
        output_path = expected_output or "artifacts/runs/{run_id}/reverse-login/function-list.md"
        contains_yaml = "\n                  output_contains:\n" + "".join(
            f"                    - path: {output_path}\n                      text: {text}\n" for text in output_contains
        )
    output_exists_yaml = ""
    if expected_output:
        output_exists_yaml = f"\n                  output_exists:\n                    - {expected_output}"
    forbidden_yaml = ""
    if forbidden_modified:
        forbidden_yaml = "\n              forbidden_modified:\n" + "".join(f"                - {path}\n" for path in forbidden_modified)
    input_exists_yaml = ""
    if input_exists:
        input_exists_yaml = "\n              input_exists:\n" + "".join(f"                - {path}\n" for path in input_exists)
    reconcile_yaml = ""
    if reconcile_on_startup:
        reconcile_yaml = """
              reconcile_on_startup:
                initial_run_status: running
                initial_step_status: running
                agent_status: idle
                summary:
                  released_leases: 1
                  blocked_runs: 1
                  blocked_steps: 1
                  reset_agents: 1
"""
    (suite_root / "expected" / "legacy-login.assert.yml").write_text(
        textwrap.dedent(
            f"""
            assert:
              expected_result: {expected_result}
              run_status: {expected_run_status}
{input_exists_yaml}
{reconcile_yaml}
              steps:
                reverse-login:
                  status: {expected_step_status}
{output_exists_yaml}{contains_yaml}{forbidden_yaml}
            """
        ),
        encoding="utf-8",
    )
    return suite_root


def _write_two_step_suite(tmp_path, depends_after=None):
    suite_root = tmp_path / "suite"
    (suite_root / "taskbooks").mkdir(parents=True)
    (suite_root / "expected").mkdir(parents=True)
    (suite_root / "taskbooks" / "legacy-login.yml").write_text(
        textwrap.dedent(
            """
            title: 登录模块改造
            objective: 输出登录模块逆向文档和需求文档
            steps:
              - id: reverse-login
                agent: niuma-1
                objective: 逆向登录模块
                outputs:
                  - path: artifacts/runs/{run_id}/reverse-login/function-list.md
              - id: write-requirements
                agent: niuma-2
                depends_on:
                  - reverse-login
                objective: 编写需求文档
                inputs:
                  - path: artifacts/runs/{run_id}/reverse-login/function-list.md
                outputs:
                  - path: artifacts/runs/{run_id}/write-requirements/requirements.md
            """
        ),
        encoding="utf-8",
    )
    depends_yaml = ""
    if depends_after:
        depends_yaml = "\n              depends_after:\n" + "".join(
            f"                {step_id}: [{', '.join(dependencies)}]\n" for step_id, dependencies in depends_after.items()
        )
    (suite_root / "expected" / "legacy-login.assert.yml").write_text(
        textwrap.dedent(
            f"""
            assert:
              run_status: succeeded
              steps:
                reverse-login:
                  status: succeeded
                write-requirements:
                  status: succeeded{depends_yaml}
            """
        ),
        encoding="utf-8",
    )
    return suite_root


def _write_correction_suite(tmp_path):
    suite_root = tmp_path / "suite"
    (suite_root / "taskbooks").mkdir(parents=True)
    (suite_root / "expected").mkdir(parents=True)
    (suite_root / "taskbooks" / "legacy-login.yml").write_text(
        textwrap.dedent(
            """
            title: correction loop
            objective: verify correction rerun and downstream recovery
            steps:
              - id: reverse-login
                agent: niuma-1
                objective: fail-before-correction reverse login
                outputs:
                  - path: artifacts/runs/{run_id}/reverse-login/function-list.md
              - id: write-requirements
                agent: niuma-2
                depends_on:
                  - reverse-login
                objective: write requirements
                inputs:
                  - path: artifacts/runs/{run_id}/reverse-login/function-list.md
                outputs:
                  - path: artifacts/runs/{run_id}/write-requirements/requirements.md
            """
        ),
        encoding="utf-8",
    )
    (suite_root / "expected" / "legacy-login.assert.yml").write_text(
        textwrap.dedent(
            """
            assert:
              run_status: succeeded
              correction_loop:
                step_id: reverse-login
                text: parse JSP login guards
              steps:
                reverse-login:
                  status: succeeded
                  output_exists:
                    - artifacts/runs/{run_id}/reverse-login/function-list.md
                write-requirements:
                  status: succeeded
                  output_exists:
                    - artifacts/runs/{run_id}/write-requirements/requirements.md
                  depends_after:
                    - reverse-login
            """
        ),
        encoding="utf-8",
    )
    return suite_root
