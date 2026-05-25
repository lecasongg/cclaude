# 本地 Agent 工厂试运行说明

## 启动 Worker Server

在 PowerShell 里运行：

```powershell
cd D:\牛马架构审查包\agent_factory
$env:PYTHONPATH="D:\牛马架构审查包"
python worker_server.py
```

默认地址：`http://127.0.0.1:8846`
默认 token：`change-me-local-token`

## 打开监控大屏

浏览器访问：

```text
http://127.0.0.1:8846/
```

## 启动常驻 Hermes 主管

另开一个 PowerShell：

```powershell
cd D:\牛马架构审查包\agent_factory
python hermes_supervisor.py http://127.0.0.1:8846 change-me-local-token
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
python hermes_supervisor.py http://127.0.0.1:8846 change-me-local-token workers
python hermes_supervisor.py http://127.0.0.1:8846 change-me-local-token delegate niuma-1 "分析这个 JSP 项目，输出需求清单"
python hermes_supervisor.py http://127.0.0.1:8846 change-me-local-token chain niuma-1 niuma-2 "逆向分析 JSP" "根据上游清单编写需求文档"
```

## 当前试运行模式

`config.example.json` 默认使用：

```json
"runtime_mode": "mock-subprocess"
```

这会为每个牛马启动独立 Python 子进程，验证：

- 独立 worker_id
- 独立 workspace
- 独立 skills 目录
- 独立 profile 目录
- artifact 流水线
- PowerShell Hermes 到 Worker Server 的派工链路

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
cd D:\牛马架构审查包\agent_factory
$env:PYTHONPATH="D:\牛马架构审查包"
python worker_server.py
```

Worker Server 会自动读取 `runtime_config.json` 恢复供应商、Base URL、模型、角色和 key。注意：Web 大屏不会显示真实 key，但 `runtime_config.json` 在当前试运行版本里会保存本地明文 key，不要分享这个文件。要重置配置，停止 Worker Server 后删除 `runtime_config.json`。
