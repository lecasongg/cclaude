import textwrap
from pathlib import Path

import pytest

from agent_factory.core.taskbook import TaskBookError, load_taskbook


def test_load_taskbook_builds_execution_order(tmp_path):
    taskbook_path = tmp_path / "login.yml"
    taskbook_path.write_text(
        textwrap.dedent(
            """
            taskbook_version: 1
            title: 登录模块改造
            objective: 输出登录模块逆向文档和测试计划
            agents:
              - id: niuma-1
                role: reverse-engineering
              - id: niuma-2
                role: requirements-writer
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
            constraints:
              - 不得修改 shared/references 下的源文件
            """
        ),
        encoding="utf-8",
    )

    taskbook = load_taskbook(taskbook_path)

    assert taskbook.title == "登录模块改造"
    assert taskbook.execution_order() == ["reverse-login", "write-requirements"]
    assert taskbook.step("write-requirements").depends_on == ["reverse-login"]


def test_taskbook_rejects_duplicate_step_ids(tmp_path):
    taskbook_path = tmp_path / "duplicate.yml"
    taskbook_path.write_text(
        textwrap.dedent(
            """
            title: 重复步骤
            objective: 测试
            steps:
              - id: reverse-login
                agent: niuma-1
                objective: 逆向
                outputs:
                  - path: artifacts/runs/{run_id}/reverse-login/a.md
              - id: reverse-login
                agent: niuma-2
                objective: 写文档
                outputs:
                  - path: artifacts/runs/{run_id}/reverse-login/b.md
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(TaskBookError, match="duplicate step id: reverse-login"):
        load_taskbook(taskbook_path)


def test_taskbook_rejects_unknown_dependency(tmp_path):
    taskbook_path = tmp_path / "unknown-dependency.yml"
    taskbook_path.write_text(
        textwrap.dedent(
            """
            title: 未知依赖
            objective: 测试
            steps:
              - id: write-requirements
                agent: niuma-2
                depends_on:
                  - reverse-login
                objective: 写文档
                outputs:
                  - path: artifacts/runs/{run_id}/write-requirements/requirements.md
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(TaskBookError, match="unknown dependency reverse-login for step write-requirements"):
        load_taskbook(taskbook_path)


def test_taskbook_rejects_cycle(tmp_path):
    taskbook_path = tmp_path / "cycle.yml"
    taskbook_path.write_text(
        textwrap.dedent(
            """
            title: 循环依赖
            objective: 测试
            steps:
              - id: a
                agent: niuma-1
                depends_on: [b]
                objective: A
                outputs:
                  - path: artifacts/runs/{run_id}/a/a.md
              - id: b
                agent: niuma-2
                depends_on: [a]
                objective: B
                outputs:
                  - path: artifacts/runs/{run_id}/b/b.md
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(TaskBookError, match="cycle detected"):
        load_taskbook(taskbook_path)


def test_taskbook_rejects_output_paths_outside_artifacts(tmp_path):
    taskbook_path = tmp_path / "bad-output.yml"
    taskbook_path.write_text(
        textwrap.dedent(
            """
            title: 越权输出
            objective: 测试
            steps:
              - id: reverse-login
                agent: niuma-1
                objective: 逆向
                outputs:
                  - path: ../shared/references/login.jsp
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(TaskBookError, match="invalid output path for step reverse-login"):
        load_taskbook(taskbook_path)


def test_repository_sample_taskbooks_are_valid():
    taskbook_dir = Path(__file__).parents[1] / "taskbooks"
    sample_paths = sorted(taskbook_dir.glob("*.yml"))

    assert sample_paths
    for path in sample_paths:
        load_taskbook(path)
