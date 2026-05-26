# 架构图

## 静态结构

```
+--------------------------------------------+
|              User (你)                     |
+----------------------+---------------------+
                       | 自然语言对话
                       v
+--------------------------------------------+
|       Hermes (本 Claude Code 会话)         |
|  · 收命令 / 拆任务 / 派工 / 汇报           |
+----------------------+---------------------+
                       | HTTP /api/*
                       v
+--------------------------------------------+
|        worker_server (FastAPI, 长驻)       |
|                                            |
|  +-------------+   +-------------------+   |
|  |  TaskBus    |   |  ArtifactStore    |   |
|  +-------------+   +-------------------+   |
|                                            |
|  +--------------------------------------+  |
|  |  HermesSupervisor                    |  |
|  |  · delegate()                        |  |
|  |  · chain()  ← 文件级握手             |  |
|  +--------------------------------------+  |
|                                            |
|  +--------------------------------------+  |
|  |  WorkerRuntime × N                   |  |
|  |  └── build_backend(WorkerConfig)     |  |
|  +--------------------------------------+  |
+----------------------+---------------------+
                       | subprocess (per task)
       +---------------+---------------+
       v               v               v
  +---------+    +---------+    +---------+
  | claude  |    | claude  |    | claude  |
  |  CLI    |    |  CLI    |    |  CLI    |
  | niuma-1 |    | niuma-2 |    | niuma-N |
  +----+----+    +----+----+    +----+----+
       |              |              |
   profile        profile        profile
   workspace      workspace      workspace
   skills         skills         skills
   (隔离)         (隔离)         (隔离)
```

## 链式派工时序

```
User           Hermes        worker_server      niuma-1           ArtifactStore     niuma-2
 |               |                 |                 |                   |               |
 |--- chain ---->|                 |                 |                   |               |
 |               |--- /api/chain ->|                 |                   |               |
 |               |                 |--- spawn ------>|                   |               |
 |               |                 |                 |--- Read/Write --->|               |
 |               |                 |                 |   (在自己 workspace)              |
 |               |                 |                 |--- 输出 result.md ->|              |
 |               |                 |<-- exit 0 ------|                   |               |
 |               |                 |                                     |               |
 |               |                 |   生成 handoff_prompt:                              |
 |               |                 |   "上游任务: <raw>                                   |
 |               |                 |    文件路径: artifacts/niuma-1/.../result.md"        |
 |               |                 |                                                     |
 |               |                 |--- spawn ----------------------------------------> | |
 |               |                 |                                     |               |
 |               |                 |                                     |<-- Read ------|
 |               |                 |                                     |--- text ----->|
 |               |                 |                                     |               |
 |               |                 |                                     |--- Write ---->|
 |               |                 |                                     |  doc.md       |
 |               |                 |<-- exit 0 -------------------------------------------|
 |               |<-- (source, target) records ----------------------------                |
 |<-- 汇报 ------|                                                                         |
```

## Backend 装配

```
factory_config.json
   |
   v
  load_factory_config()
   |
   v
  [WorkerConfig, ...]
   |
   v
  worker_server.py 启动循环：
     for config in configs:
        backend = build_backend(config)  ← 工厂分发
        runtime = WorkerRuntime(config, bus, artifacts, backend)
        runtimes[config.worker_id] = runtime

  build_backend(config):
     match config.backend_type:
        "claude_cli"        -> ClaudeCliWorkerBackend(**opts)
        "openai_compatible" -> OpenAICompatibleWorkerBackend(**opts)
        "subprocess"        -> SubprocessWorkerBackend(**opts)
        "fake"              -> FakeWorkerBackend(**opts)
        _                   -> raise BackendError
```
