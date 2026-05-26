# Marvis Codex AI 工厂操作台 · 产品化架构蓝图 v0.3

本文档将原始“Codex 多智能体特工队”蓝图整理为一个可产品化、可工程落地、可持续迭代的 AI 工厂操作台方案。

Marvis 的目标不是再做一个普通聊天机器人，也不是只做一个 Agent workflow 画布，而是提供一套面向真实工程任务的本地/私有化 Agent 工厂运行时：用户像管理工位一样管理多个独立 AI Agent，每个 Agent 拥有自己的身份、工作区、技能、记忆、日志和执行进程。

---

## 1. 产品定位

### 1.1 一句话定位

Marvis 是一套新的、独立的 AI 工厂操作台产品，首期面向旧系统改造团队和企业内网团队，调度一组独立 Codex 工位，打穿“老系统逆向 → 需求文档 → 测试用例”的完整工程链路。

### 1.2 不做什么

- 不做单纯聊天窗口。
- 不做只传 prompt 的“假多智能体”演示。
- 不做完全云端绑定的 Agent SaaS。
- 不优先做花哨动画和营销式大屏。
- 不把所有任务抽象成僵硬的低代码节点。

### 1.3 核心差异

| 维度 | 普通 Agent 应用 | Marvis |
|---|---|---|
| Agent 形态 | 会话、函数、Python 对象 | 独立进程、独立工作区、独立身份 |
| 协作方式 | 消息/上下文传递 | V1 以文件级产物握手为核心，消息总线后续增强 |
| 任务执行 | 以 prompt 为中心 | 以任务书、工位、产物、日志为中心 |
| 适用场景 | 问答、轻量自动化 | 旧系统改造、内网工程自动化、长任务流水线 |
| 用户感知 | 和 AI 对话 | 管理一组 AI 工位 |

### 1.4 产品边界

Marvis 应作为独立产品发展，而不是当前 `cclaude` 项目的一个附属功能。当前项目可以作为孵化原型和技术验证场，但产品命名、配置模型、运行时目录、CLI、UI 和测试体系都应逐步独立。

这意味着：

- `cclaude` 负责验证 Codex CLI/Moon Bridge/多 worker 调度能力。
- Marvis 负责沉淀产品级运行时、任务书、合规测试、工厂控制台和交付体验。
- 后续代码可以从当前项目中抽出 `core` 能力，形成 Marvis 自己的包、CLI 和配置目录。

---

## 2. 目标用户与核心场景

### 2.1 目标用户

| 用户 | 需求 |
|---|---|
| 旧系统改造团队 | 让不同 Agent 分别负责逆向、需求文档、测试用例和迁移准备 |
| 企业内网团队 | 使用私有模型、中转站、本地部署和内网代码库，降低外部依赖 |
| 项目负责人 | 监控 AI 工位的进度、产物、风险和验收状态 |

首期不把独立开发者、泛自动化用户、普通聊天用户作为核心 ICP。产品应先服务“有存量代码、有改造压力、有内网约束、有交付文档要求”的团队。

### 2.2 V1 首个打穿场景：老系统改造

V1 不追求泛化到所有 Agent 工作流，而是先完整打穿一个高价值场景：老系统改造。

目标链路：

```text
遗留代码输入
  -> Agent A：逆向分析 JSP/JS/SQL
  -> Agent B：生成需求文档和业务规则
  -> Agent C：生成测试计划和测试用例
  -> 用户审核与修正
  -> 形成可交付改造包
```

阶段拆解：

1. 逆向分析  
   Agent A 读取 JSP/JS/SQL，输出功能清单、接口清单、表关系。

2. 需求文档生成  
   Agent B 读取 Agent A 的产物，生成 PRD、业务规则、异常流程。

3. 测试用例生成  
   Agent C 读取需求文档和代码路径，生成测试计划、pytest/JUnit 用例。

4. 用户审核与修正  
   用户对产物提出修正，系统追加 correction，并驱动相关 step 重跑。

5. 迁移改造准备  
   Agent D 负责代码迁移，Agent E 负责审查，Agent F 负责修复失败测试。

V1 的胜负手不是“支持多少场景”，而是这个链路能否稳定、可审计、可重跑、可交付。

### 2.3 文件级产物握手是 V1 核心

V1 的 Agent 协作以文件级产物握手为主，不把消息总线作为首要复杂度。

示例：

```text
Agent A 输出：
artifacts/runs/run-001/reverse/function-list.md
artifacts/runs/run-001/reverse/table-map.md

Agent B 输入：
读取 Agent A declared outputs，生成 requirements.md

Agent C 输入：
读取 requirements.md 和 table-map.md，生成 test-plan.md
```

这种设计的好处：

- 产物可见。
- 依赖清晰。
- 可审计。
- 可重跑。
- 不依赖一次性上下文。
- 更符合旧系统改造团队的交付习惯。

---

## 3. 产品原则

1. 工位优先，而不是聊天优先。  
   用户看到的是一组可管理的 AI 工位，而不是一堆会话。

2. 产物优先，而不是回答优先。  
   每个任务必须产生文件、日志、状态或可检查的 artifact。

3. 可恢复优先，而不是一次性执行优先。  
   长任务中断后应能恢复，不能依赖单次上下文窗口。

4. 约束优先，而不是完全放任自治。  
   Agent 可以自主执行，但必须遵守任务书、权限、产物标准和自检清单。

5. 本地优先，云端可选。  
   支持本地项目、本地工作区、私有模型代理、Moon Bridge、企业中转站。

6. 工程真实优先，而不是演示效果优先。  
   UI 朴素、低动画、可审计、可重跑、可定位失败。

---

## 4. 核心概念模型

| 概念 | 定义 |
|---|---|
| 用户 | 系统最高权限者，创建任务书、确认派工、审核产物 |
| 工厂操作台 | 用户进行监控、派工、审查、配置的 UI |
| 调度器 | 负责把任务书拆分为工位任务，可由 Hermes/Codex/Claude 等承担 |
| Agent 工位 | 独立执行单元，拥有模型、profile、workspace、skills、memory、logs |
| 任务书 | 用户确认后的任务契约，包含目标、步骤、依赖、约束、产物标准 |
| 流水线 | 一次任务书执行实例，由多个步骤和多个工位组成 |
| 产物 | Agent 写出的文件、报告、补丁、测试结果、日志摘要 |
| 资源管理器 | 管理 Agent 注册、占用、锁、健康状态和调度冲突 |
| 消息总线 | Agent 和调度器之间传递任务、状态、通知、错误、汇报 |
| 事件日志 | 所有关键动作的结构化记录，用于恢复、审计和 UI 实时展示 |

---

## 5. 系统架构

### 5.1 总体分层

```text
-------------------------------------------------------+
| UI: AI 工厂操作台                                      |
| 总控台 / 流水线视图 / 工位中心 / 任务书编辑器 / 日志    |
+-------------------------------------------------------+
| API Server                                             |
| Auth / Workers / Tasks / Pipelines / Messages / Logs   |
+-------------------------------------------------------+
| Orchestration Runtime                                  |
| ResourceManager / Scheduler / TaskBook Engine / Bus    |
+-------------------------------------------------------+
| Agent Runtime                                          |
| Codex CLI / Claude CLI / OpenAI-Compatible / Mock      |
+-------------------------------------------------------+
| Storage                                                |
| SQLite / artifacts / workspaces / profiles / events    |
+-------------------------------------------------------+
| Model & Tool Integrations                              |
| Moon Bridge / OpenAI / Anthropic / MCP / Local tools    |
+-------------------------------------------------------+
```

### 5.2 当前项目映射

| 目标模块 | 当前已有基础 | 需要增强 |
|---|---|---|
| Agent Runtime | 已有 `claude_cli`、`codex_cli`、`openai_compatible` | 统一事件协议、健康检查、权限边界 |
| Worker Config | 已有 per-worker profile/workspace/skills/backend | 增加 tags、capabilities、group、resource limits |
| Task Bus | 已有基础状态和任务队列 | 持久化、锁、恢复、消息类型 |
| Artifacts | 已有任务结果文件 | 结构化产物索引、版本、依赖关系 |
| UI Console | 已有基础 worker/task 页面 | 工位中心、流水线视图、任务书编辑器、日志面板 |

---

## 6. Agent 工位模型

### 6.1 Agent 必备属性

```yaml
agent_id: niuma-1
display_name: 牛马1
role: JSP/JS/SQL 老系统逆向分析工位
group: legacy-modernization
tags:
  - jsp
  - sql
  - reverse-engineering
backend:
  type: codex_cli
  model: deepseek-v4-pro
  base_url: http://127.0.0.1:38440/v1
  api_key_env: NIUMA_1_API_KEY
paths:
  profile: agents/niuma-1/profile
  workspace: agents/niuma-1/workspace
  skills: agents/niuma-1/skills
  memory: agents/niuma-1/memory
  logs: agents/niuma-1/logs
limits:
  max_parallel_tasks: 1
  default_timeout_seconds: 1800
```

### 6.2 Agent 状态

| 状态 | 含义 |
|---|---|
| idle | 空闲，可被调度 |
| reserved | 已被某个流水线锁定，但尚未开始执行 |
| running | 正在执行任务 |
| waiting | 等待依赖、用户确认或外部资源 |
| blocked | 被错误阻塞，需要人工处理 |
| failed | 当前任务失败 |
| offline | 进程不可用或健康检查失败 |

### 6.3 Agent 能力边界

每个 Agent 应具备：

- 独立模型配置。
- 独立 profile 和 memory。
- 独立 workspace。
- 独立 skills。
- 文件读写能力。
- shell 执行能力。
- 结构化事件输出能力。
- 自检和失败汇报能力。

长期目标是让 Agent 能 spawn 子 Agent，但 V1 应先保证平级 Agent 稳定可控。

---

## 7. 工作区与权限模型

### 7.1 推荐目录结构

```text
marvis-runtime/
  shared/
    taskbooks/
    references/
    public-artifacts/
  agents/
    niuma-1/
      profile/
      workspace/
      skills/
      memory/
      logs/
      state.yaml
    niuma-2/
      profile/
      workspace/
      skills/
      memory/
      logs/
      state.yaml
  artifacts/
    runs/
      run-20260527-001/
        step-001/
        step-002/
  events/
    run-20260527-001.jsonl
  marvis.db
```

### 7.2 权限规则

| 角色 | 自己工作区 | 同级工作区 | shared | artifacts | 系统配置 |
|---|---|---|---|---|---|
| 用户 | 读写 | 读写 | 读写 | 读写 | 读写 |
| 调度器 | 读写 | 读写 | 读写 | 读写 | 受限读写 |
| 子 Agent | 读写 | 只读 | 读写 | 写自己的产物 | 只读 |

### 7.3 权限落地分阶段

P0 阶段可以先用路径约定和运行参数限制。  
P1 阶段引入文件访问代理或 allowlist。  
P2 阶段支持 OS 用户隔离、容器隔离或轻量 sandbox。

注意：如果使用 Codex CLI 的宽权限参数，必须在 UI 和日志中明确标注“高信任运行模式”，并限制默认工作目录，避免误写系统路径。

---

## 8. 任务书模型

### 8.1 任务书定位

任务书是用户、调度器和 Agent 之间的执行契约。它既不是纯 prompt，也不是完全僵硬的代码流程，而是自然语言目标与结构化约束的组合。

### 8.2 最小可用 schema

```yaml
taskbook_version: 1
title: 老系统登录模块逆向与需求整理
objective: 输出登录模块功能说明、接口清单、数据库依赖和需求文档

runtime:
  scheduler: hermes
  timeout_seconds: 3600
  correction_policy: append_rules_and_rerun_failed_steps

agents:
  - id: niuma-1
    role: reverse-engineering
  - id: niuma-2
    role: requirements-writer

steps:
  - id: reverse-login
    agent: niuma-1
    objective: 分析 legacy/login 目录，输出功能清单
    inputs:
      - path: shared/references/legacy-login/
    outputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
    timeout_seconds: 1800
    self_check:
      - 必须列出入口 JSP
      - 必须列出相关 SQL
      - 必须说明异常分支

  - id: write-requirements
    agent: niuma-2
    depends_on:
      - reverse-login
    objective: 读取逆向产物，生成需求文档
    inputs:
      - path: artifacts/runs/{run_id}/reverse-login/function-list.md
    outputs:
      - path: artifacts/runs/{run_id}/write-requirements/requirements.md
    self_check:
      - 必须包含业务流程
      - 必须包含字段说明
      - 必须包含验收标准

constraints:
  - 不得修改 shared/references 下的源文件
  - 所有产物必须写入 artifacts/runs/{run_id}
  - 不确定的信息必须标注“待确认”
```

### 8.3 执行语义

- 调度器读取任务书，创建 PipelineRun。
- ResourceManager 锁定所需 Agent。
- 每个 step 生成一次 AgentTask。
- Agent 执行前读取 step objective、inputs、outputs、constraints、self_check。
- step 完成后写入 result、events、self_check_report。
- 下游 step 只能读取已完成 step 的 declared outputs。
- 用户修正会追加为 correction，并触发失败 step 或指定 step 重跑。

---

## 9. 调度与资源管理

### 9.1 ResourceManager 职责

- 注册 Agent。
- 记录 Agent 心跳和健康状态。
- 管理 Agent lease。
- 防止多个调度器抢占同一 Agent。
- 提供资源查询 API。
- 持久化当前 run、step、worker 状态。

### 9.2 核心数据表建议

| 表 | 用途 |
|---|---|
| agents | Agent 静态信息和能力标签 |
| agent_state | Agent 当前状态、当前任务、心跳 |
| leases | 调度锁，避免重复派工 |
| pipeline_runs | 每次任务书运行实例 |
| step_runs | 每个步骤的状态、依赖、产物 |
| messages | Agent/调度器消息 |
| artifacts | 产物索引 |
| events | 可查询事件，原始 jsonl 仍保留 |

### 9.3 调度策略

V1 使用保守调度：

- 每个 Agent 同时只跑一个任务。
- 依赖满足后才派发下游 step。
- 失败时停止相关下游 step。
- 用户确认后可重跑失败 step。

V2 增加：

- 按标签自动选择 Agent。
- 超时转移。
- 优先级队列。
- 多调度器协作。
- 成本和模型能力策略。

---

## 10. 配置治理与 marvisctl

当系统扩展到 20 个以上 Agent 时，配置复杂度不能由用户手工维护 JSON/YAML 承担。Marvis 必须提供一套配置治理能力，把 Agent 模板、模型配置、技能安装、运行诊断和任务书校验统一起来。

### 10.1 配置分层

Agent 配置应采用继承和覆盖模型：

```text
全局默认配置
  -> group/template 配置
    -> agent 个体覆盖
      -> run 临时覆盖
```

示例：

```yaml
defaults:
  backend_type: codex_cli
  base_url: http://127.0.0.1:38440/v1
  timeout_seconds: 1800

templates:
  reverse-engineer:
    model: deepseek-v4-pro
    role: 老系统逆向分析工位
    tags:
      - jsp
      - sql
      - reverse-engineering
    skills:
      - jsp-reverse-engineering
      - sql-analysis

  requirements-writer:
    model: deepseek-v4-pro
    role: 需求文档撰写工位
    tags:
      - requirements
      - documentation
    skills:
      - requirements-doc-writer

agents:
  niuma-1:
    extends: reverse-engineer
    display_name: 牛马1
    api_key_env: NIUMA_1_API_KEY

  niuma-2:
    extends: requirements-writer
    display_name: 牛马2
    api_key_env: NIUMA_2_API_KEY
```

这样新增 Agent 不需要复制整段配置，只需要声明它继承哪个模板，并覆盖少量差异字段。

### 10.2 marvisctl 定位

`marvisctl` 是 Marvis 的命令行运维入口，负责配置治理、健康检查、批量 Agent 管理、任务书校验、任务运行和合规测试。

它不是可选工具，而是 20+ Agent 规模下的基础设施。

### 10.3 marvisctl 命令草案

```powershell
marvisctl doctor
marvisctl config validate
marvisctl config render niuma-1

marvisctl agent list
marvisctl agent show niuma-1
marvisctl agent create niuma-3 --from reverse-engineer --model deepseek-v4-pro
marvisctl agent clone niuma-1 niuma-7
marvisctl agent check --all
marvisctl agent install-skill niuma-1 jsp-reverse-engineering

marvisctl taskbook lint taskbooks/login.yml
marvisctl taskbook dry-run taskbooks/login.yml

marvisctl run start taskbooks/login.yml
marvisctl run status run-001
marvisctl run logs run-001
marvisctl artifact list run-001

marvisctl compliance run --suite taskbook
marvisctl compliance run --suite taskbook --backend codex_cli --model deepseek-v4-pro
marvisctl compliance run --suite taskbook --prompt-template v3
```

### 10.4 marvisctl P0 能力

P0 阶段至少需要：

- `doctor`：检查 Python、Codex CLI、Moon Bridge、API key、模型、workspace 权限。
- `config validate`：检查配置语法、路径冲突、重复 Agent ID、缺失环境变量。
- `config render <agent>`：显示继承后的最终 Agent 配置。
- `agent list/check`：查看 Agent 状态并执行健康检查。
- `taskbook lint`：静态检查任务书字段、依赖、产物路径、约束。
- `taskbook dry-run`：不调用模型，只验证调度计划和资源锁定。
- `compliance run`：运行任务书合规测试集。

---

## 11. Taskbook Compliance 验厂测试集

Marvis 必须建立 `taskbook-compliance` 测试集。每次更换模型、后端、prompt 模板、Codex CLI 参数或任务书执行器时，都应先跑合规测试，避免系统表面可运行但实际破坏任务契约。

Compliance 测试集是 Marvis 的真正护城河之一。多数 Agent 产品会先做调度、聊天、UI 和模型接入，但很少把“任务书契约是否被不同模型稳定遵守”做成系统化测试资产。Marvis 应趁早把这件事做出来，让每个场景、每个模型、每个 prompt 模板的能力边界都可验证、可回归、可比较。

对旧系统改造场景来说，Compliance 不是测试附属品，而是产品信任的来源：企业用户不只关心 Agent 能不能回答，更关心它是否按任务书读取输入、写入指定产物、不越权修改源文件、失败后可解释、修正后可重跑。

### 11.1 测试目标

合规测试不评价回答是否华丽，而是验证 Agent 是否遵守任务书契约：

- 是否读取了声明的 input。
- 是否写入了声明的 output。
- 是否没有修改 forbidden path。
- 是否按依赖顺序执行。
- 是否在依赖未满足时进入 waiting/blocked。
- 是否生成 self_check_report。
- 是否能处理用户 correction。
- 是否能在服务重启后恢复 run/step 状态。
- 是否能在不同模型和 prompt 模板下保持最低合规行为。

### 11.2 测试集结构

```text
tests/compliance/
  fixtures/
    legacy-login/
    tiny-python-project/
    readonly-reference/
  taskbooks/
    valid-two-agent-chain.yml
    missing-input.yml
    forbidden-write.yml
    correction-loop.yml
    restart-recovery.yml
  expected/
    valid-two-agent-chain.assert.yml
    missing-input.assert.yml
    forbidden-write.assert.yml
```

### 11.3 测试模式

```text
quick compliance
- 使用 mock backend
- 不调用真实模型
- 每次提交都可以跑
- 验证任务书解析、调度、状态、权限、产物索引

model compliance
- 使用真实 Codex CLI / Moon Bridge / DeepSeek
- 换模型、换 prompt 模板、发布前运行
- 验证真实 Agent 是否遵守任务书和文件产物契约
```

### 11.4 断言方式

合规测试应优先使用确定性断言：

```yaml
assert:
  run_status: succeeded
  steps:
    reverse-login:
      status: succeeded
      output_exists:
        - artifacts/runs/{run_id}/reverse-login/function-list.md
      forbidden_modified:
        - shared/references/legacy-login/login.jsp
    write-requirements:
      status: succeeded
      depends_after:
        - reverse-login
      output_contains:
        path: artifacts/runs/{run_id}/write-requirements/requirements.md
        terms:
          - 登录
          - 验收标准
```

LLM judge 可以作为辅助，但不能作为唯一验收标准。核心契约必须通过路径、状态、事件、产物和结构化内容断言来验证。

### 11.5 上线规则

以下变化必须先通过 `taskbook-compliance`：

- 新模型上线。
- 新 Moon Bridge 或中转站配置。
- 新 prompt 模板。
- 新 Agent template。
- 新 backend type。
- 新权限策略。
- 任务书执行器改造。

这套测试集是 Marvis 的“验厂流程”。没有验厂，不能把新模型或新模板投入正式流水线。

---

## 12. 消息总线

### 12.1 消息类型

| 类型 | 说明 |
|---|---|
| dispatch | 派发任务 |
| accepted | Agent 接受任务 |
| progress | 动作级进度 |
| artifact_ready | 产物已生成 |
| dependency_ready | 依赖可用 |
| report | 任务汇报 |
| error | 错误报告 |
| ask_user | 请求用户确认 |
| correction | 用户修正要求 |

### 12.2 消息格式

```json
{
  "message_id": "msg-001",
  "run_id": "run-20260527-001",
  "step_id": "reverse-login",
  "from": "niuma-1",
  "to": "scheduler",
  "type": "progress",
  "created_at": "2026-05-27T10:00:00+08:00",
  "payload": {
    "text": "正在分析 login.jsp",
    "percent": 35,
    "current_file": "legacy/login/login.jsp"
  }
}
```

V1 可以先由 API Server 中转；V2 再支持 Agent 之间直接订阅和发送。

---

## 13. 日志、状态与恢复

### 13.1 事件日志

每个 run 必须有 append-only jsonl：

```json
{"ts":"2026-05-27T10:00:00+08:00","type":"step_started","agent":"niuma-1","step":"reverse-login"}
{"ts":"2026-05-27T10:01:12+08:00","type":"file_written","agent":"niuma-1","path":"artifacts/runs/run-001/reverse-login/function-list.md"}
{"ts":"2026-05-27T10:02:40+08:00","type":"self_check_passed","agent":"niuma-1","step":"reverse-login"}
```

### 13.2 Agent state.yaml

每个 Agent 保留轻量状态文件：

```yaml
agent_id: niuma-1
status: running
current_run_id: run-20260527-001
current_step_id: reverse-login
last_event_at: 2026-05-27T10:02:40+08:00
last_artifact:
  path: artifacts/runs/run-001/reverse-login/function-list.md
```

### 13.3 恢复策略

- API Server 启动时读取 SQLite。
- 对 running/reserved 状态做 reconcile。
- 检查 Agent 进程是否仍存在。
- 检查 step declared outputs 是否存在。
- 无法确认的任务标记为 blocked，等待用户处理。

---

## 14. UI 产品设计

### 14.1 信息架构

| 页面 | 目标 |
|---|---|
| 总控台 | 看全局资源、正在运行的流水线、失败任务 |
| 流水线视图 | 看每个任务书的步骤、依赖、进度、产物 |
| 工位中心 | 管理 Agent、模型、标签、技能、健康状态 |
| 任务书编辑器 | 创建、校验、保存、下发任务书 |
| 产物库 | 浏览每个 run 的文件、报告、补丁、日志 |
| 日志审计 | 查看事件流、错误、重试、用户修正 |
| 设置 | 配置模型、Moon Bridge、token、路径、权限模式 |

### 14.2 视觉方向

- 机械工业控制台风格。
- 密集但清晰，优先信息扫描。
- 状态灯、表格、时间线、工位卡、日志面板。
- 少动画或无动画。
- 重点突出“正在做什么”和“产物在哪里”。

### 14.3 首页布局建议

第一屏直接进入总控台：

```text
+-------------------------------------------------------+
| Marvis AI Factory           运行中 2   空闲 4   异常 1 |
+-------------------+-----------------------------------+
| 工位中心           | 当前流水线                         |
| niuma-1 running    | 登录模块逆向     step 1/3           |
| niuma-2 idle       | 需求文档生成     waiting            |
| niuma-3 blocked    |                                   |
+-------------------+-----------------------------------+
| 事件流                                                |
| 10:00 niuma-1 started reverse-login                   |
| 10:01 niuma-1 wrote function-list.md                  |
+-------------------------------------------------------+
```

### 14.4 关键 UI 状态

- 空闲：可派工。
- 运行中：显示当前动作和耗时。
- 等待中：显示等待哪个依赖。
- 阻塞：显示错误原因和建议操作。
- 完成：显示产物入口和自检结果。

---

## 15. MVP 路线

### P0：从 demo 变成可靠运行时

1. SQLite ResourceManager。
2. TaskBook YAML loader 和基础校验。
3. PipelineRun/StepRun 数据模型。
4. append-only event log。
5. Agent workspace 规范化。
6. Codex/Moon Bridge 健康检查。
7. 配置继承模型：defaults/template/agent/run。
8. `marvisctl doctor/config/agent/taskbook` 最小命令集。
9. `taskbook-compliance` quick suite。
10. UI 显示 run、step、artifact、event。

验收标准：

- 可以创建一份任务书。
- 可以锁定两个 niuma。
- niuma-1 生成文件，niuma-2 读取并生成下游文件。
- 服务重启后仍能看到 run 状态和产物。
- 失败任务能显示错误原因。
- `marvisctl doctor` 可以发现缺失模型、API key、workspace 权限问题。
- `marvisctl taskbook lint` 可以提前发现任务书字段和依赖错误。
- quick compliance 可以在不调用真实模型的情况下验证调度契约。

### P1：从可靠运行时变成工厂操作台

1. 工位中心：标签、分组、模型、技能、健康状态。
2. 流水线视图：步骤依赖、等待、运行、失败、完成。
3. 用户修正闭环。
4. 消息总线持久化。
5. 失败 step 重跑。
6. 产物库和日志审计。
7. `taskbook-compliance` model suite。
8. Agent template 管理和批量克隆。

验收标准：

- 用户可以从 UI 下发任务书。
- 用户可以看见动作级进度。
- 用户可以对失败 step 追加修正并重跑。
- 每个产物能追溯到 Agent、step、时间和输入。
- 新模型或新 prompt 模板上线前，可以先跑 model compliance。

### P2：从单机工厂变成可扩展平台

1. 多调度器协作。
2. Agent 自动选择。
3. 子 Agent 递归创建。
4. OS/容器级隔离。
5. MCP/A2A 集成。
6. 成本、token、性能指标。
7. 插件化技能市场。

---

## 16. 架构风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 宽权限执行导致误写文件 | 高 | 默认限制 workspace，UI 标注高信任模式，后续引入 sandbox |
| 多进程 Agent 成本高 | 中 | 限制并发、队列化、按需启动 |
| 20+ Agent 配置失控 | 高 | 配置继承、模板化、marvisctl validate/render、UI 工位中心 |
| 换模型或 prompt 后行为退化 | 高 | taskbook-compliance quick/model 双测试集 |
| LLM 不严格遵守任务书 | 高 | 结构化 prompt、自检清单、产物校验、失败重跑 |
| 任务状态丢失 | 高 | SQLite + append-only event log + state.yaml |
| UI 变成复杂低代码平台 | 中 | 以任务书和工位为中心，少做节点画布 |
| 模型/中转站协议不兼容 | 中 | 后端适配层、健康检查、明确模型能力 |
| Agent 之间互相污染产物 | 中 | 路径权限、artifact 声明、只读 peer workspace |

---

## 17. 当前项目下一步建议

建议不要先大改 UI，也不要先扩展更多模型后端。下一步应先做 P0 的运行时内核：

1. 新增 `core/resource_manager.py`，用 SQLite 管理 Agent、lease、run、step。
2. 新增 `core/taskbook.py`，支持 YAML 任务书加载和校验。
3. 新增 `core/event_log.py`，统一写入 run 级 jsonl 事件。
4. 改造 `core/task_bus.py`，让内存状态变成 ResourceManager 的运行缓存。
5. 新增 `core/config_registry.py`，支持 defaults/template/agent/run 配置合并。
6. 新增 `marvisctl.py`，先实现 doctor、config validate、agent list/check、taskbook lint。
7. 新增 `tests/compliance/`，先实现 quick compliance。
8. 新增 API：`/api/pipelines`、`/api/runs`、`/api/events`、`/api/artifacts`。
9. UI 先补一个最小流水线视图，不做复杂节点画布。

第一阶段完成后，Marvis 就会从“可以派工的多 Agent demo”升级为“有状态、有产物、有审计、有恢复能力的 AI 工厂操作台”。

---

## 18. P0 工程拆解

P0 的目标不是一次性做完整平台，而是把当前 demo 改造成一个可靠的单机运行时。每个任务都应该能独立测试、独立提交、独立回滚。

### M1：配置注册表 ConfigRegistry

目标：让 20+ Agent 的配置不再靠复制粘贴维护。

新增模块：

- `core/config_registry.py`
- `tests/test_config_registry.py`

能力：

- 加载 defaults/template/agent/run 四层配置。
- 支持 `extends` 继承。
- 检测重复 agent_id。
- 检测缺失 api_key_env。
- 渲染单个 Agent 的最终配置。

验收：

- `render_agent("niuma-1")` 返回合并后的完整配置。
- template 修改后，继承它的 Agent 自动生效。
- 配置冲突时返回明确错误。

### M2：SQLite ResourceManager

目标：把 worker 状态、资源锁和 pipeline 状态从内存搬到持久层。

新增模块：

- `core/resource_manager.py`
- `tests/test_resource_manager.py`

核心对象：

- AgentRecord
- AgentState
- Lease
- PipelineRun
- StepRun

能力：

- 注册 Agent。
- 查询空闲 Agent。
- 创建/释放 lease。
- 记录 run/step 状态。
- 服务重启后恢复状态。

验收：

- 同一个 Agent 不能被两个 run 同时锁定。
- 重启后能读回未完成 run。
- stuck lease 可以被标记为 blocked 或释放。

### M3：事件日志 EventLog

目标：让每个动作都可审计、可回放、可在 UI 实时显示。

新增模块：

- `core/event_log.py`
- `tests/test_event_log.py`

能力：

- 写入 append-only jsonl。
- 支持 run 级事件流。
- 支持按 run_id、agent_id、step_id 过滤。
- 同步写入 SQLite 事件索引。

事件类型：

- run_created
- step_started
- agent_progress
- artifact_written
- self_check_passed
- step_failed
- run_finished

验收：

- 多次写入不会覆盖旧事件。
- UI 可以从 API 读取事件流。
- 失败事件必须包含 error message 和 traceback 摘要。

### M4：TaskBook Loader 与 Linter

目标：把任务书变成可校验的执行契约。

新增模块：

- `core/taskbook.py`
- `tests/test_taskbook.py`

能力：

- 加载 YAML 任务书。
- 校验必填字段。
- 校验 step id 唯一。
- 校验 depends_on 引用存在。
- 校验 output path 不越权。
- 生成执行计划。

验收：

- 合法任务书能生成 DAG。
- 循环依赖会报错。
- 缺失产物声明会报错。
- forbidden path 会被 lint 拦截。

### M5：Pipeline Executor

目标：让任务书可以驱动多个 Agent 顺序/并行执行。

新增模块：

- `core/pipeline_executor.py`
- `tests/test_pipeline_executor.py`

能力：

- 创建 PipelineRun。
- 按依赖调度 StepRun。
- 调用现有 worker backend 执行 step prompt。
- 将 outputs 写入 artifact index。
- step 失败后阻断下游。

验收：

- niuma-1 完成后，niuma-2 可以读取 niuma-1 declared output。
- 依赖未满足时，下游 step 不会启动。
- step 失败时 run 进入 failed 或 blocked。

### M6：marvisctl 最小 CLI

目标：提供工程师可用的本地操作入口。

新增入口：

- `marvisctl.py`
- `tests/test_marvisctl.py`

P0 命令：

```powershell
python marvisctl.py doctor
python marvisctl.py config validate
python marvisctl.py config render niuma-1
python marvisctl.py agent list
python marvisctl.py agent check --all
python marvisctl.py taskbook lint taskbooks/demo.yml
python marvisctl.py taskbook dry-run taskbooks/demo.yml
```

验收：

- 命令返回非零退出码表示失败。
- 错误信息面向用户可读。
- 不打印 API key。

### M7：Taskbook Compliance Quick Suite

目标：每次改调度器、prompt 模板、配置模型前，先跑不调用真实模型的合规测试。

新增目录：

```text
tests/compliance/
  fixtures/
  taskbooks/
  expected/
```

P0 用 mock backend 验证：

- 配置合并正确。
- 任务书 lint 正确。
- ResourceManager lease 正确。
- step 依赖顺序正确。
- artifact index 正确。
- forbidden path 被拦截。

验收：

- `python marvisctl.py compliance run --suite taskbook --mode quick` 可运行。
- quick suite 不依赖真实 API key。
- 任一契约破坏都会失败。

### M8：API 扩展

目标：让 UI 能读取 pipeline、event、artifact 状态。

新增或扩展接口：

- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/runs/{run_id}/artifacts`
- `POST /api/taskbooks/lint`
- `POST /api/runs`

验收：

- 所有接口继续使用 Hermes token。
- API 不泄露真实 API key。
- run/event/artifact 的返回结构稳定，供 UI 直接消费。

### M9：最小流水线 UI

目标：让用户不看命令行也能理解“谁在干什么、做到哪一步、产物在哪里”。

页面能力：

- 展示 run 列表。
- 展示 step 状态。
- 展示 Agent 当前动作。
- 展示事件流。
- 展示产物链接。
- 展示失败原因。

验收：

- 一个两 Agent 任务能在 UI 上看到完整执行链路。
- 失败 step 能看到错误和日志入口。
- 产物可以从 UI 打开。

### 推荐实施顺序

```text
M1 ConfigRegistry
  -> M2 ResourceManager
  -> M3 EventLog
  -> M4 TaskBook
  -> M5 Pipeline Executor
  -> M6 marvisctl
  -> M7 Compliance Quick Suite
  -> M8 API
  -> M9 UI
```

其中 M1-M4 是内核地基，M5-M7 是运行时闭环，M8-M9 是产品可见性。
