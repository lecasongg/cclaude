# 牛马团队 · Claude CLI 化改造评审包

> 版本：v1 草案 · 日期：2026-05-26 · 状态：**待技术评审**

## 一句话

把现有 `niuma-*` worker 从「一次性 chat completion」升级为「每人一个独立的 Claude Code agent 进程」，让它们具备真正的工具调用、工作区、技能与子任务能力，由本会话作为 Hermes 工头统一调度。

## 这个包里有什么

| 文件 | 给谁看 | 内容 |
|---|---|---|
| `00-for-codex.md` | **接手的 agent**（Codex / Claude / 其他 LLM） | Agent 入口指令：clone 哪个分支、跑什么基线、怎么按计划执行、何时停下问 |
| `README.md` | 所有人 | 你在看的这份 · 索引 + 决策摘要 |
| `01-spec.md` | 架构 / 技术负责人 | 完整设计规约：目标、架构、协议、数据流、风险 |
| `02-implementation-plan.md` | 落地工程师 / agent 执行者 | 任务级实施计划：每个任务的文件、代码、测试、提交 |
| `03-review-checklist.md` | 评审人 | 验收清单：架构 / 安全 / 兼容 / 性能 / 可观测 5 维 |
| `04-cost-and-rollout.md` | 决策者 / 项目经理 | 成本估算、灰度方案、回滚预案 |
| `skeleton/` | 工程师 | 可直接 copy 的骨架代码与配置范例 |
| `diagrams/` | 所有人 | ASCII 架构图、时序图 |

## 决策摘要

**问题**：当前 `OpenAICompatibleWorkerBackend` 把 niuma worker 退化成纯文本生成器——无工具、无文件读写、无多轮规划、无失败重试。链式派工时还会泄漏 niuma-1 的任务手册给 niuma-2（已通过 [7f00973](../../core/supervisor.py) 修复，但只是治标）。

**方案**：每个 `niuma-*` 改为由 Hermes 拉起的独立 `claude -p` 子进程，拥有：
- `profiles/niuma-N/` — 独立的 `MEMORY.md`、技能、MCP、对话历史
- `workspaces/niuma-N/` — 独立的 cwd，文件读写隔离
- `skills/niuma-N/` — 专属技能目录（如 niuma-1 装「JSP 逆向」技能）
- 完整的 Claude Code 工具集（Read/Write/Edit/Bash/Grep/Glob/Task/...）

**保留多模型可能性**：`WorkerBackend` 协议化，B 方案 `ClaudeCliWorkerBackend` 与 C 方案 `OpenAICompatibleWorkerBackend` 共存。未来想给某个 niuma 接 DeepSeek/GPT，只改 `WorkerConfig.backend_type`，不动 Hermes。

**链式派工质变**：从「拼 prompt 传给下一个」变为「niuma-2 直接 `Read('../niuma-1/output/xxx.md')`」——文件级握手，零信息丢失，零文档泄漏。

## 不在本提案范围

- 模型选型决策（默认 Claude Sonnet，可后续单独评审）
- Web Console 改版（保留现状，仅可能加 niuma 工作区文件浏览）
- Anthropic API 计费与订阅模式选型（见 `04-cost-and-rollout.md` 数据，决策另议）
- 现有 `niuma-1` / `niuma-2` 已安装文档（task_manual / conversion_rules）的迁移路径 — 在 `02` 的 Task 7 处理

## 关键风险（详见 `01-spec.md` §10）

1. **进程管理复杂度**：subprocess + stream-json + timeout + kill — 比 HTTP 调用难写难调
2. **claude CLI 依赖**：需要在服务器上预装 `claude` 命令并配置 Anthropic 凭据
3. **成本不确定**：取决于 Claude API 计费 vs Max 订阅，见 `04`
4. **回退路径**：保留 C 方案 backend 不删，故障时可快速切回

## 评审建议

**人类评审者**：
1. 先读 `01-spec.md` 第 1-4 节（目标、架构、协议、数据流）
2. 看 `diagrams/` 里的两张图
3. 抽样翻 `02-implementation-plan.md` 任意一个 Task，看任务粒度是否合理
4. 用 `03-review-checklist.md` 走一遍验收维度
5. 看 `04-cost-and-rollout.md` 的成本表和灰度方案

预计评审时间 30-45 分钟。

**Agent 接手者（Codex / Claude / 其他 LLM）**：
直接从 `00-for-codex.md` 开始，里面有 clone 指令、基线自检、阅读顺序、停下问的条件。
