# 00 · 接手 Agent 入口指令

> **读者**：本评审包的"接手者"。无论你是 Codex / Claude / 其他 LLM agent，从这一份开始读。  
> **如果你是人类评审者**：请直接读 `README.md`，本文件可跳过。

---

## 你是谁、要干什么

你被指派接手一个名为 **cclaude / agent_factory** 的 Python + FastAPI 项目，把现有的"一次性 chat completion 式" niuma worker 升级为"每人一个独立 Claude CLI 进程"的真正 agent 团队（B 方案）。

完整的设计、实施计划、骨架代码、成本评估全部在这个包里。**你不需要重新设计，只需按计划执行。**

---

## 第一步：把仓库放到工作区

```bash
# 1. clone（默认 redesign/console-brutalist 是当前 HEAD）
git clone https://github.com/lecasongg/cclaude.git
cd cclaude
git checkout redesign/console-brutalist

# 2. 从本评审包推荐的分支起点开始
git checkout -b feature/claude-cli-backend
```

**仓库当前状态参考点**：commit `7f00973`（fix(chain): stop leaking niuma-1 task_manual+conversion_rules into niuma-2 prompt）

---

## 第二步：基线自检（每一项不通过都要先停下来）

```bash
# Python 版本
python --version
# Expected: 3.11+

# 测试基线
python -m pytest tests/ -q
# Expected: 39 passed

# claude CLI 是否就绪
claude --version
# Expected: 输出版本号
# 如果 command not found：
#   npm install -g @anthropic-ai/claude-code
# 然后让用户处理登录或设置 ANTHROPIC_API_KEY

# claude CLI 关键 flag 是否存在（实施计划假定这些 flag 存在）
claude --help | grep -E -- "-p|--output-format|--cwd|--model|--permission-mode"
# Expected: 五个 flag 都出现
# 如果有缺失：暂停执行，把缺失情况报给用户，等指令
```

---

## 第三步：阅读顺序

按这个顺序读完，再开始动手：

1. **`README.md`** — 总览，决策摘要（5 分钟）
2. **`01-spec.md`** — 完整规约
   - 必读：§1（背景）、§2（目标）、§3（架构）、§4（详细设计）
   - 选读：§5-12（数据流 / 安全 / 风险 / 后续）
3. **`diagrams/architecture.md`** — 看 3 张图建立空间感（5 分钟）
4. **`02-implementation-plan.md`** — 9 个 Task 的逐步实施计划，**这是你的主要工作清单**
5. **`03-review-checklist.md`** — 知道你产出要满足的验收维度
6. **`04-cost-and-rollout.md`** — 成本和灰度，主要为产物 reviewer 准备，你了解一下即可
7. **`skeleton/`** — 4 份骨架代码 + 1 份配置范例，落地时可直接 copy

---

## 第四步：执行实施计划

打开 `02-implementation-plan.md`，按 **Task 0 → Task 9** 顺序执行。

每个 Task 的形态都是固定的：

```
Task N · 标题
  Files: 列出要改 / 要建 / 要测的文件
  Step 1: 写失败测试（含完整代码）
  Step 2: 跑测试确认失败
  Step 3: 写实现（含完整代码）
  Step 4: 跑测试确认通过
  Step 5: 跑全套确认零回归
  Step 6: git commit（含建议的 message）
```

**严格遵守**：

- TDD：先写测试，看到红，再写实现，看到绿，再 commit
- 每个 Task 一次 commit；不要把多个 Task 揉成一个
- pytest 中途任何回归都要先修复再前进，不要"先放着以后再说"
- 骨架代码（`skeleton/*.py`）是**完整可运行**的，不是伪代码 —— 落地时 copy 进 `core/` 即可，遇到 import 错误自己调整

---

## 第五步：什么时候停下来问

遇到以下任意一种情况，**停下来汇报、等指令**：

1. **Task 0 自检失败**（claude CLI 没装、pytest 基线不绿、claude flag 缺失）
2. **实施计划某一步的假设与实际仓库状态冲突**（比如你发现 `core/api.py` 已经被人改过、与 spec 引用的行号对不上）
3. **超过 3 次反复修改仍无法让某个测试通过**（这通常意味着 spec 有 bug，让用户介入）
4. **API 调用失败且影响进度**（凭据问题、限流）
5. **任何会破坏现有数据的操作**（删除 `artifacts/` / `runtime_config.json` / `workspaces/` 都需要确认）
6. **要 push 到远端 / 开 PR / 删分支**等不可逆操作

---

## 关键事实卡（避免重复问用户）

| 项 | 值 |
|---|---|
| 仓库地址 | https://github.com/lecasongg/cclaude |
| 起始分支 | `redesign/console-brutalist`（最新 commit: `7f00973`） |
| 工作分支 | `feature/claude-cli-backend`（你需要自己创建） |
| Python 版本 | 3.11+ |
| 测试基线 | pytest 39 passed |
| 包的命名空间 | `agent_factory.core.*`（由 `conftest.py` / `serve.py` 别名映射，不要试图改） |
| 启动方式 | `python serve.py`（不是 `python worker_server.py`） |
| 默认端口 | 127.0.0.1:8846 |
| 默认 token | `local-token`（仅本地开发） |
| API 鉴权头 | `x-hermes-token` |
| 凭据来源 | 环境变量 `ANTHROPIC_API_KEY` / `NIUMA_1_API_KEY` / ...（**不要**写进 `factory_config.json`） |
| 运行时配置 | `runtime_config.json` 已 gitignored，不要 commit |
| 测试别名机制 | 仓库根 `conftest.py` 把 `agent_factory` 别名到当前目录；本地跑 pytest 直接生效，CI 同理 |

---

## 包里有什么术语你可能不熟

- **Hermes**：在本项目里 = "调度者 / 工头"，是一个角色名，代码里对应 `HermesSupervisor` 类。当前由发起任务的人类用户的 LLM 助手扮演这个角色。
- **niuma**："牛马"的拼音，是 worker 在本项目里的代号（niuma-1 / niuma-2 ...）。仅是命名习惯，没有特殊技术含义。
- **WorkerBackend**：抽象协议，定义为 `async def run(prompt, config) -> str`。现有四个实现：`FakeWorkerBackend`、`SubprocessWorkerBackend`、`OpenAICompatibleWorkerBackend`，要新增的是 `ClaudeCliWorkerBackend`。
- **链式派工 (chain)**：把 niuma-1 的产物作为输入交给 niuma-2 继续处理，由 `HermesSupervisor.chain()` 实现。本次改造要把它从"prompt 拼接式"改为"文件级握手式"。
- **artifact**：worker 产出的文件，由 `ArtifactStore` 落盘到 `artifacts/<worker_id>/<task_id>/<filename>`。
- **profile / workspace / skills 三件套**：每个 niuma 的隔离单元，分别对应 `profiles/niuma-N/`（CLAUDE_CONFIG_DIR / 记忆 / 凭据）、`workspaces/niuma-N/`（cwd / 文件读写）、`skills/niuma-N/`（专属技能目录）。

---

## 如果你的运行环境有专属约定

本评审包**不绑定任何 agent 平台特定的 skill / sub-skill / plan mode**。原则上：

- 如果你的平台有 TDD 自动化能力，按你的能力用，但产出要满足实施计划里的"写测试 → 看红 → 写实现 → 看绿 → commit"节奏
- 如果你能 spawn 子 agent 做 review，鼓励用（每个 Task 完成后跑一次 spec + code review 是好实践）
- 如果你的平台只能单线程顺序执行，按 Task 0→9 顺序做即可

---

## 最终交付物清单

完成全部 9 个 Task 后，你的 PR 应该包含：

- [ ] `feature/claude-cli-backend` 分支，8 次明确的 commit
- [ ] `core/models.py` 新增 `backend_type` / `backend_options` 字段
- [ ] `core/artifacts.py` 新增 `resolve_path()` 方法
- [ ] `core/worker_runtime.py` 新增 `ClaudeCliWorkerBackend`
- [ ] `core/backends.py` 新文件，`build_backend()` 工厂
- [ ] `core/skill_linking.py` 新文件，跨平台技能软链
- [ ] `core/supervisor.py:chain()` 改为文件级握手
- [ ] `worker_server.py` 启动时通过工厂装配 backend
- [ ] `factory_config.example.json` 含 claude_cli + openai_compatible 两种范例
- [ ] `RUNBOOK.md` 增加"切换 backend"小节
- [ ] pytest ≥ 50 个用例全绿
- [ ] PR 描述里贴：(a) `python -m pytest tests/ -q` 输出 (b) Task 9 端到端手测的输出 / 截图

完成后**不要自行 push 到远端、不要自行开 PR**——把本地 commit 状态汇报给用户，等用户审核后再下一步。

---

## 一句话总结

> 读完包 → 跑基线 → 按 02-implementation-plan.md 一个 Task 一个 Task 做 → 完成后回报给用户。
