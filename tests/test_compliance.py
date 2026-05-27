import textwrap

import marvisctl
from agent_factory.core.compliance import ComplianceSuite
from agent_factory.core.pipeline_executor import StepExecutionContext


def test_compliance_quick_suite_runs_taskbook_and_asserts_outputs(tmp_path):
    suite_root = _write_suite(tmp_path)

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is True
    assert result.errors == []
    assert result.cases[0]["name"] == "legacy-login"
    assert result.cases[0]["status"] == "passed"
    assert result.cases[0]["errors"] == []


def test_compliance_quick_suite_reports_failed_assertion(tmp_path):
    suite_root = _write_suite(tmp_path, expected_output="artifacts/runs/{run_id}/missing.md")

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is False
    assert "missing expected output" in result.errors[0]
    assert result.cases[0]["status"] == "failed"


def test_marvisctl_runs_quick_compliance_suite(tmp_path, capsys):
    suite_root = _write_suite(tmp_path)

    assert marvisctl.main(["compliance", "run", "--suite", str(suite_root), "--mode", "quick"]) == 0

    assert "compliance ok" in capsys.readouterr().out


def test_repository_compliance_suite_runs(tmp_path):
    suite_root = __import__("pathlib").Path(__file__).parents[1] / "tests" / "compliance"

    result = ComplianceSuite(suite_root).run_quick(tmp_path / "workspace")

    assert result.success is True
    assert result.cases[0]["status"] == "passed"


def test_compliance_suite_can_run_with_custom_step_runner(tmp_path):
    suite_root = _write_suite(tmp_path)
    calls = []

    def runner(context: StepExecutionContext) -> dict[str, str]:
        calls.append(context.step.step_id)
        return {output_path: "real worker output" for output_path in context.output_paths}

    result = ComplianceSuite(suite_root).run_with_runner(tmp_path / "workspace", runner)

    assert result.success is True
    assert calls == ["reverse-login"]


def _write_suite(tmp_path, expected_output="artifacts/runs/{run_id}/reverse-login/function-list.md"):
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
    (suite_root / "expected" / "legacy-login.assert.yml").write_text(
        textwrap.dedent(
            f"""
            assert:
              run_status: succeeded
              steps:
                reverse-login:
                  status: succeeded
                  output_exists:
                    - {expected_output}
            """
        ),
        encoding="utf-8",
    )
    return suite_root
