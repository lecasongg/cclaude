# 本地 Agent 工厂试运行说明

## 启动 Worker Server

在 PowerShell 里运行：

```powershell
cd D:\codex\cclaude
copy factory_config.example.json factory_config.json
python serve.py
```

默认地址：`http://127.0.0.1:8846`
默认 token：`local-token`

如果 8846 端口被占用，复制一份配置改 `server.port`，再指定配置路径启动：

```powershell
$env:CCLAUDE_CONFIG_PATH="D:\codex\cclaude\factory_config.local.json"
python serve.py
```

## 打开监控大屏

浏览器访问：

```text
http://127.0.0.1:8846/
```

## 启动常驻 Hermes 主管

另开一个 PowerShell：

```powershell
cd D:\codex\cclaude
python hermes_supervisor.py http://127.0.0.1:8846 local-token
```

进入后会看到：

```text
Hermes>
```

可输入：

```text
workers
delegate niuma-1 分析 JSP 文件，输出需求清单
chain niuma-1 niuma-2 逆向分析 JSP => 根据上游清单编写需求文档
exit
```

仍然可以用一次性命令：

```powershell
python hermes_supervisor.py http://127.0.0.1:8846 local-token workers
python hermes_supervisor.py http://127.0.0.1:8846 local-token delegate niuma-1 "分析这个 JSP 项目，输出需求清单"
python hermes_supervisor.py http://127.0.0.1:8846 local-token chain niuma-1 niuma-2 "逆向分析 JSP" "根据上游清单编写需求文档"
```

## 当前试运行模式

`python serve.py` 会按顺序选择配置文件：

```text
factory_config.json → factory_config.example.json → config.example.json
```

推荐复制 `factory_config.example.json` 为本地 `factory_config.json` 后修改；默认示例使用 `claude_cli` backend。旧 `config.example.json` 仍可用于 OpenAI 兼容回退。

试运行前确认：

```powershell
claude.cmd --version
$env:NIUMA_1_API_KEY="你的 niuma-1 中转站 Key"
$env:NIUMA_2_API_KEY="你的 niuma-2 中转站 Key"
```

`claude_cli` backend 会在启动 Claude CLI 子进程时，把当前 worker 的 `api_key_env` 映射为 `ANTHROPIC_API_KEY`，把 `base_url` 映射为 `ANTHROPIC_BASE_URL`。因此使用 Anthropic-compatible 中转站时，在 `factory_config.json` 里给每个 niuma 配自己的 `api_key_env` 和 `base_url` 即可；不要把真实 key 写进配置文件。

## niuma 身份三件套

每个 niuma 都是一次独立的 Claude CLI 子进程，任务结束进程退出，但身份和工作区保留在磁盘上：

- `profiles/niuma-N/`：作为 `CLAUDE_CONFIG_DIR`，保存该 worker 的 Claude 配置、记忆、命令历史和 MCP 配置。
- `workspaces/niuma-N/`：作为 `--cwd`，该 worker 的 Read/Write/Edit/Bash 等工具默认在这里工作。
- `skills/niuma-N/`：启动任务前链接到 `workspaces/niuma-N/.claude/skills/`，用于安装专属技能。

Claude CLI backend 还会用 `--add-dir artifacts` 授权 worker 读取 artifact 根目录。链式派工时，niuma-2 收到的是 niuma-1 artifact 的绝对路径；它应该用自己的 Read 工具读取文件，而不是依赖 Hermes 把上游内容拼进 prompt。

## OpenAI 兼容中转模型模式

真实模型后端使用 OpenAI Chat Completions 兼容接口，支持 DeepSeek、Opus/Sonnet 中转、OneAPI/NewAPI/OpenRouter 类服务。只要中转站支持：

```text
POST /v1/chat/completions
Authorization: Bearer <key>
model: <模型名>
```

就可以通过 Web 大屏或配置文件切换供应商、Base URL 和模型名。

使用前设置每个牛马自己的 key 和默认 Base URL：

```powershell
$env:OPENAI_COMPATIBLE_API_URL="http://你的中转站/v1"
$env:NIUMA_1_API_KEY="你的牛马1 Key"
$env:NIUMA_2_API_KEY="你的牛马2 Key"
```

`DEEPSEEK_API_URL` 仍作为兼容旧配置的别名可用。`runtime_mode` 可以使用推荐的新名字：

```json
"runtime_mode": "openai-compatible"
```

也可以继续使用旧名字：

```json
"runtime_mode": "deepseek"
```

模型接入点在：

```text
agent_factory/core/worker_runtime.py
```

`OpenAICompatibleWorkerBackend` 会读取每个 worker 自己的 `api_key_env`，保证 key 独立。

## 切换 backend

新配置推荐使用每个 worker 自己的 `backend_type` 和 `backend_options`。参考 `factory_config.example.json`：

```json
{
  "worker_id": "niuma-1",
  "model": "claude-sonnet-4-6",
  "api_key_env": "NIUMA_1_API_KEY",
  "base_url": "https://your-anthropic-compatible-relay/v1",
  "backend_type": "claude_cli",
  "backend_options": {
    "timeout_seconds": 1800,
    "extra_args": ["--permission-mode", "acceptEdits"]
  }
}
```

可选值：

- `claude_cli`：每个任务启动独立 `claude -p` 子进程，使用 `profile_dir`、`workspace_dir`、`skills_dir` 隔离。
- `openai_compatible`：走 OpenAI Chat Completions 兼容接口，用于 DeepSeek/中转站回退。
- `subprocess`：运行自定义命令，主要用于本地 mock 或集成脚本。
- `fake`：测试用固定文本 backend。

灰度建议：先只把 `niuma-1` 切到 `claude_cli`，`niuma-2` 保持 `openai_compatible`；观察任务成功率、耗时和成本后，再切第二个 worker。回滚时只需要把目标 worker 的 `backend_type` 改回 `openai_compatible` 并重启 Worker Server。

本地运行 pytest。测试配置会自动把每次运行的临时目录放到仓库内唯一的 `.tmp/pytest-runs/<run-id>`，避免 Windows 默认 `%TEMP%` 或旧 `.tmp/pytest` 残留目录被锁：

```powershell
python -m pytest tests/ -q
```

如果需要临时覆盖，也可以显式指定一个新的 basetemp：

```powershell
python -m pytest tests/ -q --basetemp=.tmp/pytest-local
```

## Claude CLI 排障

`claude_cli` backend 每次任务都会把原始 stream-json 事件写到 worker 的 workspace：

```text
workspaces/<worker_id>/.hermes/last-events.jsonl
```

如果任务失败，优先看三处：

- `/api/tasks` 或 Console 里的 `error` 字段：区分 CLI 未安装、凭据缺失、非零退出、超时或缺少 `result` 事件。
- `workspaces/<worker_id>/.hermes/last-events.jsonl`：回看 Claude CLI 的 system/assistant/tool/result 事件流。
- `artifacts/<worker_id>/<task_id>/result.md`：任务成功时的最终文本产物。

当错误包含 `claude CLI missing result event` 时，说明 CLI 退出码是 0，但 stdout 里没有最终 `type=result` 事件。此时打开 `last-events.jsonl` 看最后几行，通常能判断是输出格式变化、CLI 提前结束，还是只产生了中间事件。

## Web 大屏配置说明

监控大屏顶部按流水线纵向显示每个牛马工位：牛马1 在上，牛马2 在下。每张工位卡会显示：

- 当前状态、当前任务、队列深度
- 供应商、模型名称、Base URL
- API key 对应的环境变量名，以及是否已配置
- 工位角色、workspace、skills 信息

点击工位卡上的“配置”可以修改并保存：

- provider
- base URL
- model
- role
- API key

保存后会立即影响后续新任务，并写入本地：

```text
D:\牛马架构审查包\agent_factory\runtime_config.json
```

以后重启 Worker Server，只需要：

```powershell
cd D:\codex\cclaude
python serve.py
```

Worker Server 会自动读取 `runtime_config.json` 恢复供应商、Base URL、模型、角色和 key。注意：Web 大屏不会显示真实 key，但 `runtime_config.json` 在当前试运行版本里会保存本地明文 key，不要分享这个文件。要重置配置，停止 Worker Server 后删除 `runtime_config.json`。

## 控制台手动验证清单（重做后）

每次重做控制台或改动 `web/console.html` 后，逐项打勾：

- [ ] 默认进 PIPELINE 标签
- [ ] 切到 DISPATCH，刷新页面后仍在 DISPATCH（localStorage 起效）
- [ ] 4 张统计卡数据正确（Server online、Workers 2/2、Keys、AUTO 开关）
- [ ] 工位卡上下叠展示；「规则」按钮只 1 个，且只在 niuma-1 上有
- [ ] 点「配置」→ 居中模态弹出，蒙版 / ESC / × 三种方式都能关
- [ ] 点「规则」→ 居中模态弹出，任务手册和转换规则两个上传区都在
- [ ] DISPATCH 单工位派工：选工位 + 填 prompt + 发送，成功并出现在 Timeline
- [ ] DISPATCH 链式派工：填 prompt + 上传 1 个文件 + 启动，成功并能在 ARCHIVE 看到两条任务
- [ ] ARCHIVE 左右两栏：选历史任务，右侧产物阅读器显示内容
- [ ] 故意触发错误（空 prompt 发送 / 改坏 token），alert 显示深红边矩形
- [ ] 视觉整体：米底 / 黑字 / serif / 0 圆角 / 无阴影 / 红绿克制
