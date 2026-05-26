# 牛马团队 Claude CLI 化 · 技术规约

**作者**：Hermes（本会话） · **日期**：2026-05-26 · **目标读者**：架构师 / 技术负责人

---

## 1. 背景与问题

### 1.1 现状

- 仓库：`D:\claude-code\cclaude`，FastAPI + Alpine.js 单体应用
- Worker 抽象：`WorkerConfig` + `WorkerRuntime` + `WorkerBackend`（三选一：`FakeWorkerBackend` / `SubprocessWorkerBackend` / `OpenAICompatibleWorkerBackend`）
- 实际生产用：`OpenAICompatibleWorkerBackend` → DeepSeek，仅一次性 `/chat/completions`
- 链式派工：`HermesSupervisor.chain()`，prompt 字符串拼接 + artifact 文本拼接

### 1.2 暴露的问题

| 问题 | 表现 | 根因 |
|---|---|---|
| 无工具能力 | 任务手册让模型「读规则文件、用 openpyxl 写 .xlsx」，模型只能编一段假装做了的 Markdown | backend 不暴露任何工具，只能返回文本 |
| 无独立工作区 | `workspace_dir` / `profile_dir` / `skills_dir` 三个字段空转 | 没有任何 backend 真正用这三个目录 |
| 上下文泄漏 | niuma-2 在 chain 里看到 niuma-1 的任务手册 | 已修（[7f00973](../../core/supervisor.py)），但治标 |
| 无重试 / 无自检 | 模型一次输出即终态，失败直接 `RuntimeError` | 没有 ReAct loop |
| 无技能复用 | `skills/niuma-N/` 目录空 | 没有技能加载机制 |

### 1.3 用户期望（原话归纳）

> 「我要的是一个团队 ... 每个都有自己独立的工作区，文件存放/配置文件，都是独立的，然后可以进行工作串联 ... 你（Hermes）永远都是我的第一交流对象，你去监控管理他们的状态。」

---

## 2. 设计目标

### 2.1 功能目标

- **F1** 每个 `niuma-*` 是一个真正的 agent（有工具循环、能多轮调工具、能自我修正）
- **F2** 每个 niuma 拥有完全隔离的「身份三件套」：profile（记忆 / 配置） / workspace（cwd） / skills（技能）
- **F3** Hermes 能并发派工给多个 niuma，能实时观察其工作过程（stream events），能强制超时 / 取消
- **F4** 链式派工通过**文件系统握手**，而非 prompt 字符串拼接
- **F5** 保留多模型扩展性：架构上允许某个 niuma 走非 Claude 后端

### 2.2 非功能目标

- **N1** 与现有 FastAPI 网关、`TaskBus`、`ArtifactStore`、Console 前端零冲突——上线后老接口（`/api/delegate` / `/api/chain`）行为对外不变
- **N2** 单个 niuma 故障不影响其他 niuma 与 Hermes 主进程
- **N3** 故障可快速回滚到现有 `OpenAICompatibleWorkerBackend`（配置开关）
- **N4** 全部测试（pytest）保持绿色，新功能附带不少于 80% 覆盖

### 2.3 不做的事

- 不重写 FastAPI / Console / TaskBus / ArtifactStore
- 不引入数据库（继续用 `runtime_config.json` + 文件系统）
- 不做 Web 端的 niuma 实时日志查看（仅 API 暴露，前端二期再做）
- 不做跨机分布式（先单机多进程）

---

## 3. 总体架构

### 3.1 角色

```
                   ┌─────────────────────────────┐
                   │  User (你)                  │
                   └──────────────┬──────────────┘
                                  │ 对话
                                  ▼
                   ┌─────────────────────────────┐
                   │  Hermes (本 Claude 会话)    │
                   │  · 监听用户                  │
                   │  · 拆任务                    │
                   │  · 派工 / 监控 / 汇报        │
                   └──────────────┬──────────────┘
                                  │ HTTP /api/*
                                  ▼
                   ┌─────────────────────────────┐
                   │  worker_server (FastAPI)    │
                   │  · TaskBus                  │
                   │  · ArtifactStore            │
                   │  · WorkerRuntime × N        │
                   └──────────────┬──────────────┘
                                  │ subprocess
                  ┌───────────────┼───────────────┐
                  ▼               ▼               ▼
            ┌──────────┐    ┌──────────┐    ┌──────────┐
            │ niuma-1  │    │ niuma-2  │    │ niuma-3  │
            │ claude   │    │ claude   │    │ DeepSeek │
            │ CLI 进程 │    │ CLI 进程 │    │ + tool   │
            │          │    │          │    │ loop     │
            └──────────┘    └──────────┘    └──────────┘
              │  │  │         │  │  │         │  │  │
              ▼  ▼  ▼         ▼  ▼  ▼         ▼  ▼  ▼
           profile workspace skills  (each isolated)
```

### 3.2 进程边界

- **Hermes** = 本 Claude Code 会话，对用户唯一可见
- **worker_server** = 长驻 FastAPI 进程（`serve.py` 启动）
- **niuma-N** = 每次任务**临时拉起**的 `claude -p ...` 子进程；任务结束即退出
  - 决策：不做 niuma 常驻，因为 claude CLI 本来就是"一个会话一个进程"的模型
  - 但 niuma 的 **profile 是常驻的**（`profiles/niuma-N/` 目录），所以"身份"持续

### 3.3 与现有代码的关系

| 现有 | 改动 | 说明 |
|---|---|---|
| `core/models.py:WorkerConfig` | 增字段 `backend_type` / `claude_args` | 不删字段，向后兼容 |
| `core/worker_runtime.py` | 新增 `ClaudeCliWorkerBackend` | 不改 `WorkerRuntime` 接口 |
| `core/supervisor.py` | 不改 | `chain()` 内部已经做文件级握手准备 |
| `core/api.py` | 不改 | endpoint 路径与契约不变 |
| `core/task_bus.py` / `core/artifacts.py` | 不改 | |
| `web/console.html` | 不改 | 后续加"打开 workspace"按钮再说 |
| `serve.py` / `conftest.py` | 不改 | |

---

## 4. 详细设计

### 4.1 `WorkerBackend` 协议

定义一个明确的抽象（Python 用 Protocol 或抽象基类）：

```python
class WorkerBackend(Protocol):
    async def run(self, prompt: str, config: WorkerConfig) -> str:
        """跑一次任务，返回最终输出文本（也可能是空字符串，主要产物落在 workspace）"""
        ...
```

现有三个 backend（Fake / Subprocess / OpenAICompatible）都已经满足这个签名。

### 4.2 新 backend：`ClaudeCliWorkerBackend`

```python
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
        env["CLAUDE_CONFIG_DIR"] = config.profile_dir  # 1. profile 隔离
        # 注意：CLAUDE_CONFIG_DIR 让 claude CLI 把 ~/.claude 指向此目录
        # MEMORY.md, MCP 配置, projects 历史都落在这里

        args = [
            *self.claude_command,
            "-p", prompt,                       # 2. headless 模式，prompt 走参数
            "--output-format", "stream-json",   # 3. 拿事件流（含 tool use）
            "--cwd", config.workspace_dir,      # 4. cwd 隔离
            "--model", config.model,            # 5. 模型选择
            *self.extra_args,
        ]

        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=config.workspace_dir,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        events = []
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
            raise RuntimeError(f"claude CLI exited {process.returncode}: {stderr.decode('utf-8', errors='replace')[:400]}")

        # 解析 stream-json 拿最终文本
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            events.append(event)

        # 取最后一条 type=result 的 result 字段
        for event in reversed(events):
            if event.get("type") == "result":
                return event.get("result", "")
        return ""
```

#### 4.2.1 stream-json 事件类型

claude CLI `--output-format stream-json` 每行一个 JSON 对象，关键 type：

| type | 含义 | Hermes 用途 |
|---|---|---|
| `system.init` | 会话初始化 | 拿 `session_id` |
| `assistant` | 模型输出（含 tool_use） | 实时透传给前端 |
| `user` | 工具执行结果回填 | 监控 |
| `result` | 最终结果（含 cost / duration / usage） | 记账 + 汇报 |

#### 4.2.2 技能（Skills）注入

每个 niuma 的 `skills_dir`（如 `skills/niuma-1/`）里放它专属的技能，结构遵循 Claude Code 技能规范：

```
skills/niuma-1/
  jsp-reverse-engineering/
    SKILL.md           # frontmatter + 技能描述
    references/...
    scripts/...
```

把 `skills_dir` 注入到 niuma 的发现路径：
- 方案 a：通过 symlink / junction 把 `skills/niuma-1/` 挂到 `profiles/niuma-1/skills/`（更隐式，但跨平台麻烦）
- 方案 b：用 claude CLI 的 `--additional-skills-dir` 参数（如果存在）
- 方案 c：在每次启动时把 `skills/niuma-1/` 内容**软链接**到 `workspaces/niuma-1/.claude/skills/`（项目级技能，最自然）

**默认采用方案 c**，详见实施计划 Task 5。

### 4.3 链式派工的文件级握手

修改 `HermesSupervisor.chain()`，从 prompt 拼接改为**约定文件路径**：

```python
async def chain(self, source_worker, target_worker, source_prompt, next_instruction,
                handoff_user_prompt=None):
    first = await self.delegate(source_worker, source_prompt)

    # 现有：artifact_id 是 ArtifactStore 内部的虚拟路径
    # 新增：把 artifact 物理路径告诉 niuma-2
    upstream_artifacts = [
        self.artifacts.resolve_path(artifact_id)  # 绝对路径
        for artifact_id in first.artifact_ids
    ]

    upstream_ref = handoff_user_prompt if handoff_user_prompt is not None else source_prompt
    handoff_prompt = (
        f"{next_instruction}\n\n"
        f"上游任务: {upstream_ref}\n\n"
        f"上游产物文件路径（请用 Read 工具读取，不要假设内容）:\n"
        + "\n".join(f"- {path}" for path in upstream_artifacts)
    )

    second = self.bus.create_task(target_worker, handoff_prompt, ...)
    return first, await self.runtimes[target_worker].execute(second.task_id)
```

niuma-2 收到的 prompt 是"去读这几个文件"，不再是把上游内容塞在 prompt 里。这解决：
- 上下文泄漏（不再 inline 任何上游内容）
- 大 artifact 截断（之前 18KB 拼进去会爆 context）
- 文档隔离（niuma-2 自己的 task_manual 不会被上游 prompt 污染）

### 4.4 配置扩展

`WorkerConfig` 增字段：

```python
@dataclass
class WorkerConfig:
    # ... existing fields
    backend_type: str = "claude_cli"          # 新增："claude_cli" | "openai_compatible" | "subprocess" | "fake"
    backend_options: dict = field(default_factory=dict)  # 新增：透传给 backend 的参数
```

`backend_options` 例子：

```json
{
  "claude_command": ["claude"],
  "extra_args": ["--permission-mode", "acceptEdits"],
  "timeout_seconds": 1800
}
```

`factory_config.json` 范例见 `skeleton/factory_config.example.json`。

### 4.5 Backend 工厂

新增 `core/backends.py`：

```python
def build_backend(config: WorkerConfig) -> WorkerBackend:
    if config.backend_type == "claude_cli":
        return ClaudeCliWorkerBackend(**config.backend_options)
    if config.backend_type == "openai_compatible":
        return OpenAICompatibleWorkerBackend(**config.backend_options)
    if config.backend_type == "subprocess":
        return SubprocessWorkerBackend(**config.backend_options)
    if config.backend_type == "fake":
        return FakeWorkerBackend(**config.backend_options)
    raise ConfigError(f"unknown backend_type: {config.backend_type}")
```

`worker_server.py` 启动时按 `WorkerConfig.backend_type` 实例化 backend。

---

## 5. 数据流

### 5.1 单工位派工

```
User → Hermes → POST /api/delegate (worker=niuma-1)
                    ↓
              compose_worker_prompt(niuma-1, prompt)  # 注入已安装文档
                    ↓
              supervisor.delegate(niuma-1, prompt)
                    ↓
              WorkerRuntime.execute(task_id)
                    ↓
              ClaudeCliWorkerBackend.run(prompt, config)
                    ↓
              subprocess: claude -p ... --cwd workspaces/niuma-1
                    ↓
              [niuma-1 在 workspace 里读写文件、调工具、TodoWrite...]
                    ↓
              stdout: stream-json events
                    ↓
              解析 type=result，提取最终输出文本
                    ↓
              ArtifactStore.write_text(niuma-1, task_id, "result.md", text)
                    ↓
              bus.mark_succeeded → 返回 TaskRecord
                    ↓
              Hermes 看 TaskRecord，把结果汇报给用户
```

### 5.2 链式派工

```
User → Hermes → POST /api/chain (source=niuma-1, target=niuma-2)
                    ↓
              compose_worker_prompt(niuma-1, prompt)
                    ↓
              supervisor.chain(...)
                    ├── delegate(niuma-1, composed_prompt)  # niuma-1 跑完
                    │     └── ArtifactStore 落盘 artifacts/niuma-1/task-xxx/result.md
                    ↓
              收集 niuma-1 的 artifact 绝对路径
                    ↓
              组装 handoff_prompt: "上游任务: <原始prompt> + 文件路径列表"
                    ↓
              delegate(niuma-2, handoff_prompt)
                    └── niuma-2 在它自己的 workspace 里
                          调 Read 工具去读 artifacts/niuma-1/task-xxx/result.md
                          然后开始工作
                    ↓
              返回 (first, second) TaskRecord
```

---

## 6. 目录与文件布局

```
cclaude/
├── core/
│   ├── backends.py             ← 新增（工厂）
│   ├── worker_runtime.py       ← 新增 ClaudeCliWorkerBackend
│   ├── models.py               ← WorkerConfig 加字段
│   ├── supervisor.py           ← chain() 改文件级握手
│   ├── api.py                  ← 不动
│   ├── task_bus.py             ← 不动
│   └── artifacts.py            ← 新增 resolve_path() 方法
├── profiles/
│   ├── niuma-1/                ← niuma-1 的 CLAUDE_CONFIG_DIR
│   │   ├── settings.json
│   │   ├── MEMORY.md
│   │   └── projects/...        ← claude CLI 自动维护
│   └── niuma-2/
├── workspaces/
│   ├── niuma-1/                ← niuma-1 的 cwd
│   │   └── .claude/skills/     ← 从 skills/niuma-1/ 软链
│   └── niuma-2/
├── skills/
│   ├── niuma-1/
│   │   ├── jsp-reverse-engineering/
│   │   └── requirements-extraction/
│   └── niuma-2/
│       └── docx-writer/
├── artifacts/                  ← ArtifactStore 物理位置
│   └── niuma-1/task-xxx/result.md
├── tests/
│   └── test_claude_cli_backend.py  ← 新增
└── proposals/2026-05-26-claude-cli-team/  ← 本评审包
```

---

## 7. 安全与权限

### 7.1 文件系统隔离

- niuma-N 的 `cwd = workspaces/niuma-N`，正常调用 `Read` / `Write` / `Edit` 不会出 workspace
- 但 Bash 工具可以 `cd ..`，技术上可越界——**这是 claude CLI 的设计权限模型**
- 缓解：niuma 默认 `--permission-mode acceptEdits`（允许编辑），危险操作（rm、git push、网络）走 ask；高敏环境用 `--permission-mode plan`

### 7.2 凭据隔离

- 每个 `profiles/niuma-N/` 独立持有 Anthropic 凭据（API key 或 OAuth token）
- 不同 niuma 可以用不同账号——便于配额隔离 / 计费分账
- API key **不在** `factory_config.json` 明文，统一从环境变量或 `runtime_config.json`（已 gitignored）读

### 7.3 进程沙箱

- 不在本期实现，niuma 跑在与 worker_server 同一用户、同一文件系统下
- 二期可考虑 Docker / Windows Sandbox 隔离

---

## 8. 可观测性

### 8.1 实时事件

- `ClaudeCliWorkerBackend.run()` 不只是返回最终文本，还要把每行 stream-json 事件存到 `TaskRecord.events: list[dict]`
- `/api/tasks/{task_id}/events` 新接口（二期），供前端做时间线
- 一期：events 落盘 `artifacts/niuma-N/task-xxx/events.jsonl`，hermes 可读

### 8.2 计费

- `type=result` 事件含 `usage.input_tokens` / `usage.output_tokens` / `total_cost_usd`
- 累计写入 `TaskRecord.usage` 字段（新增）
- 可在 `/api/health` 上暴露 daily / monthly 总额

### 8.3 失败诊断

- subprocess 非 0 退出：stderr 前 400 字符进 `TaskRecord.error`
- 超时：明确写"exceeded Xs, killed"
- stream-json 解析失败：把 raw stdout 末尾 1KB 写进 error

---

## 9. 兼容与回滚

### 9.1 平滑切换

- 默认 `factory_config.json` 仍把 niuma-1/2 配成 `backend_type: "openai_compatible"`（现状）
- 上线后先把 niuma-1 单个切到 `backend_type: "claude_cli"`，观察一周
- 然后 niuma-2 切，再观察一周
- 全切完后，老 backend 留代码，半年后视情况删

### 9.2 回滚

- 改 `factory_config.json` 单字段 + 重启 worker_server，秒级回滚
- artifacts 格式不变，已生成的产物不受影响

---

## 10. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| claude CLI 在生产服务器没装 / 版本不对 | 中 | 高（启动即失败） | worker_server 启动时 `claude --version` 自检，写入 health endpoint |
| claude CLI stream-json 格式未来变更 | 低 | 中 | 锁定一个 CLI 主版本，CHANGELOG 关注 |
| subprocess 僵尸进程堆积 | 中 | 高（吃光内存） | timeout 强制 kill + 进程组 wait + 启动时 sweep 旧 pid |
| 单个 niuma 任务超时 30 分钟，用户体验差 | 中 | 中 | `/api/tasks/{id}/events` 实时流；前端轮询并显示「思考中：第 N 步」 |
| Claude API 限流 / 余额耗尽 | 中 | 高 | health endpoint 每日额度上报；失败时清晰提示 |
| Skill 软链在 Windows 上失败（需要管理员） | 高 | 中 | fallback 用 `mklink /J`（junction），不需要管理员；再 fallback 用 copy |
| 链式派工时 niuma-2 读不到 niuma-1 artifact（路径不对 / 跨盘符） | 中 | 高 | `ArtifactStore.resolve_path()` 必须返回绝对路径；niuma-2 prompt 里明示绝对路径 |
| Claude Max 订阅 vs 按量计费模式选错，成本失控 | 中 | 高 | 见 `04-cost-and-rollout.md`，先小流量灰度 |
| niuma 工作时跑了 `rm -rf` 或 git push 等破坏操作 | 低 | 极高 | `--permission-mode` 设到 ask，关键工具白名单 |

---

## 11. 测试策略

详见 `02-implementation-plan.md`，简要：

- **单测**：`ClaudeCliWorkerBackend` 用 mock subprocess（捕获 args + 模拟 stdout stream-json）
- **集成测**：用 `claude` 真命令跑一个最小 prompt（"echo hello"），断言 artifact 落盘
- **回归测**：现有 39 个 pytest 用例全绿
- **手测**：见 `RUNBOOK.md` 现有验收清单 + 本提案 `03-review-checklist.md`

---

## 12. 后续路线（不在本期）

- Console 端"打开 niuma workspace"按钮
- `/api/tasks/{id}/events` SSE 实时流，前端显示工具调用过程
- niuma 互相派工（niuma-2 在工作中调用 `Task` 工具 spawn 出 niuma-3 临时帮手）
- 跨机分布式（niuma 跑在不同容器 / 不同机器）
- MCP server 接入（niuma 接数据库 / 内部系统 API）
