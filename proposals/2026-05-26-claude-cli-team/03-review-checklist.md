# 评审清单

> 评审人：在每项后面打 ✅ / ❌ / N/A 并写一行评论。预计 30 分钟跑完。

## A · 架构合理性

- [ ] **A1** 是否复用了现有 `WorkerBackend` 协议而非另起一套？
- [ ] **A2** `WorkerConfig` 新增字段是否完全后向兼容（旧 config 不改动也能跑）？
- [ ] **A3** Hermes 调度层（FastAPI / TaskBus / ArtifactStore）是否完全无改动？
- [ ] **A4** 链式派工的文件级握手是否解决了上下文泄漏 + 大产物截断两个问题？
- [ ] **A5** 是否给未来的 DeepSeek/GPT 接入留好扩展点（`backend_type` + 工厂）？

## B · 安全

- [ ] **B1** 每个 niuma 的 `CLAUDE_CONFIG_DIR` 是否真的隔离（不同 niuma 不共享 MEMORY / 凭据）？
- [ ] **B2** 是否避免了把 API key 写入 `factory_config.json`（必须走 env / runtime_config）？
- [ ] **B3** 文件系统隔离的边界是否明确说明（niuma 通过 Bash 可越界，是已知妥协）？
- [ ] **B4** `--permission-mode` 的默认值是否合理（建议 acceptEdits）？
- [ ] **B5** subprocess 超时是否有强 kill 路径，不会留僵尸？

## C · 兼容与回滚

- [ ] **C1** 默认 `backend_type` 是否能让现有 niuma-1 / niuma-2 零改动继续工作？
- [ ] **C2** 单 niuma 灰度切换的步骤是否清晰（Task 9）？
- [ ] **C3** 出问题时回滚到 `openai_compatible` 是否真的只需改 1 个字段 + 重启？
- [ ] **C4** 老 backend（OpenAICompatibleWorkerBackend / SubprocessWorkerBackend）是否保留并仍受测试覆盖？
- [ ] **C5** Console 前端是否完全不需要改？

## D · 性能与成本

- [ ] **D1** subprocess 启动开销在端到端任务时延中占比是否可接受（任务通常几十秒，开销几百毫秒）？
- [ ] **D2** 多 niuma 并发时是否有连接数 / 文件句柄上限风险？
- [ ] **D3** Claude API 计费模式是否在 `04-cost-and-rollout.md` 写清并给出灰度建议？
- [ ] **D4** 上下文泄漏修复后 niuma-2 的输入 token 是否真的降下来（手测验证）？
- [ ] **D5** 是否记录单任务的 input/output tokens 与 cost（供后续成本审计）？

## E · 可观测性

- [ ] **E1** 单 niuma 任务失败时，错误信息是否能让人定位是 CLI 没装 / 凭据错 / 超时 / 工具调用错？
- [ ] **E2** stream-json events 是否落盘（artifacts/niuma-N/task-xxx/events.jsonl），供后续回放？
- [ ] **E3** health endpoint 是否能反映 `claude --version` 自检结果？
- [ ] **E4** 链式派工中失败发生在哪一段（source / target）是否清晰可区分？

## F · 测试

- [ ] **F1** pytest 39 → 50 个，全绿？
- [ ] **F2** `ClaudeCliWorkerBackend` 是否有正常 / 失败 / 超时三种用例覆盖？
- [ ] **F3** 文件级握手是否有"内容不再 inline，但路径被引用"的回归测试？
- [ ] **F4** 工厂的未知 backend_type 是否有清晰的 BackendError？
- [ ] **F5** Windows-specific 的 mklink fallback 是否有显式测试或在文档中说明？

## G · 文档与运维

- [ ] **G1** RUNBOOK 是否能让一个新工程师 30 分钟内启动整个系统？
- [ ] **G2** `factory_config.example.json` 是否同时含 claude_cli 和 openai_compatible 两种范例？
- [ ] **G3** "灰度方案" 是否能让运维敢按方案做切换？
- [ ] **G4** 风险登记（spec §10）是否覆盖了运维实际可能踩的坑（CLI 未装 / 凭据缺失 / Windows 符号链接权限）？

---

## 重大决策清单（必须由架构师签字）

- [ ] **D-1** 同意把 niuma 子进程模式作为 niuma-1/niuma-2 的默认 backend
- [ ] **D-2** 同意保留 `OpenAICompatibleWorkerBackend` 作为可选回退，不删
- [ ] **D-3** 同意 `--permission-mode acceptEdits` 作为默认（不需额外 ask）
- [ ] **D-4** 同意每个 niuma 单独走 Anthropic 凭据，不共享
- [ ] **D-5** 同意 niuma 进程**临时启动 / 一次性使用**（非常驻）的设计

---

## 我个人最在意的三件事（reviewer 着重看）

1. **Task 3 `ClaudeCliWorkerBackend` 的实现是否健壮**——这是新代码的主战场，单测必须扎实
2. **Task 6 chain 文件级握手**——这是真正解决 niuma-2 上下文污染的根本方案，断言要严
3. **Task 9 灰度切换**——上线第一周如果出问题，回滚必须真能秒级生效
