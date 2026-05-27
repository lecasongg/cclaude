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
    assert {case["name"] for case in result.cases} == {"legacy-login", "legacy-modernization"}
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


def _write_suite(
    tmp_path,
    expected_output="artifacts/runs/{run_id}/reverse-login/function-list.md",
    output_contains=None,
    forbidden_modified=None,
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
        contains_yaml = "\n                  output_contains:\n" + "".join(
            f"                    - path: {expected_output}\n                      text: {text}\n" for text in output_contains
        )
    forbidden_yaml = ""
    if forbidden_modified:
        forbidden_yaml = "\n              forbidden_modified:\n" + "".join(f"                - {path}\n" for path in forbidden_modified)
    (suite_root / "expected" / "legacy-login.assert.yml").write_text(
        textwrap.dedent(
            f"""
            assert:
              run_status: succeeded
              steps:
                reverse-login:
                  status: succeeded
                  output_exists:
                    - {expected_output}{contains_yaml}{forbidden_yaml}
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
