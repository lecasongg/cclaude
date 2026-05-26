# 成本与灰度方案

## 1 · 单任务成本估算

### 假设
- niuma-1 工作量：读 5 个 JSP 文件（约 30K token） → 10 轮工具调用 → 输出 8K token Markdown
- niuma-2 工作量：读 niuma-1 的 result.md（10K token） → 5 轮工具调用 → 输出 5K token Markdown

### 三种成本模式

| 方案 | niuma-1 单价 | niuma-2 单价 | chain 单次 | 100 次/天月成本 |
|---|---|---|---|---|
| **现状（DeepSeek 直连）** | ¥0.03 | ¥0.05 | ¥0.08 | ¥240 |
| **B 方案 + Claude Sonnet API 按量** | ¥1.20 | ¥0.80 | ¥2.00 | ¥6000 |
| **B 方案 + Claude Opus API 按量** | ¥6.00 | ¥4.00 | ¥10.00 | ¥30000 |
| **B 方案 + Claude Max 订阅** | 订阅内 | 订阅内 | ¥0 | $200 / 月固定（≈ ¥1500） |

> **关键**：如果使用 Claude Max 订阅模式，团队规模扩大后单任务边际成本为 0。

### 隐性成本对比

| 项 | 现状 | B 方案 |
|---|---|---|
| 单次任务时长 | 10-30 秒 | 1-5 分钟（多轮工具调用） |
| 失败率 | 高（编造内容、漏步骤） | 低（真读真写，TodoWrite 追踪） |
| 重跑率 | 经常需要人工纠正后重跑 | 低 |
| **有效产物率** | 估 30%（剩下要修） | 估 85% |
| **实际单"可用产物"成本** | ¥0.08 / 0.30 = ¥0.27 | ¥2 / 0.85 = ¥2.35 |

按可用产物折算，B 方案是现状的 **8-9 倍贵**，但**产物质量与工作流真实性是质变**。

---

## 2 · 灰度方案

### 阶段 0：准备（D-day 前 1 周）
- 服务器装 `claude` CLI 并完成登录
- 准备一份 niuma-1 专属的 `task_manual` 改写版（移除关于"执行 openpyxl"的具体步骤，因为 niuma-1 现在真的能跑代码了）
- 在测试环境跑通 Task 9 端到端

### 阶段 1：单 niuma 灰度（第 1 周）
- 仅 niuma-1 切到 `claude_cli`，niuma-2 保持 `openai_compatible`
- 监控指标：
  - 任务成功率（目标 ≥ 95%）
  - 平均时长（目标 ≤ 5 分钟）
  - 日均成本（核对预算）
- 任一指标连续 3 天恶化 → 回滚

### 阶段 2：双 niuma 灰度（第 2 周）
- niuma-2 也切到 `claude_cli`
- 跑通完整 chain 流程
- 同时验证文件级握手有效（niuma-2 不再 inline 上游内容）

### 阶段 3：稳定运行（第 3 周+）
- 监控指标稳定后，删除旧 `task_manual` / `conversion_rules` 已安装文档
- 改为通过 `skills/niuma-1/` 注入专属技能
- 评估是否要加 niuma-3（不同模型）扩团队

---

## 3 · 回滚预案

### 触发条件
- 任一 niuma 连续 5 次任务失败
- 单日 API 成本超过预算 2 倍
- Claude API 限流 / 5xx > 10%

### 操作步骤（目标：< 5 分钟）

1. 编辑 `factory_config.json`，把目标 niuma 的 `backend_type` 改回 `openai_compatible`
2. `taskkill /F /PID <worker_server pid>`
3. `python serve.py`
4. 验证 `/api/health` 返回 200，且任务派工恢复

### 回滚后排查

artifact 保留：`artifacts/niuma-N/task-xxx/` 仍可读
events 保留：`artifacts/niuma-N/task-xxx/events.jsonl` 用于事后分析

---

## 4 · 决策矩阵

| 计费模式 | 适用场景 | 推荐？ |
|---|---|---|
| Anthropic API 按 token 计费 | 任务量不稳定 / 试运行 / < 30 任务/天 | ✅ 起步 |
| Anthropic Claude Max 订阅 | 任务量稳定 ≥ 30/天 / 团队多人 / 长期运行 | ✅ 稳定期 |
| 完全不切 B 方案 | 只要文档生成，质量可接受，预算极紧 | ❌（已知质量瓶颈） |
| 自建 ReAct loop + DeepSeek | 团队有 Python 工程能力且模型混搭是硬需求 | 待评估，可作为 niuma-3 路径 |

---

## 5 · 关键问题（请决策者明确回答）

- [ ] **Q1** 是否同意进入"阶段 1"灰度（仅 niuma-1）？目标日期：__________
- [ ] **Q2** 同意采用哪种计费模式？☐ 按 token ☐ Max 订阅 ☐ 先 token 后看量再切
- [ ] **Q3** 月预算上限：__________ 元
- [ ] **Q4** 出现成本超支时，是否同意自动暂停 niuma 接受新任务（需开发熔断逻辑）？
- [ ] **Q5** 灰度期是否需要每日成本日报推送（飞书 / 邮件 / Console 看板）？
