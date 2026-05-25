# Agent Factory Web Console Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing local Agent Factory page into a more professional, usable control console for worker status, single-worker dispatch, niuma-1 to niuma-2 chain dispatch, task filtering, artifact reading, and basic health visibility.

**Architecture:** Keep the current FastAPI server and single-file Alpine/Tailwind console so the running workflow remains simple. Add one small authenticated health endpoint, then rewrite `web/console.html` with clear UI regions and grouped Alpine state/methods without introducing a frontend build system.

**Tech Stack:** Python 3.13, FastAPI, pytest, FastAPI TestClient, Tailwind CDN, Alpine.js CDN, browser `fetch`.

---

## File Structure

- Modify `D:/牛马架构审查包/agent_factory/core/api.py`
  - Add authenticated `GET /api/health` inside `create_app()`.
  - Return server health, worker count, task count, configured key count, and whether runtime config persistence is available.
- Modify `D:/牛马架构审查包/agent_factory/tests/test_api.py`
  - Add tests for `/api/health` success and token rejection.
  - Keep existing API tests unchanged except where formatting is needed.
- Replace `D:/牛马架构审查包/agent_factory/web/console.html`
  - Keep it as one HTML file.
  - Add small component-style CSS classes in `<style type="text/tailwindcss">` for `.panel`, `.btn-primary`, `.btn-secondary`, `.field`, `.chip`, `.status-dot`.
  - Add top status bar, pipeline cards, single dispatch, chain dispatch, task filters, artifact reader, and timeline.
  - Group Alpine methods by responsibility with method names used directly by the template.

No new frontend dependencies or build files are introduced.

---

### Task 1: Add API Health Endpoint

**Files:**
- Modify: `D:/牛马架构审查包/agent_factory/core/api.py:79-84`
- Modify: `D:/牛马架构审查包/agent_factory/tests/test_api.py:46-54`

- [ ] **Step 1: Write failing tests for health authorization and response shape**

Add these tests after `test_api_rejects_missing_token` in `D:/牛马架构审查包/agent_factory/tests/test_api.py`:

```python
def test_api_rejects_health_without_token(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 401


def test_api_reports_health_with_token(tmp_path, monkeypatch):
    monkeypatch.setenv("NIUMA_1_API_KEY", "sk-worker-1")
    monkeypatch.delenv("NIUMA_2_API_KEY", raising=False)
    client = build_client(tmp_path)

    response = client.get("/api/health", headers={"x-hermes-token": "local-token"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "workers_total": 2,
        "workers_with_api_key": 1,
        "tasks_total": 0,
        "runtime_config_persistence": True,
    }
```

- [ ] **Step 2: Run the new health tests and verify they fail**

Run from `D:/牛马架构审查包/agent_factory` with `PYTHONPATH='D:/牛马架构审查包'`:

```bash
PYTHONPATH='D:/牛马架构审查包' pytest tests/test_api.py::test_api_rejects_health_without_token tests/test_api.py::test_api_reports_health_with_token -v
```

Expected: both tests fail with `404 Not Found` because `/api/health` does not exist yet.

- [ ] **Step 3: Implement the health endpoint**

In `D:/牛马架构审查包/agent_factory/core/api.py`, insert this route immediately before the existing `@app.get("/api/workers")` route:

```python
    @app.get("/api/health")
    async def health(x_hermes_token: str | None = Header(default=None)):
        authorize(x_hermes_token)
        return {
            "status": "ok",
            "workers_total": len(workers),
            "workers_with_api_key": sum(1 for worker in workers if os.environ.get(worker.api_key_env)),
            "tasks_total": len(bus.list_tasks()),
            "runtime_config_persistence": runtime_config_path is not None,
        }
```

- [ ] **Step 4: Run the health tests and verify they pass**

```bash
PYTHONPATH='D:/牛马架构审查包' pytest tests/test_api.py::test_api_rejects_health_without_token tests/test_api.py::test_api_reports_health_with_token -v
```

Expected: both tests pass.

- [ ] **Step 5: Run the full API test file**

```bash
PYTHONPATH='D:/牛马架构审查包' pytest tests/test_api.py -v
```

Expected: all tests in `tests/test_api.py` pass.

---

### Task 2: Replace Console With Component-Style Layout

**Files:**
- Modify: `D:/牛马架构审查包/agent_factory/web/console.html`

- [ ] **Step 1: Replace the whole console HTML with the enhanced version**

Replace the entire contents of `D:/牛马架构审查包/agent_factory/web/console.html` with:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hermes Local Agent Factory</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
  <style type="text/tailwindcss">
    @layer components {
      .panel { @apply rounded-2xl border border-white/10 bg-[#0f1011]/90 p-5; }
      .panel-soft { @apply rounded-xl border border-white/10 bg-black/30 p-4; }
      .btn-primary { @apply rounded-lg bg-[#5e6ad2] px-4 py-2 text-sm font-medium text-white hover:bg-[#828fff] disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400; }
      .btn-secondary { @apply rounded-lg border border-white/10 bg-[#101111] px-4 py-2 text-sm text-zinc-200 hover:border-white/20 hover:bg-white/5 disabled:cursor-not-allowed disabled:text-zinc-600; }
      .field { @apply rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-100 outline-none ring-[#5e6ad2]/40 placeholder:text-zinc-600 focus:ring-2; }
      .chip { @apply rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-zinc-300; }
      .status-dot { @apply inline-block h-2 w-2 rounded-full; }
    }
  </style>
</head>
<body class="min-h-screen bg-[#010102] text-zinc-100 antialiased">
  <main x-data="factoryConsole()" x-init="init()" class="mx-auto flex min-h-screen max-w-7xl flex-col gap-5 px-5 py-5 lg:px-8">
    <header class="panel overflow-hidden">
      <div class="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p class="font-mono text-xs uppercase tracking-[0.32em] text-indigo-300">Hermes Workshop</p>
          <h1 class="mt-3 text-3xl font-semibold tracking-tight md:text-4xl">本地 Agent 工厂控制台</h1>
          <p class="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">把牛马1的老系统逆向分析和牛马2的需求文档编写串成一条可观察、可派工、可读产物的本地流水线。</p>
        </div>
        <div class="grid gap-3 lg:w-[30rem]">
          <div class="grid gap-2 md:grid-cols-[1fr_11rem]">
            <input x-model="baseUrl" class="field font-mono" aria-label="Server URL">
            <button @click="refreshAll" :disabled="isRefreshing" class="btn-primary" x-text="isRefreshing ? '刷新中...' : '刷新状态'"></button>
          </div>
          <input x-model="token" type="password" class="field font-mono" aria-label="Hermes Token">
        </div>
      </div>
    </header>

    <section class="grid gap-3 lg:grid-cols-4">
      <div class="panel-soft">
        <p class="font-mono text-xs uppercase tracking-widest text-zinc-500">Server</p>
        <div class="mt-3 flex items-center gap-2">
          <span class="status-dot" :class="health.status === 'ok' ? 'bg-emerald-400' : 'bg-red-400'"></span>
          <span class="font-medium" x-text="health.status === 'ok' ? 'online' : 'unknown'"></span>
        </div>
        <p class="mt-2 break-all font-mono text-xs text-zinc-500" x-text="baseUrl"></p>
      </div>
      <div class="panel-soft">
        <p class="font-mono text-xs uppercase tracking-widest text-zinc-500">Workers</p>
        <p class="mt-3 text-2xl font-semibold" x-text="`${workers.length} / ${health.workers_total || workers.length}`"></p>
        <p class="mt-2 text-xs text-zinc-500">已加载工位</p>
      </div>
      <div class="panel-soft">
        <p class="font-mono text-xs uppercase tracking-widest text-zinc-500">API Keys</p>
        <p class="mt-3 text-2xl font-semibold" x-text="`${workersWithKeys()} / ${workers.length}`"></p>
        <p class="mt-2 text-xs text-zinc-500">已配置模型密钥</p>
      </div>
      <div class="panel-soft">
        <p class="font-mono text-xs uppercase tracking-widest text-zinc-500">Auto Refresh</p>
        <button @click="toggleAutoRefresh" class="mt-3 btn-secondary w-full" x-text="autoRefresh ? '关闭自动刷新' : '开启自动刷新'"></button>
        <p class="mt-2 text-xs text-zinc-500">开启后每 5 秒刷新状态</p>
      </div>
    </section>

    <div x-show="alert" x-transition class="rounded-2xl border px-4 py-3 text-sm" :class="alert && alert.type === 'error' ? 'border-red-400/40 bg-red-500/10 text-red-200' : 'border-emerald-400/40 bg-emerald-500/10 text-emerald-200'">
      <div class="flex items-start justify-between gap-4">
        <p x-text="alert ? alert.message : ''"></p>
        <button @click="alert = null" class="text-xs text-zinc-400 hover:text-zinc-100">关闭</button>
      </div>
    </div>

    <section class="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
      <div class="panel">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="font-mono text-xs uppercase tracking-[0.25em] text-zinc-500">Pipeline</p>
            <h2 class="mt-1 text-xl font-medium">牛马流水线</h2>
          </div>
          <span class="chip">niuma-1 → niuma-2</span>
        </div>

        <div class="mt-5 grid gap-4">
          <template x-for="(worker, index) in workers" :key="worker.worker_id">
            <article @click="selectedWorker = worker.worker_id" class="rounded-2xl border p-4 transition" :class="selectedWorker === worker.worker_id ? 'border-indigo-400 bg-indigo-500/10' : 'border-white/10 bg-black/30 hover:border-white/20'">
              <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div class="min-w-0">
                  <div class="flex items-center gap-3">
                    <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/5 font-mono text-sm text-indigo-200" x-text="index + 1"></span>
                    <div class="min-w-0">
                      <h3 class="font-medium" x-text="worker.display_name"></h3>
                      <p class="font-mono text-xs text-zinc-500" x-text="worker.worker_id"></p>
                    </div>
                  </div>
                  <p class="mt-3 text-sm leading-6 text-zinc-300" x-text="worker.role"></p>
                </div>
                <div class="flex items-center gap-2">
                  <span class="rounded-full px-2 py-1 font-mono text-xs" :class="statusClass(worker.status)" x-text="worker.status"></span>
                  <button @click.stop="openWorkerConfig(worker)" class="btn-secondary px-3 py-1.5">配置</button>
                </div>
              </div>

              <div class="mt-4 grid gap-3 text-sm md:grid-cols-2">
                <div class="panel-soft p-3">
                  <p class="font-mono text-xs text-zinc-500">Provider / Model</p>
                  <p class="mt-1 truncate text-zinc-200"><span x-text="worker.provider"></span> · <span x-text="worker.model"></span></p>
                </div>
                <div class="panel-soft p-3">
                  <p class="font-mono text-xs text-zinc-500">API Key</p>
                  <p class="mt-1 text-zinc-300"><span x-text="worker.api_key_env"></span> · <span :class="worker.api_key_configured ? 'text-emerald-300' : 'text-red-300'" x-text="worker.api_key_configured ? '已配置' : '未配置'"></span></p>
                </div>
                <div class="panel-soft p-3 md:col-span-2">
                  <p class="font-mono text-xs text-zinc-500">Base URL</p>
                  <p class="mt-1 break-all font-mono text-xs text-zinc-300" x-text="worker.base_url || '未配置'"></p>
                </div>
                <div class="panel-soft p-3 md:col-span-2">
                  <p class="font-mono text-xs text-zinc-500">当前任务</p>
                  <p class="mt-1 line-clamp-2 text-zinc-300" x-text="currentTaskPrompt(worker) || '空闲'"></p>
                </div>
              </div>
            </article>
          </template>
        </div>
      </div>

      <div class="grid gap-5">
        <section class="panel">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="font-mono text-xs uppercase tracking-[0.25em] text-zinc-500">Dispatch</p>
              <h2 class="mt-1 text-xl font-medium">单工位派工</h2>
            </div>
            <span class="chip" x-text="selectedWorker"></span>
          </div>
          <div class="mt-5 grid gap-3">
            <select x-model="selectedWorker" class="field">
              <template x-for="worker in workers" :key="worker.worker_id">
                <option class="bg-zinc-950" :value="worker.worker_id" x-text="`${worker.display_name} · ${worker.worker_id}`"></option>
              </template>
            </select>
            <textarea x-model="prompt" rows="5" placeholder="给选中的牛马下达任务..." class="field resize-y"></textarea>
            <button @click="delegateTask" :disabled="isDelegating || !prompt.trim()" class="btn-primary" x-text="isDelegating ? '派工中...' : '发送任务'"></button>
          </div>
        </section>

        <section class="panel">
          <p class="font-mono text-xs uppercase tracking-[0.25em] text-zinc-500">Chain</p>
          <h2 class="mt-1 text-xl font-medium">牛马1 → 牛马2 链式派工</h2>
          <div class="mt-5 grid gap-3">
            <textarea x-model="chainPrompt" rows="4" placeholder="给牛马1的逆向分析任务..." class="field resize-y"></textarea>
            <textarea x-model="nextInstruction" rows="3" class="field resize-y"></textarea>
            <button @click="chainTask" :disabled="isChaining || !chainPrompt.trim()" class="btn-primary" x-text="isChaining ? '流水线执行中...' : '启动链式派工'"></button>
          </div>
        </section>

        <section x-show="configWorker" class="panel border-indigo-400/30 bg-indigo-500/10">
          <div class="flex items-center justify-between">
            <h3 class="font-medium">工位配置</h3>
            <button @click="configWorker = null" class="text-sm text-zinc-400 hover:text-zinc-100">关闭</button>
          </div>
          <div class="mt-4 grid gap-3">
            <input x-model="configForm.provider" placeholder="provider" class="field">
            <input x-model="configForm.base_url" placeholder="base url，例如 http://host:port/v1" class="field">
            <input x-model="configForm.model" placeholder="model" class="field">
            <input x-model="configForm.role" placeholder="role" class="field">
            <input x-model="configForm.api_key" type="password" placeholder="API key，留空则保留原 key" class="field">
            <p class="text-xs leading-5 text-amber-300">本地试运行会把 key 保存到 runtime_config.json；不要分享这个文件。</p>
            <button @click="saveWorkerConfig" :disabled="isSavingConfig" class="btn-primary" x-text="isSavingConfig ? '保存中...' : '保存配置'"></button>
          </div>
        </section>
      </div>
    </section>

    <section class="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
      <div class="panel">
        <div class="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p class="font-mono text-xs uppercase tracking-[0.25em] text-zinc-500">History</p>
            <h2 class="mt-1 text-xl font-medium">任务历史</h2>
          </div>
          <div class="grid gap-2 md:grid-cols-2">
            <select x-model="taskFilter.worker" class="field py-1.5">
              <option class="bg-zinc-950" value="all">全部工位</option>
              <template x-for="worker in workers" :key="worker.worker_id">
                <option class="bg-zinc-950" :value="worker.worker_id" x-text="worker.worker_id"></option>
              </template>
            </select>
            <select x-model="taskFilter.status" class="field py-1.5">
              <option class="bg-zinc-950" value="all">全部状态</option>
              <option class="bg-zinc-950" value="succeeded">succeeded</option>
              <option class="bg-zinc-950" value="failed">failed</option>
              <option class="bg-zinc-950" value="running">running</option>
              <option class="bg-zinc-950" value="pending">pending</option>
            </select>
          </div>
        </div>
        <div class="mt-5 max-h-[560px] space-y-3 overflow-auto pr-1">
          <template x-for="task in filteredTasks()" :key="task.task_id">
            <button @click="selectTask(task)" class="w-full rounded-2xl border p-4 text-left transition" :class="selectedTask && selectedTask.task_id === task.task_id ? 'border-indigo-400 bg-indigo-500/10' : 'border-white/10 bg-black/30 hover:border-white/20'">
              <div class="flex items-center justify-between gap-3">
                <span class="font-medium" x-text="task.worker_id"></span>
                <span class="rounded-full px-2 py-1 font-mono text-xs" :class="statusClass(task.status)" x-text="task.status"></span>
              </div>
              <p class="mt-2 line-clamp-2 text-sm leading-6 text-zinc-400" x-text="task.prompt"></p>
              <p class="mt-3 font-mono text-xs text-zinc-600" x-text="task.task_id"></p>
            </button>
          </template>
          <p x-show="filteredTasks().length === 0" class="rounded-2xl border border-white/10 bg-black/30 p-6 text-center text-sm text-zinc-500">暂无匹配任务。</p>
        </div>
      </div>

      <div class="panel">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="font-mono text-xs uppercase tracking-[0.25em] text-zinc-500">Artifact</p>
            <h2 class="mt-1 text-xl font-medium">产物阅读器</h2>
          </div>
          <button @click="copyArtifact" :disabled="!artifactText()" class="btn-secondary">复制产物</button>
        </div>
        <template x-if="selectedTask">
          <div class="mt-5 space-y-4">
            <div class="panel-soft">
              <div class="flex flex-wrap items-center gap-2">
                <span class="chip" x-text="selectedTask.worker_id"></span>
                <span class="chip" x-text="selectedTask.status"></span>
                <span class="chip" x-show="selectedTask.parent_task_id">有上游任务</span>
              </div>
              <p class="mt-3 font-mono text-xs text-zinc-500" x-text="selectedTask.task_id"></p>
              <p class="mt-3 text-sm leading-6 text-zinc-300" x-text="selectedTask.prompt"></p>
              <p class="mt-3 text-sm text-red-300" x-show="selectedTask.error" x-text="selectedTask.error"></p>
            </div>
            <div class="flex flex-wrap gap-2">
              <template x-for="artifactId in selectedTask.artifact_ids" :key="artifactId">
                <button @click="loadArtifact(artifactId)" class="rounded-lg border border-indigo-400/40 bg-indigo-500/10 px-3 py-2 font-mono text-xs text-indigo-200 hover:bg-indigo-500/20" x-text="artifactId"></button>
              </template>
            </div>
            <pre class="max-h-[620px] overflow-auto whitespace-pre-wrap rounded-2xl border border-white/10 bg-black/50 p-5 text-sm leading-7 text-zinc-200" x-text="artifactText() || '这个任务还没有产物。'"></pre>
          </div>
        </template>
        <p x-show="!selectedTask" class="mt-5 rounded-2xl border border-white/10 bg-black/30 p-8 text-center text-sm text-zinc-500">选择左侧任务查看结果和 artifact。</p>
      </div>
    </section>

    <section class="panel">
      <div class="flex items-center justify-between">
        <div>
          <p class="font-mono text-xs uppercase tracking-[0.25em] text-zinc-500">Timeline</p>
          <h2 class="mt-1 text-xl font-medium">操作回执</h2>
        </div>
        <button @click="events = []" class="btn-secondary">清空</button>
      </div>
      <div class="mt-5 grid gap-3">
        <template x-for="event in events" :key="event.id">
          <article class="rounded-2xl border border-white/10 bg-black/30 p-4">
            <div class="flex items-center justify-between gap-4">
              <span class="font-mono text-xs uppercase tracking-widest text-indigo-300" x-text="event.type"></span>
              <span class="font-mono text-xs text-zinc-500" x-text="event.time"></span>
            </div>
            <pre class="mt-3 overflow-auto whitespace-pre-wrap text-sm leading-6 text-zinc-300" x-text="event.body"></pre>
          </article>
        </template>
        <p x-show="events.length === 0" class="text-sm text-zinc-500">暂无操作回执。</p>
      </div>
    </section>
  </main>

  <script>
    function factoryConsole() {
      return {
        baseUrl: 'http://127.0.0.1:8846',
        token: 'change-me-local-token',
        health: {},
        workers: [],
        tasks: [],
        selectedTask: null,
        artifactContent: '',
        selectedWorker: 'niuma-1',
        prompt: '',
        chainPrompt: '',
        nextInstruction: '根据上游逆向分析清单，编写可交付的需求文档。',
        taskFilter: {worker: 'all', status: 'all'},
        configWorker: null,
        configForm: {provider: '', base_url: '', model: '', role: '', api_key: ''},
        events: [],
        alert: null,
        autoRefresh: false,
        autoRefreshTimer: null,
        isRefreshing: false,
        isDelegating: false,
        isChaining: false,
        isSavingConfig: false,
        headers() {
          return {'content-type': 'application/json', 'x-hermes-token': this.token};
        },
        async init() {
          await this.refreshAll();
        },
        async requestJson(path, options = {}) {
          const response = await fetch(`${this.baseUrl}${path}`, {
            ...options,
            headers: {...this.headers(), ...(options.headers || {})}
          });
          const body = await response.json().catch(() => ({}));
          if (!response.ok) {
            throw new Error(body.detail || body.error || `HTTP ${response.status}`);
          }
          return body;
        },
        async refreshAll() {
          if (this.isRefreshing) return;
          this.isRefreshing = true;
          try {
            await Promise.all([this.refreshHealth(), this.refreshWorkers(), this.refreshTasks()]);
          } catch (error) {
            this.health = {};
            this.showAlert('error', `刷新失败：${error.message}`);
            this.record('error', error.message);
          } finally {
            this.isRefreshing = false;
          }
        },
        async refreshHealth() {
          this.health = await this.requestJson('/api/health');
        },
        async refreshWorkers() {
          const body = await this.requestJson('/api/workers');
          this.workers = body.workers || [];
          if (!this.workers.find((worker) => worker.worker_id === this.selectedWorker) && this.workers.length) {
            this.selectedWorker = this.workers[0].worker_id;
          }
        },
        async refreshTasks() {
          const body = await this.requestJson('/api/tasks');
          this.tasks = body.tasks || [];
          if (!this.selectedTask && this.tasks.length) {
            this.selectTask(this.tasks[0]);
          }
        },
        toggleAutoRefresh() {
          this.autoRefresh = !this.autoRefresh;
          if (this.autoRefresh) {
            this.autoRefreshTimer = setInterval(() => this.refreshAll(), 5000);
            this.record('system', '自动刷新已开启，每 5 秒刷新一次。');
          } else {
            clearInterval(this.autoRefreshTimer);
            this.autoRefreshTimer = null;
            this.record('system', '自动刷新已关闭。');
          }
        },
        async delegateTask() {
          if (this.isDelegating || !this.prompt.trim()) return;
          this.isDelegating = true;
          this.alert = null;
          try {
            const body = await this.requestJson('/api/delegate', {
              method: 'POST',
              body: JSON.stringify({worker_id: this.selectedWorker, prompt: this.prompt})
            });
            this.record('delegate', this.taskSummary(body));
            this.selectedTask = body;
            this.artifactContent = '';
            if (body.status === 'failed') {
              this.showAlert('error', body.error || '任务执行失败，请查看任务历史。');
            } else {
              this.showAlert('success', `${body.worker_id} 已完成任务。`);
            }
            await this.refreshAll();
          } catch (error) {
            this.showAlert('error', `派工请求失败：${error.message}`);
            this.record('error', error.message);
          } finally {
            this.isDelegating = false;
          }
        },
        async chainTask() {
          if (this.isChaining || !this.chainPrompt.trim()) return;
          this.isChaining = true;
          this.alert = null;
          try {
            const body = await this.requestJson('/api/chain', {
              method: 'POST',
              body: JSON.stringify({
                source_worker: 'niuma-1',
                target_worker: 'niuma-2',
                prompt: this.chainPrompt,
                next_instruction: this.nextInstruction
              })
            });
            this.record('chain', `上游：${this.taskSummary(body.source)}\n\n下游：${this.taskSummary(body.target)}`);
            this.selectedTask = body.target;
            this.artifactContent = '';
            if (body.source.status === 'failed' || body.target.status === 'failed') {
              this.showAlert('error', body.target.error || body.source.error || '链式任务执行失败。');
            } else {
              this.showAlert('success', '牛马1 → 牛马2 链式派工已完成。');
            }
            await this.refreshAll();
          } catch (error) {
            this.showAlert('error', `链式派工失败：${error.message}`);
            this.record('error', error.message);
          } finally {
            this.isChaining = false;
          }
        },
        openWorkerConfig(worker) {
          this.selectedWorker = worker.worker_id;
          this.configWorker = worker;
          this.configForm = {
            provider: worker.provider || '',
            base_url: worker.base_url || '',
            model: worker.model || '',
            role: worker.role || '',
            api_key: ''
          };
        },
        async saveWorkerConfig() {
          if (!this.configWorker || this.isSavingConfig) return;
          this.isSavingConfig = true;
          this.alert = null;
          const payload = {
            provider: this.configForm.provider,
            base_url: this.configForm.base_url,
            model: this.configForm.model,
            role: this.configForm.role
          };
          if (this.configForm.api_key) {
            payload.api_key = this.configForm.api_key;
          }
          try {
            const body = await this.requestJson(`/api/workers/${this.configWorker.worker_id}/config`, {
              method: 'PATCH',
              body: JSON.stringify(payload)
            });
            this.configForm.api_key = '';
            this.record('config', `${body.worker.worker_id} · ${body.worker.provider} · ${body.worker.model}\n${body.notice}`);
            this.showAlert('success', body.notice || '配置已保存。');
            await this.refreshAll();
          } catch (error) {
            this.showAlert('error', `配置请求失败：${error.message}`);
            this.record('error', error.message);
          } finally {
            this.isSavingConfig = false;
          }
        },
        currentTaskPrompt(worker) {
          const task = this.tasks.find((candidate) => candidate.task_id === worker.current_task_id);
          return task ? task.prompt : '';
        },
        workersWithKeys() {
          return this.workers.filter((worker) => worker.api_key_configured).length;
        },
        filteredTasks() {
          return this.tasks.filter((task) => {
            const workerMatch = this.taskFilter.worker === 'all' || task.worker_id === this.taskFilter.worker;
            const statusMatch = this.taskFilter.status === 'all' || task.status === this.taskFilter.status;
            return workerMatch && statusMatch;
          });
        },
        selectTask(task) {
          this.selectedTask = task;
          this.artifactContent = '';
        },
        async loadArtifact(artifactId) {
          try {
            const body = await this.requestJson(`/api/artifacts/${artifactId}`);
            this.artifactContent = body.content || '';
          } catch (error) {
            this.showAlert('error', `读取产物失败：${error.message}`);
            this.record('error', error.message);
          }
        },
        artifactText() {
          return this.artifactContent || (this.selectedTask && this.selectedTask.result_text) || '';
        },
        async copyArtifact() {
          const text = this.artifactText();
          if (!text) return;
          await navigator.clipboard.writeText(text);
          this.showAlert('success', '产物已复制到剪贴板。');
        },
        statusClass(status) {
          if (status === 'succeeded' || status === 'idle') return 'bg-emerald-500/15 text-emerald-300';
          if (status === 'failed') return 'bg-red-500/15 text-red-300';
          if (status === 'running') return 'bg-indigo-500/15 text-indigo-300';
          return 'bg-zinc-800 text-zinc-300';
        },
        showAlert(type, message) {
          this.alert = {type, message};
        },
        taskSummary(task) {
          const lines = [
            `${task.worker_id} · ${task.status}`,
            task.prompt || '',
          ];
          if (task.error) {
            lines.push(`错误：${task.error}`);
          }
          if (task.artifact_ids && task.artifact_ids.length) {
            lines.push(`产物：${task.artifact_ids.join(', ')}`);
          }
          return lines.filter(Boolean).join('\n');
        },
        record(type, body) {
          this.events.unshift({id: crypto.randomUUID(), type, body, time: new Date().toLocaleTimeString()});
        }
      }
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: Smoke test the console route returns the new page**

Start the server if it is not already running:

```bash
PYTHONPATH='D:/牛马架构审查包' python 'D:/牛马架构审查包/agent_factory/worker_server.py'
```

In another shell, run:

```bash
curl -s 'http://127.0.0.1:8846/' | grep -E '本地 Agent 工厂控制台|启动链式派工|产物阅读器'
```

Expected: output contains all three strings.

- [ ] **Step 3: Smoke test the health, workers, and tasks APIs used by the page**

```bash
curl -s -H 'x-hermes-token: change-me-local-token' 'http://127.0.0.1:8846/api/health'
curl -s -H 'x-hermes-token: change-me-local-token' 'http://127.0.0.1:8846/api/workers'
curl -s -H 'x-hermes-token: change-me-local-token' 'http://127.0.0.1:8846/api/tasks'
```

Expected:
- health response includes `"status":"ok"`.
- workers response includes `"workers"` and the configured `niuma-1` / `niuma-2` workers.
- tasks response includes `"tasks"`.

---

### Task 3: Manual Browser Verification

**Files:**
- Verify: `D:/牛马架构审查包/agent_factory/web/console.html`
- Verify: `D:/牛马架构审查包/agent_factory/core/api.py`

- [ ] **Step 1: Open the console in a browser**

Open:

```text
http://127.0.0.1:8846/
```

Expected visible UI:
- Header title is `本地 Agent 工厂控制台`.
- Status cards show Server, Workers, API Keys, Auto Refresh.
- Pipeline section shows 牛马1 and 牛马2.
- Right side shows 单工位派工 and 牛马1 → 牛马2 链式派工.
- Lower section shows 任务历史 and 产物阅读器.

- [ ] **Step 2: Verify refresh and filters**

In the browser:
1. Click `刷新状态`.
2. Toggle `开启自动刷新`, wait one refresh interval, then toggle it off.
3. Change task history filters between `全部工位`, `niuma-1`, `niuma-2`, and status values.

Expected:
- No JavaScript error alert appears.
- Worker cards remain visible after refresh.
- Filter changes do not break the task list; empty states show `暂无匹配任务。` when there are no matches.

- [ ] **Step 3: Verify single-worker dispatch with a low-cost prompt**

Use a short prompt to avoid unnecessary model spend:

```text
用一句话回复：牛马1在线。
```

Select `牛马1 · niuma-1`, click `发送任务`.

Expected:
- Button changes to `派工中...` while the request runs.
- A success or failure alert appears.
- A timeline entry of type `delegate` appears.
- If succeeded, task history shows the new task and artifact reader shows model output.
- If failed, the alert and task card show the provider error without breaking the page.

- [ ] **Step 4: Verify chain dispatch path**

Use a short chain prompt:

```text
分析一个只有登录按钮的旧页面，输出三条需求线索。
```

Click `启动链式派工`.

Expected:
- Button changes to `流水线执行中...` while the request runs.
- A timeline entry of type `chain` appears.
- If both workers are configured, selected task becomes the niuma-2 task and artifact reader shows the downstream document.
- If niuma-2 API key is missing, the page shows a clear failure alert and keeps the UI usable.

- [ ] **Step 5: Verify artifact reading and copy**

Select any succeeded task with an artifact, click the artifact id, then click `复制产物`.

Expected:
- Artifact text appears in the reader.
- `复制产物` shows success alert `产物已复制到剪贴板。`.

---

### Task 4: Final Verification

**Files:**
- Verify: all modified files

- [ ] **Step 1: Run all tests**

From `D:/牛马架构审查包/agent_factory`:

```bash
PYTHONPATH='D:/牛马架构审查包' pytest tests -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify server starts from the documented command**

```bash
PYTHONPATH='D:/牛马架构审查包' python 'D:/牛马架构审查包/agent_factory/worker_server.py'
```

Expected: uvicorn starts on `http://127.0.0.1:8846` without import errors.

- [ ] **Step 3: Verify the main page and health endpoint while the server is running**

```bash
curl -s 'http://127.0.0.1:8846/' | grep '本地 Agent 工厂控制台'
curl -s -H 'x-hermes-token: change-me-local-token' 'http://127.0.0.1:8846/api/health'
```

Expected:
- first command prints the title line.
- second command returns JSON containing `"status":"ok"`.

---

## Self-Review

**Spec coverage:**
- Visual/professional UI: Task 2 replaces the console with Linear/Raycast-inspired dark developer-tool layout.
- Better usability: Task 2 adds chain dispatch, filters, artifact reader, copy action, and auto refresh.
- Operational stability: Task 1 adds health status; Task 2 improves error display through shared `requestJson`; Task 4 verifies server and API behavior.
- No frontend build system: file structure and Task 2 keep a single `console.html`.

**Placeholder scan:** No TBD, TODO, or unspecified implementation steps remain.

**Type consistency:** `/api/health` fields in Task 1 match the `health` object consumed by Task 2. Existing API fields match `worker_to_dict()` and `task_to_dict()` output.
