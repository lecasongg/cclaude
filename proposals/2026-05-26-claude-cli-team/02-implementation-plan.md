# 实施计划 · 任务级

> **接手者**：先读 `00-for-codex.md`。本计划按"先写失败测试 → 看红 → 写实现 → 看绿 → 单 Task 一次 commit"的节奏推进。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal**：把现有 `WorkerBackend` 体系扩展出 `ClaudeCliWorkerBackend`，并把链式派工改成文件级握手；老 backend 共存可切换。

**Architecture**：见 `01-spec.md` 第 3-4 节。新增一个 backend 实现 + 一个工厂 + 一个 `WorkerConfig` 字段 + `supervisor.chain()` 调整 + skill 软链脚本。

**Tech Stack**：Python 3.11+ / asyncio / subprocess / FastAPI / claude CLI (Node.js)

---

## 前置条件

- `claude --version` 在服务器命令行可直接执行
- 服务器持有有效的 Anthropic 凭据（API key 或 OAuth 已登录）
- pytest 39/39 当前为绿（基线）

---

## Task 0：准备分支与基线确认

**Files:** 无

- [ ] **Step 1**：从 `redesign/console-brutalist` 切新分支 `feature/claude-cli-backend`
```bash
git checkout redesign/console-brutalist
git pull
git checkout -b feature/claude-cli-backend
```

- [ ] **Step 2**：确认 baseline pytest 通过
```bash
python -m pytest tests/ -q
# Expected: 39 passed
```

- [ ] **Step 3**：确认 claude CLI 可用
```bash
claude --version
# Expected: 输出版本号，非 "command not found"
```

---

## Task 1：扩展 `WorkerConfig` 加 `backend_type` / `backend_options`

**Files:**
- Modify: `core/models.py:14-26`
- Test: `tests/test_config.py`

- [ ] **Step 1**：先写失败测试

```python
# tests/test_config.py 追加
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
```

- [ ] **Step 2**：跑测试确认失败
```bash
python -m pytest tests/test_config.py::test_worker_config_defaults_backend_type_to_claude_cli -v
# Expected: FAIL - AttributeError 'WorkerConfig' object has no attribute 'backend_type'
```

- [ ] **Step 3**：在 `core/models.py:WorkerConfig` 中追加字段

```python
@dataclass
class WorkerConfig:
    worker_id: str
    display_name: str
    provider: str
    model: str
    api_key_env: str
    profile_dir: str
    workspace_dir: str
    skills_dir: str
    base_url: str = ""
    role: str = "通用交付工位"
    enabled: bool = True
    backend_type: str = "claude_cli"
    backend_options: dict = field(default_factory=dict)
```

- [ ] **Step 4**：跑测试确认通过
```bash
python -m pytest tests/test_config.py -v
# Expected: PASS (and other config tests still green)
```

- [ ] **Step 5**：跑全套确认零回归
```bash
python -m pytest tests/ -q
# Expected: 40 passed
```

- [ ] **Step 6**：提交
```bash
git add core/models.py tests/test_config.py
git commit -m "feat(config): add backend_type/backend_options to WorkerConfig"
```

---

## Task 2：`ArtifactStore.resolve_path()` 返回绝对路径

**Files:**
- Modify: `core/artifacts.py`
- Test: `tests/test_artifacts.py`

- [ ] **Step 1**：失败测试

```python
def test_artifact_store_resolves_absolute_path(tmp_path):
    store = ArtifactStore(tmp_path)
    aid = store.write_text("niuma-1", "task-abc", "result.md", "hello")

    resolved = store.resolve_path(aid)

    assert Path(resolved).is_absolute()
    assert Path(resolved).read_text(encoding="utf-8") == "hello"
```

- [ ] **Step 2**：跑测试
```bash
python -m pytest tests/test_artifacts.py::test_artifact_store_resolves_absolute_path -v
# Expected: FAIL - AttributeError
```

- [ ] **Step 3**：在 `core/artifacts.py:ArtifactStore` 实现

```python
def resolve_path(self, artifact_id: str) -> str:
    # artifact_id 格式：worker_id/task_id/filename
    return str((self.root / artifact_id).resolve())
```

- [ ] **Step 4**：跑测试通过
```bash
python -m pytest tests/test_artifacts.py -v
```

- [ ] **Step 5**：提交
```bash
git add core/artifacts.py tests/test_artifacts.py
git commit -m "feat(artifacts): add resolve_path() for absolute path handoff"
```

---

## Task 3：新增 `ClaudeCliWorkerBackend`

**Files:**
- Modify: `core/worker_runtime.py`（追加 dataclass）
- Test: `tests/test_claude_cli_backend.py`（新建）

- [ ] **Step 1**：失败测试（mock subprocess）

```python
# tests/test_claude_cli_backend.py
import json
import pytest
from unittest.mock import AsyncMock, patch
from agent_factory.core.models import WorkerConfig
from agent_factory.core.worker_runtime import ClaudeCliWorkerBackend


def make_config(tmp_path):
    return WorkerConfig(
        worker_id="niuma-1",
        display_name="牛马1",
        provider="anthropic",
        model="claude-sonnet-4-6",
        api_key_env="ANTHROPIC_API_KEY",
        profile_dir=str(tmp_path / "profiles/niuma-1"),
        workspace_dir=str(tmp_path / "workspaces/niuma-1"),
        skills_dir=str(tmp_path / "skills/niuma-1"),
    )


@pytest.mark.asyncio
async def test_claude_cli_backend_invokes_claude_with_isolated_profile_and_cwd(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    captured = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env", {})
        captured["cwd"] = kwargs.get("cwd")

        process = AsyncMock()
        result_event = json.dumps({"type": "result", "result": "任务完成"})
        process.communicate.return_value = (result_event.encode("utf-8"), b"")
        process.returncode = 0
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    backend = ClaudeCliWorkerBackend(claude_command=["claude"])
    result = await backend.run("分析 JSP", config)

    assert result == "任务完成"
    assert "claude" in captured["args"]
    assert "-p" in captured["args"]
    assert "分析 JSP" in captured["args"]
    assert "--cwd" in captured["args"]
    assert captured["env"]["CLAUDE_CONFIG_DIR"] == str(tmp_path / "profiles/niuma-1")
    assert captured["cwd"] == str(tmp_path / "workspaces/niuma-1")


@pytest.mark.asyncio
async def test_claude_cli_backend_raises_on_nonzero_exit(tmp_path, monkeypatch):
    config = make_config(tmp_path)

    async def fake_create_subprocess_exec(*args, **kwargs):
        process = AsyncMock()
        process.communicate.return_value = (b"", b"auth error")
        process.returncode = 1
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    backend = ClaudeCliWorkerBackend()

    with pytest.raises(RuntimeError, match="exited 1"):
        await backend.run("hi", config)


@pytest.mark.asyncio
async def test_claude_cli_backend_kills_on_timeout(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    killed = {"called": False}

    async def fake_create_subprocess_exec(*args, **kwargs):
        process = AsyncMock()

        async def slow_communicate():
            await asyncio.sleep(10)
            return (b"", b"")

        process.communicate = slow_communicate
        process.kill = lambda: killed.update(called=True)
        process.wait = AsyncMock()
        process.returncode = -9
        return process

    import asyncio
    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    backend = ClaudeCliWorkerBackend(timeout_seconds=1)

    with pytest.raises(RuntimeError, match="exceeded"):
        await backend.run("hi", config)

    assert killed["called"]
```

- [ ] **Step 2**：跑测试确认失败
```bash
python -m pytest tests/test_claude_cli_backend.py -v
# Expected: FAIL - ImportError ClaudeCliWorkerBackend
```

- [ ] **Step 3**：在 `core/worker_runtime.py` 追加（**完整代码**，不要写 placeholder）

```python
import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ClaudeCliWorkerBackend:
    claude_command: list[str] = field(default_factory=lambda: ["claude"])
    timeout_seconds: int = 1800
    extra_args: list[str] = field(default_factory=list)

    async def run(self, prompt: str, config: WorkerConfig) -> str:
        Path(config.profile_dir).mkdir(parents=True, exist_ok=True)
        Path(config.workspace_dir).mkdir(parents=True, exist_ok=True)
        Path(config.skills_dir).mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(Path(config.profile_dir).resolve())

        args = [
            *self.claude_command,
            "-p", prompt,
            "--output-format", "stream-json",
            "--cwd", str(Path(config.workspace_dir).resolve()),
            "--model", config.model,
            *self.extra_args,
        ]

        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(Path(config.workspace_dir).resolve()),
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError(f"claude CLI exceeded {self.timeout_seconds}s, killed")

        if process.returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"claude CLI exited {process.returncode}: {stderr_text}")

        last_result_text = ""
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "result":
                last_result_text = event.get("result", "")
        return last_result_text
```

- [ ] **Step 4**：跑测试
```bash
python -m pytest tests/test_claude_cli_backend.py -v
# Expected: 3 passed
```

- [ ] **Step 5**：跑全套
```bash
python -m pytest tests/ -q
# Expected: 43 passed (40 + 3)
```

- [ ] **Step 6**：提交
```bash
git add core/worker_runtime.py tests/test_claude_cli_backend.py
git commit -m "feat(worker): add ClaudeCliWorkerBackend"
```

---

## Task 4：Backend 工厂

**Files:**
- Create: `core/backends.py`
- Test: `tests/test_backends.py`

- [ ] **Step 1**：失败测试

```python
# tests/test_backends.py
import pytest
from agent_factory.core.backends import build_backend, BackendError
from agent_factory.core.models import WorkerConfig
from agent_factory.core.worker_runtime import (
    ClaudeCliWorkerBackend, FakeWorkerBackend,
    OpenAICompatibleWorkerBackend, SubprocessWorkerBackend,
)


def base_config(backend_type, **opts):
    return WorkerConfig(
        worker_id="niuma-1",
        display_name="x",
        provider="x",
        model="x",
        api_key_env="X",
        profile_dir="p",
        workspace_dir="w",
        skills_dir="s",
        backend_type=backend_type,
        backend_options=opts,
    )


def test_build_backend_returns_claude_cli_by_default():
    config = base_config("claude_cli")
    assert isinstance(build_backend(config), ClaudeCliWorkerBackend)


def test_build_backend_returns_openai_compatible():
    config = base_config("openai_compatible")
    assert isinstance(build_backend(config), OpenAICompatibleWorkerBackend)


def test_build_backend_returns_fake_with_options():
    config = base_config("fake", response_text="hi")
    backend = build_backend(config)
    assert isinstance(backend, FakeWorkerBackend)
    assert backend.response_text == "hi"


def test_build_backend_rejects_unknown_type():
    config = base_config("unknown")
    with pytest.raises(BackendError):
        build_backend(config)
```

- [ ] **Step 2**：测试失败
```bash
python -m pytest tests/test_backends.py -v
# Expected: FAIL - ImportError
```

- [ ] **Step 3**：实现 `core/backends.py`

```python
from agent_factory.core.models import WorkerConfig
from agent_factory.core.worker_runtime import (
    ClaudeCliWorkerBackend,
    FakeWorkerBackend,
    OpenAICompatibleWorkerBackend,
    SubprocessWorkerBackend,
)


class BackendError(ValueError):
    pass


def build_backend(config: WorkerConfig):
    backend_type = config.backend_type
    options = dict(config.backend_options)
    if backend_type == "claude_cli":
        return ClaudeCliWorkerBackend(**options)
    if backend_type == "openai_compatible":
        return OpenAICompatibleWorkerBackend(**options)
    if backend_type == "subprocess":
        return SubprocessWorkerBackend(**options)
    if backend_type == "fake":
        return FakeWorkerBackend(**options)
    raise BackendError(f"unknown backend_type: {backend_type}")
```

- [ ] **Step 4**：测试通过
```bash
python -m pytest tests/test_backends.py -v
```

- [ ] **Step 5**：跑全套
```bash
python -m pytest tests/ -q
# Expected: 47 passed
```

- [ ] **Step 6**：提交
```bash
git add core/backends.py tests/test_backends.py
git commit -m "feat(backends): add build_backend factory"
```

---

## Task 5：Skill 软链脚本

**Files:**
- Create: `core/skill_linking.py`
- Test: `tests/test_skill_linking.py`

- [ ] **Step 1**：失败测试

```python
# tests/test_skill_linking.py
from pathlib import Path
from agent_factory.core.skill_linking import link_worker_skills


def test_link_worker_skills_creates_claude_skills_dir(tmp_path):
    skills_src = tmp_path / "skills/niuma-1/demo-skill"
    skills_src.mkdir(parents=True)
    (skills_src / "SKILL.md").write_text("---\nname: demo-skill\n---", encoding="utf-8")
    workspace = tmp_path / "workspaces/niuma-1"
    workspace.mkdir(parents=True)

    link_worker_skills(skills_dir=tmp_path / "skills/niuma-1", workspace_dir=workspace)

    linked = workspace / ".claude/skills/demo-skill/SKILL.md"
    assert linked.exists()
    assert "demo-skill" in linked.read_text(encoding="utf-8")
```

- [ ] **Step 2**：测试失败
```bash
python -m pytest tests/test_skill_linking.py -v
# Expected: FAIL ImportError
```

- [ ] **Step 3**：实现 `core/skill_linking.py`

```python
import os
import shutil
import sys
from pathlib import Path


def link_worker_skills(skills_dir: Path, workspace_dir: Path) -> None:
    skills_dir = Path(skills_dir)
    workspace_dir = Path(workspace_dir)
    target_root = workspace_dir / ".claude" / "skills"
    target_root.mkdir(parents=True, exist_ok=True)

    if not skills_dir.exists():
        return

    for skill_path in skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
        target = target_root / skill_path.name
        if target.exists() or target.is_symlink():
            continue
        _link_or_copy(skill_path, target)


def _link_or_copy(source: Path, target: Path) -> None:
    try:
        os.symlink(source, target, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass

    if sys.platform == "win32":
        try:
            import subprocess
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                check=True, capture_output=True,
            )
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    shutil.copytree(source, target)
```

- [ ] **Step 4**：跑测试
```bash
python -m pytest tests/test_skill_linking.py -v
```

- [ ] **Step 5**：把软链调用接到 `ClaudeCliWorkerBackend.run()` 开头（`core/worker_runtime.py`）：

```python
from agent_factory.core.skill_linking import link_worker_skills

# 在 mkdir 三件套之后、build args 之前：
link_worker_skills(Path(config.skills_dir), Path(config.workspace_dir))
```

- [ ] **Step 6**：跑全套
```bash
python -m pytest tests/ -q
# Expected: 48 passed
```

- [ ] **Step 7**：提交
```bash
git add core/skill_linking.py core/worker_runtime.py tests/test_skill_linking.py
git commit -m "feat(skills): link per-worker skills into workspace .claude/skills"
```

---

## Task 6：`supervisor.chain()` 文件级握手

**Files:**
- Modify: `core/supervisor.py`
- Test: `tests/test_supervisor.py`

- [ ] **Step 1**：失败测试

```python
@pytest.mark.asyncio
async def test_supervisor_chain_passes_artifact_file_paths_not_content(tmp_path):
    bus = TaskBus(["niuma-1", "niuma-2"])
    artifacts = ArtifactStore(tmp_path)
    source_runtime = WorkerRuntime(worker_config("niuma-1"), bus, artifacts, FakeWorkerBackend("# 需求清单\n非常长的内容" * 100))
    target_backend = FakeWorkerBackend("# 需求文档")
    target_runtime = WorkerRuntime(worker_config("niuma-2"), bus, artifacts, target_backend)
    supervisor = HermesSupervisor(bus, artifacts, {"niuma-1": source_runtime, "niuma-2": target_runtime})

    await supervisor.chain("niuma-1", "niuma-2", "逆向 JSP", "写文档")

    target_prompt = target_backend.calls[0][0]
    assert "非常长的内容" not in target_prompt    # 不再 inline 内容
    assert "result.md" in target_prompt           # 引用了文件
    assert "请用 Read 工具读取" in target_prompt
```

- [ ] **Step 2**：测试失败
```bash
python -m pytest tests/test_supervisor.py::test_supervisor_chain_passes_artifact_file_paths_not_content -v
# Expected: FAIL
```

- [ ] **Step 3**：修改 `core/supervisor.py`

```python
async def chain(
    self,
    source_worker: str,
    target_worker: str,
    source_prompt: str,
    next_instruction: str,
    handoff_user_prompt: str | None = None,
) -> tuple[TaskRecord, TaskRecord]:
    first = await self.delegate(source_worker, source_prompt)
    upstream_paths = [self.artifacts.resolve_path(aid) for aid in first.artifact_ids]
    upstream_ref = handoff_user_prompt if handoff_user_prompt is not None else source_prompt
    handoff_prompt = (
        f"{next_instruction}\n\n"
        f"上游任务: {upstream_ref}\n\n"
        "上游产物文件路径（请用 Read 工具读取，不要假设内容）:\n"
        + "\n".join(f"- {path}" for path in upstream_paths)
    )
    second = self.bus.create_task(
        target_worker,
        handoff_prompt,
        created_by="hermes",
        parent_task_id=first.task_id,
    )
    second = await self.runtimes[target_worker].execute(second.task_id)
    return first, second
```

- [ ] **Step 4**：更新现有 `test_supervisor_chain_passes_source_artifacts_to_target`，断言改为文件路径形式（旧断言 `"# 需求清单" in target_backend.calls[0][0]` 要改）

```python
# 旧
assert "# 需求清单" in target_backend.calls[0][0]
# 新
assert "上游产物文件路径" in target_backend.calls[0][0]
```

- [ ] **Step 5**：跑测试
```bash
python -m pytest tests/test_supervisor.py tests/test_api.py -v
# Expected: PASS (注意 test_api.py 那个 chain 泄漏回归测也需要相应更新)
```

- [ ] **Step 6**：跑全套
```bash
python -m pytest tests/ -q
# Expected: 49 passed
```

- [ ] **Step 7**：提交
```bash
git add core/supervisor.py tests/test_supervisor.py tests/test_api.py
git commit -m "feat(chain): pass artifact file paths instead of inlined content"
```

---

## Task 7：`worker_server.py` 启动时用 `build_backend` 装配

**Files:**
- Modify: `worker_server.py`
- Test: `tests/test_worker_server.py` (新建，烟雾测试)

- [ ] **Step 1**：读 `worker_server.py` 现有装配逻辑（grep `OpenAICompatibleWorkerBackend(` 找到位置）

- [ ] **Step 2**：把硬编码的 backend 实例化替换为 `build_backend(worker_config)`

```python
from agent_factory.core.backends import build_backend

# 替换原来的：
# backend = OpenAICompatibleWorkerBackend(...) if ... else SubprocessWorkerBackend(...)
backend = build_backend(worker_config)
```

- [ ] **Step 3**：写烟雾测试

```python
# tests/test_worker_server.py
from agent_factory.core.backends import build_backend
from agent_factory.core.models import WorkerConfig
from agent_factory.core.worker_runtime import OpenAICompatibleWorkerBackend


def test_factory_can_build_legacy_openai_config():
    config = WorkerConfig(
        worker_id="legacy",
        display_name="legacy",
        provider="deepseek",
        model="deepseek-chat",
        api_key_env="LEGACY_API_KEY",
        profile_dir="p",
        workspace_dir="w",
        skills_dir="s",
        backend_type="openai_compatible",
    )
    assert isinstance(build_backend(config), OpenAICompatibleWorkerBackend)
```

- [ ] **Step 4**：跑全套
```bash
python -m pytest tests/ -q
```

- [ ] **Step 5**：手测：把 `factory_config.json` 的 niuma-1 backend_type 改为 `"openai_compatible"`，启动 `python serve.py`，确认 console 工作如旧

- [ ] **Step 6**：提交
```bash
git add worker_server.py tests/test_worker_server.py
git commit -m "feat(server): use build_backend factory for worker instantiation"
```

---

## Task 8：`factory_config.json` 范例与默认

**Files:**
- Modify: `factory_config.json`（或新建 `factory_config.example.json`）
- Create: `proposals/2026-05-26-claude-cli-team/skeleton/factory_config.example.json`（已包含在本评审包）

- [ ] **Step 1**：从 `proposals/2026-05-26-claude-cli-team/skeleton/factory_config.example.json` 复制到仓库根 `factory_config.example.json`

- [ ] **Step 2**：在 `RUNBOOK.md` 加一节"切换 backend"

- [ ] **Step 3**：提交
```bash
git add factory_config.example.json RUNBOOK.md
git commit -m "docs: add factory_config.example.json with claude_cli backend"
```

---

## Task 9：niuma-1 灰度切换 + 端到端手测

**Files:** 无（运维操作）

- [ ] **Step 1**：编辑本地 `factory_config.json`，把 niuma-1 改为：

```json
{
  "worker_id": "niuma-1",
  "model": "claude-sonnet-4-6",
  "api_key_env": "ANTHROPIC_API_KEY",
  "backend_type": "claude_cli",
  "backend_options": {
    "timeout_seconds": 1800
  }
}
```

- [ ] **Step 2**：`taskkill /F /PID <旧>` + `python serve.py`

- [ ] **Step 3**：在 Console 单工位派工给 niuma-1，prompt = "请在工作区写一个 hello.md，内容是 'hi from niuma-1'"

- [ ] **Step 4**：验证 `workspaces/niuma-1/hello.md` 存在且内容正确

- [ ] **Step 5**：跑一次 chain（niuma-1 → niuma-2），验证 niuma-2 prompt 含文件路径而非内容，并且 niuma-2 工作成功

- [ ] **Step 6**：把验证截图/日志附到 PR

---

## 最终验收

- [ ] pytest 全绿（≥ 50 个测试）
- [ ] `claude --version` 在 CI 也能跑（或手动跳过）
- [ ] `factory_config.example.json` 提供两种 backend 范例
- [ ] `01-spec.md` 第 9 节回滚流程亲测可行
- [ ] `03-review-checklist.md` 全部勾选

---

## 提交节奏总结

| Task | 提交数 | 关键产物 |
|---|---|---|
| 0 | 0 | 分支建好 |
| 1 | 1 | WorkerConfig 字段 |
| 2 | 1 | resolve_path |
| 3 | 1 | ClaudeCliWorkerBackend |
| 4 | 1 | build_backend 工厂 |
| 5 | 1 | skill linking |
| 6 | 1 | chain 文件级握手 |
| 7 | 1 | worker_server 装配 |
| 8 | 1 | 配置范例与文档 |
| 9 | 0 | 手测 |

**共 8 个 commit**，每个独立可回滚，便于评审。
