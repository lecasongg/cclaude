# cclaude / agent_factory

本地多 Agent 工作流：

- **牛马1** — 老系统（JSP / JS / SQL）逆向分析工位
- **牛马2** — 需求文档编写工位

由 Hermes 主管派工，Worker Server 提供 HTTP 接口与 Web 监控大屏。模型后端走 OpenAI Chat Completions 兼容协议（DeepSeek、Opus/Sonnet 中转、OneAPI/NewAPI/OpenRouter 等）。

## 快速开始

```powershell
# 1. 复制配置示例
copy config.example.json config.json

# 2. 启动 Worker Server
$env:PYTHONPATH="<repo 父目录>"
python worker_server.py
```

监控大屏：<http://127.0.0.1:8846/>

详细启动、Hermes 派工、模型/Key 配置见 [`RUNBOOK.md`](./RUNBOOK.md)。

## 目录

| 路径 | 用途 |
|------|------|
| `worker_server.py` | HTTP 服务 + 监控大屏入口 |
| `hermes_supervisor.py` | Hermes 主管 CLI |
| `core/` | Worker runtime / backend / 派工逻辑 |
| `web/` | 监控大屏前端 |
| `tests/` | 单元 / 集成测试 |
| `docs/` | 设计与说明文档 |
| `profiles/`、`skills/` | 各牛马的 profile 与技能（运行时填充） |
| `artifacts/`、`workspaces/` | 运行时产出（已 gitignore） |
| `runtime_config.json` | 本地运行时配置，**含明文 API key，已 gitignore，禁止提交** |

## 配置

- `config.example.json` / `config.deepseek.example.json` — 配置模板，提交到仓库
- `runtime_config.json` — 本地 Web 大屏写入的实际配置，含密钥，**不提交**
- API key 通过环境变量注入，例如 `NIUMA_1_API_KEY` / `NIUMA_2_API_KEY`
