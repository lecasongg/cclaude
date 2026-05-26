# 牛马控制台重做 · 报刊野兽派 / 档案夹布局 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `web/console.html` 从现有 indigo/通用 SaaS 风格重做为「报刊野兽派 + 档案夹三标签」，功能不增不减，后端零改动。

**Architecture:** 单文件 Alpine + Tailwind CDN（不变）。新增 Alpine 状态 `activeTab` + `localStorage` 记忆；三标签 `x-show` 切换；配置 / 规则面板从侧栏内联改为居中模态。视觉用 `<style type="text/tailwindcss">` 内的 `@layer components` 增加 brutalist 设计令牌。

**Tech Stack:** HTML, Tailwind CDN, Alpine.js 3.x（全部沿用现有）。

**Spec:** `docs/superpowers/specs/2026-05-26-niuma-console-redesign-design.md`

**测试策略：** 项目无前端测试基建（不在本次范围）。每个任务后：
1. 跑 `pytest -q` 确认后端无回归（应当全绿，因为没动后端）
2. 在浏览器打开 `http://127.0.0.1:8846/` 做对应的手动检查
3. 任务末尾的 commit 是验证通过后再执行

**全程注意（来自 karpathy-guidelines）：**
- 只做 spec 里写的，不顺手"改进"无关代码
- 不引入新的依赖、不引入构建链
- 每一行变动都能追溯到 spec 的某条决定
- 出现"现状还可以但我想优化"的念头 → 跳过

---

## Task 0: 启动基线（pytest 兜底 + 视觉基线截图）

**Files:** 无修改

- [ ] **Step 1: 跑 pytest 基线**

```bash
cd /d/claude-code/cclaude
pytest -q
```

Expected: 全绿。如果有红的，**停下**，先和用户确认是否是预先存在的失败再继续。

- [ ] **Step 2: 启动 worker server 看现状**

```powershell
cd D:\claude-code\cclaude
$env:PYTHONPATH="D:\claude-code"
python worker_server.py
```

打开 <http://127.0.0.1:8846/> 确认页面能开、状态卡有数据。这是我们之后每步的对照基线。

- [ ] **Step 3: 不 commit**（这一步只是确认起点干净）

---

## Task 1: 添加 brutalist 设计令牌（CSS 层）

**Files:**
- Modify: `web/console.html:9-19`（`<style type="text/tailwindcss">` 块）

**目标：** 在现有 `@layer components` 块里追加 brutalist 工具类，与现有 `.panel/.btn-primary/.field` 并存（不删旧的，新旧暂时共存）。这样可以分步迁移、随时回退到旧样式做对比。

- [ ] **Step 1: 在 head 添加 body 基础 brutalist 类与令牌**

把 `web/console.html` 的 `<style type="text/tailwindcss">` 块（第 9–19 行）替换为：

```html
  <style type="text/tailwindcss">
    @layer base {
      :root {
        --paper: #f4f1ea;
        --ink: #111111;
        --ink-soft: #3a3a3a;
        --muted: #7a7468;
        --accent: #b00020;
        --success: #1f6b3a;
      }
    }
    @layer components {
      /* === 旧类（保留，迁移完成前不删）=== */
      .panel { @apply rounded-2xl border border-white/10 bg-[#0f1011]/90 p-5; }
      .panel-soft { @apply rounded-xl border border-white/10 bg-black/30 p-4; }
      .btn-primary { @apply rounded-lg bg-[#5e6ad2] px-4 py-2 text-sm font-medium text-white hover:bg-[#828fff] disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400; }
      .btn-secondary { @apply rounded-lg border border-white/10 bg-[#101111] px-4 py-2 text-sm text-zinc-200 hover:border-white/20 hover:bg-white/5 disabled:cursor-not-allowed disabled:text-zinc-600; }
      .field { @apply rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-zinc-100 outline-none ring-[#5e6ad2]/40 placeholder:text-zinc-600 focus:ring-2; }
      .chip { @apply rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-zinc-300; }
      .status-dot { @apply inline-block h-2 w-2 rounded-full; }

      /* === 新类（brutalist）=== */
      .br-card { @apply border-[1.5px] border-[var(--ink)] bg-[var(--paper)] p-4; }
      .br-card-tight { @apply border-[1.5px] border-[var(--ink)] bg-[var(--paper)] p-3; }
      .br-divider { @apply border-t-[3px] border-double border-[var(--ink)] my-4; }
      .br-rule { @apply border-t-[1.5px] border-[var(--ink)] my-3; }
      .br-h1 { @apply text-3xl font-black tracking-tight text-[var(--ink)] md:text-4xl; font-family: Georgia, 'Songti SC', '宋体', serif; letter-spacing: -0.5px; }
      .br-h2 { @apply text-xl font-black text-[var(--ink)]; font-family: Georgia, 'Songti SC', '宋体', serif; }
      .br-h3 { @apply text-base font-bold text-[var(--ink)]; font-family: Georgia, 'Songti SC', '宋体', serif; }
      .br-label { @apply font-mono text-[10px] uppercase tracking-[2px] text-[var(--ink-soft)]; }
      .br-mono { @apply font-mono text-xs text-[var(--ink-soft)]; }
      .br-tag { @apply inline-block border-[1.5px] border-[var(--ink)] bg-[var(--paper)] px-2 py-[2px] font-mono text-[10px] uppercase tracking-[1px] text-[var(--ink)]; }
      .br-tag-on { @apply inline-block border-[1.5px] border-[var(--ink)] bg-[var(--ink)] px-2 py-[2px] font-mono text-[10px] uppercase tracking-[1px] text-[var(--paper)]; }
      .br-tag-success { @apply inline-block border-[1.5px] border-[var(--success)] bg-[var(--paper)] px-2 py-[2px] font-mono text-[10px] uppercase tracking-[1px] text-[var(--success)]; }
      .br-tag-failed { @apply inline-block border-[1.5px] border-[var(--accent)] bg-[var(--paper)] px-2 py-[2px] font-mono text-[10px] uppercase tracking-[1px] text-[var(--accent)]; }
      .br-tag-muted { @apply inline-block px-2 py-[2px] font-mono text-[10px] uppercase tracking-[1px] text-[var(--muted)]; }
      .br-btn { @apply inline-flex items-center justify-center border-[1.5px] border-[var(--ink)] bg-[var(--paper)] px-4 py-2 font-mono text-xs uppercase tracking-[1px] text-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--paper)] disabled:cursor-not-allowed disabled:border-[var(--muted)] disabled:text-[var(--muted)] disabled:hover:bg-[var(--paper)]; transition: background-color 80ms, color 80ms; }
      .br-btn-primary { @apply inline-flex items-center justify-center border-[1.5px] border-[var(--ink)] bg-[var(--ink)] px-4 py-2 font-mono text-xs uppercase tracking-[1px] text-[var(--paper)] hover:bg-[var(--paper)] hover:text-[var(--ink)] disabled:cursor-not-allowed disabled:bg-[var(--muted)] disabled:border-[var(--muted)] disabled:hover:bg-[var(--muted)] disabled:hover:text-[var(--paper)]; transition: background-color 80ms, color 80ms; }
      .br-input { @apply w-full bg-transparent border-0 border-b-[1.5px] border-[var(--ink)] px-1 py-2 text-sm text-[var(--ink)] outline-none placeholder:text-[var(--muted)] focus:border-b-[3px]; font-family: Georgia, 'Songti SC', '宋体', serif; }
      .br-input-mono { @apply w-full bg-transparent border-0 border-b-[1.5px] border-[var(--ink)] px-1 py-2 font-mono text-sm text-[var(--ink)] outline-none placeholder:text-[var(--muted)] focus:border-b-[3px]; }
      .br-textarea { @apply w-full border-[1.5px] border-[var(--ink)] bg-[var(--paper)] p-3 text-sm text-[var(--ink)] outline-none placeholder:text-[var(--muted)] focus:border-[3px]; font-family: Georgia, 'Songti SC', '宋体', serif; resize: vertical; }
      .br-tab { @apply inline-flex items-center px-4 py-2 font-mono text-xs uppercase tracking-[2px] text-[var(--ink-soft)] hover:text-[var(--ink)] cursor-pointer; }
      .br-tab-active { @apply inline-flex items-center bg-[var(--ink)] px-4 py-2 font-mono text-xs uppercase tracking-[2px] text-[var(--paper)] cursor-default; }
      .br-modal-mask { @apply fixed inset-0 z-40 flex items-center justify-center; background-color: rgba(244, 241, 234, 0.85); }
      .br-modal { @apply relative z-50 max-w-[560px] w-[90vw] border-[1.5px] border-[var(--ink)] bg-[var(--paper)] p-6; }
    }
  </style>
```

- [ ] **Step 2: 在 body 上把背景改成纸色（为后续整体迁移做准备）**

把 `web/console.html` 的 body 标签（约第 21 行）从：

```html
<body class="min-h-screen bg-[#010102] text-zinc-100 antialiased">
```

改为：

```html
<body class="min-h-screen bg-[var(--paper)] text-[var(--ink)] antialiased" style="font-family: Georgia, 'Songti SC', '宋体', serif;">
```

- [ ] **Step 3: 视觉冒烟验证**

打开浏览器 <http://127.0.0.1:8846/>，刷新。**预期：** 整体背景变成米色纸底；现有黑色面板因为 `.panel` 类用了 `bg-[#0f1011]/90`，所以面板仍是深色（这是正常的，下面任务会替换）。即"米底 + 深色面板"的过渡态。

- [ ] **Step 4: pytest 兜底**

```bash
pytest -q
```

Expected: 全绿（没动后端）。

- [ ] **Step 5: Commit**

```bash
git add web/console.html
git commit -m "ui: add brutalist design tokens and paper background"
```

---

## Task 2: 添加 activeTab 状态 + localStorage 记忆

**Files:**
- Modify: `web/console.html:328-365`（Alpine 数据模型 + init）

- [ ] **Step 1: 在 Alpine 数据模型新增 activeTab / 模态 flag**

在 `web/console.html` 第 350 行（`autoRefresh: false,` 这一行**之前**）插入三行：

```js
        activeTab: 'pipeline',
        configModalOpen: false,
        documentModalOpen: false,
```

整段看起来会是：

```js
        events: [],
        alert: null,
        activeTab: 'pipeline',
        configModalOpen: false,
        documentModalOpen: false,
        autoRefresh: false,
```

- [ ] **Step 2: 在 init() 里读 localStorage**

把 `init()` 方法（约第 363–365 行）改为：

```js
        async init() {
          const saved = localStorage.getItem('niuma.activeTab');
          if (saved === 'dispatch' || saved === 'pipeline' || saved === 'archive') {
            this.activeTab = saved;
          }
          document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
              this.configModalOpen = false;
              this.documentModalOpen = false;
            }
          });
          await this.refreshAll();
        },
```

- [ ] **Step 3: 在 record() 之前新增 setActiveTab() 方法**

在最后一个方法 `record()` 之前（约第 670 行）插入：

```js
        setActiveTab(tab) {
          this.activeTab = tab;
          localStorage.setItem('niuma.activeTab', tab);
        },
```

- [ ] **Step 4: 修改 openWorkerConfig / openDocumentInstall 同步打开模态**

把 `openWorkerConfig` 末尾添加一行 `this.configModalOpen = true;`，把 `openDocumentInstall` 末尾添加 `this.documentModalOpen = true;`。即：

`openWorkerConfig` 改为（注意末尾新增一行）：

```js
        openWorkerConfig(worker) {
          this.selectedWorker = worker.worker_id;
          this.configWorker = worker;
          this.documentInstallWorker = null;
          this.configForm = {
            provider: worker.provider || '',
            base_url: worker.base_url || '',
            model: worker.model || '',
            role: worker.role || '',
            api_key: ''
          };
          this.configModalOpen = true;
        },
```

`openDocumentInstall` 改为：

```js
        openDocumentInstall(worker) {
          this.selectedWorker = worker.worker_id;
          this.configWorker = null;
          this.documentInstallWorker = worker;
          this.documentModalOpen = true;
        },
```

- [ ] **Step 5: 浏览器验证 activeTab 持久化（用 devtools 验证）**

打开浏览器 devtools console，输入：

```js
document.querySelector('main').__x.$data.activeTab
```

应当返回 `'pipeline'`。再输入：

```js
document.querySelector('main').__x.$data.setActiveTab('dispatch')
```

刷新页面，再次执行第一行，应返回 `'dispatch'`。然后再调一次 `setActiveTab('pipeline')` 恢复默认。

（注：此时 UI 上看不到变化，因为标签栏还没加 — 下一个任务做。）

- [ ] **Step 6: Commit**

```bash
git add web/console.html
git commit -m "ui: add activeTab state with localStorage persistence and modal flags"
```

---

## Task 3: 替换页面骨架（左竖条 + 报头 + 标签栏）

**Files:**
- Modify: `web/console.html:22-71`（`<main>` 开头到 alert 行之前）

**目标：** 替换最外层 main 容器和顶部 header，搭起新骨架。所有原有 `<section>...</section>` 内容**暂时不动**，紧跟在新骨架内的占位 wrapper 里（用 `x-show="activeTab === 'pipeline'"` 包住，这样切换标签时能看到效果）。

- [ ] **Step 1: 替换 main + header + alert 区域**

把 `web/console.html` 从第 22 行的 `<main x-data="factoryConsole()"...` 一直到第 71 行的 `</div>` 闭合 alert 这一段，整段替换为：

```html
  <main x-data="factoryConsole()" x-init="init()" class="min-h-screen flex">
    <!-- 左侧垂直窄条 -->
    <aside class="w-8 shrink-0 border-r-[1.5px] border-[var(--ink)] flex items-start justify-center pt-6 sticky top-0 h-screen">
      <div class="font-mono text-[10px] uppercase tracking-[3px] text-[var(--ink)]" style="writing-mode: vertical-rl; transform: rotate(180deg);">NIUMA · WORKSHOP · N°01</div>
    </aside>

    <!-- 右侧主区 -->
    <div class="flex-1 min-w-0 flex flex-col">
      <!-- 顶部报头 -->
      <header class="sticky top-0 z-30 bg-[var(--paper)] border-b-[1.5px] border-[var(--ink)] px-8 pt-6 pb-4">
        <div class="flex items-end justify-between gap-6">
          <div>
            <div class="br-label">N°01 · LOCAL AGENT WORKSHOP</div>
            <h1 class="br-h1 mt-2">本地牛马工厂.</h1>
            <p class="br-mono mt-2">逆向 / 编写 / 交付 — 一条流水线</p>
          </div>
          <div class="flex flex-col items-end gap-2">
            <div class="br-mono" x-text="new Date().toISOString().slice(0,10)"></div>
            <div class="flex gap-2">
              <span class="br-tag" x-text="`SERVER · ${health.status === 'ok' ? 'ONLINE' : '...'}`"></span>
              <span class="br-tag" x-text="`UNITS · ${workers.length}`"></span>
            </div>
            <div class="flex gap-2 items-center mt-1">
              <input x-model="baseUrl" class="br-input-mono w-72 py-1" aria-label="Server URL">
              <input x-model="token" type="password" class="br-input-mono w-44 py-1" aria-label="Hermes Token">
              <button @click="refreshAll" :disabled="isRefreshing" class="br-btn-primary !py-1" x-text="isRefreshing ? '...' : '刷新'"></button>
            </div>
          </div>
        </div>

        <!-- 标签栏 -->
        <nav class="flex gap-1 mt-4 border-t-[1.5px] border-[var(--ink)] pt-3">
          <button @click="setActiveTab('dispatch')" :class="activeTab === 'dispatch' ? 'br-tab-active' : 'br-tab'">[ DISPATCH ]</button>
          <button @click="setActiveTab('pipeline')" :class="activeTab === 'pipeline' ? 'br-tab-active' : 'br-tab'">[ PIPELINE ]</button>
          <button @click="setActiveTab('archive')" :class="activeTab === 'archive' ? 'br-tab-active' : 'br-tab'">[ ARCHIVE ]</button>
        </nav>
      </header>

      <!-- Alert（重新设计为 brutalist）-->
      <div x-show="alert" x-transition class="mx-8 mt-4 border-[1.5px] px-4 py-3 text-sm" :class="alert && alert.type === 'error' ? 'border-[var(--accent)] text-[var(--accent)]' : 'border-[var(--ink)] text-[var(--ink)]'">
        <div class="flex items-start justify-between gap-4">
          <p x-text="alert ? alert.message : ''"></p>
          <button @click="alert = null" class="br-mono hover:text-[var(--ink)]">[ × ]</button>
        </div>
      </div>

      <!-- 内容区：三个标签 -->
      <div class="flex-1 px-8 py-6">
        <!-- DISPATCH（暂时空，下一任务填充）-->
        <section x-show="activeTab === 'dispatch'" class="space-y-6">
          <h2 class="br-h2">派工 · DISPATCH</h2>
          <div class="br-divider"></div>
          <p class="br-mono">（暂留空，下个任务填充）</p>
        </section>

        <!-- PIPELINE（包住所有旧内容，先把页面跑起来）-->
        <section x-show="activeTab === 'pipeline'" class="space-y-6">
          <h2 class="br-h2">流水线 · PIPELINE</h2>
          <div class="br-divider"></div>
          <!-- ↓↓↓ 下面跟旧的所有 section ↓↓↓ -->
```

**重要：** 替换后，原来从第 73 行开始的 `<section class="grid gap-3 lg:grid-cols-4">`（即 4 张统计卡那一段）以及之后所有 section 都**保留不动**。

- [ ] **Step 2: 在文件末尾把所有旧内容统一关闭**

找到 `</main>` 之前的最后一个 `</section>`（约第 324 行），在 `</main>` 之前**插入两行收尾**，把上面新开的 `pipeline x-show section` 和 main 内容区 div 关掉：

定位 `</main>` 行（约 325 行），把它之前两行追加：

```html
          <!-- ↑↑↑ 旧的 section 全部包在 PIPELINE 标签下 ↑↑↑ -->
        </section>

        <!-- ARCHIVE（暂时空）-->
        <section x-show="activeTab === 'archive'" class="space-y-6">
          <h2 class="br-h2">档案 · ARCHIVE</h2>
          <div class="br-divider"></div>
          <p class="br-mono">（暂留空，下个任务填充）</p>
        </section>
      </div>
    </div>
  </main>
```

- [ ] **Step 3: 浏览器验证骨架**

刷新 <http://127.0.0.1:8846/>。**预期：**
- 顶部出现米底报头 "本地牛马工厂."
- 左侧出现 32px 黑边窄条，里面有竖排 "NIUMA · WORKSHOP · N°01"
- 报头下有三个标签 `[ DISPATCH ] [ PIPELINE ] [ ARCHIVE ]`，PIPELINE 高亮
- PIPELINE 标签下还是原有的所有面板（深色卡 + 米底是过渡态，正常）
- 点 `[ DISPATCH ]` 看到"派工 · DISPATCH"标题 + 占位文字
- 点 `[ ARCHIVE ]` 看到"档案 · ARCHIVE"标题 + 占位文字
- 刷新页面，停留的标签保持不变

- [ ] **Step 4: pytest 兜底**

```bash
pytest -q
```

Expected: 全绿。

- [ ] **Step 5: Commit**

```bash
git add web/console.html
git commit -m "ui: replace shell with vertical strip, masthead and three-tab nav"
```

---

## Task 4: 把单工位派工 + 链式派工移到 DISPATCH 标签

**Files:**
- Modify: `web/console.html`（DISPATCH 占位 + 现 PIPELINE 中的派工 section）

**当前状态：** 现在所有派工 section（单工位派工、链式派工、文件输入）都在 PIPELINE 标签下（因为是旧代码的一部分）。这一步把它们从 PIPELINE 区移到 DISPATCH 区，并重写成 brutalist 样式。

- [ ] **Step 1: 删除 PIPELINE 区里的派工 section**

在 `web/console.html` 里找到包含派工的两个 section（原行 136–183，即 `<section class="panel">` → `<h2>单工位派工</h2>` 和 `<h2>牛马1 → 牛马2 链式派工</h2>` 两段）。**整段删除**，包括它们外层的 `<div class="grid gap-5">` wrapper（如果删完只剩配置弹窗那一段在内）。

更稳的做法：删除从行（含 `单工位派工`）到行（含 `启动链式派工</button>` 之后那个 `</section>`）的整段范围。

**注意：** 不要碰 `<section x-show="configWorker">` 和 `<section x-show="documentInstallWorker">` 这两段（它们是配置 / 规则面板，Task 6 处理）。

- [ ] **Step 2: 在 DISPATCH 标签下填充派工 UI**

把之前的 DISPATCH 占位 section 替换为：

```html
        <!-- DISPATCH -->
        <section x-show="activeTab === 'dispatch'" class="space-y-8 max-w-3xl">
          <div>
            <h2 class="br-h2">派工 · DISPATCH</h2>
            <div class="br-divider"></div>
          </div>

          <!-- N°01 单工位派工 -->
          <article class="space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <div class="br-label">N°01</div>
                <h3 class="br-h3 mt-1">单工位派工</h3>
              </div>
              <span class="br-tag" x-text="selectedWorker"></span>
            </div>
            <select x-model="selectedWorker" class="br-input-mono">
              <template x-for="worker in workers" :key="worker.worker_id">
                <option :value="worker.worker_id" x-text="`${worker.display_name} · ${worker.worker_id}`"></option>
              </template>
            </select>
            <textarea x-model="prompt" rows="5" placeholder="给选中的牛马下达任务..." class="br-textarea"></textarea>
            <div class="flex justify-end">
              <button @click="delegateTask" :disabled="isDelegating || !prompt.trim()" class="br-btn-primary" x-text="isDelegating ? '派工中...' : '[ 发送任务 ]'"></button>
            </div>
          </article>

          <div class="br-rule"></div>

          <!-- N°02 链式派工 -->
          <article class="space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <div class="br-label">N°02</div>
                <h3 class="br-h3 mt-1">牛马1 → 牛马2 链式派工</h3>
              </div>
              <span class="br-tag">CHAIN</span>
            </div>
            <textarea x-model="chainPrompt" rows="4" placeholder="给牛马1的逆向分析任务..." class="br-textarea"></textarea>

            <div class="br-card space-y-3">
              <div>
                <div class="br-label">FILE INPUT</div>
                <p class="br-mono mt-1">可读本机路径，也可上传 JSP / JS / SQL / Java；系统先读正文再注入牛马1提示词。</p>
              </div>
              <div class="grid grid-cols-[1fr_auto] gap-2">
                <input x-model="filePath" placeholder="D:\\project\\web\\user.jsp" class="br-input-mono">
                <button @click="loadLocalPath" :disabled="isLoadingFileContext || !filePath.trim()" class="br-btn" x-text="isLoadingFileContext ? '读取中...' : '[ 读取路径 ]'"></button>
              </div>
              <input @change="uploadFiles" multiple type="file" class="br-input-mono file:mr-3 file:border-0 file:bg-[var(--ink)] file:px-3 file:py-1 file:text-[var(--paper)] file:font-mono file:text-xs file:uppercase">
              <div x-show="fileContext.files.length" class="space-y-2 border-t-[1.5px] border-[var(--ink)] pt-3">
                <div class="flex items-center justify-between">
                  <p class="br-mono" x-text="`已载入 ${fileContext.files.length} 个文件`"></p>
                  <button @click="clearFileContext" class="br-mono hover:text-[var(--accent)]">[ 清空 ]</button>
                </div>
                <template x-for="file in fileContext.files" :key="file.path">
                  <p class="font-mono text-xs text-[var(--ink-soft)] truncate" x-text="`${file.path} · ${formatBytes(file.size)}`"></p>
                </template>
              </div>
            </div>

            <div>
              <div class="br-label mb-2">NIUMA-2 INSTRUCTION</div>
              <textarea x-model="nextInstruction" rows="3" class="br-textarea"></textarea>
            </div>
            <div class="flex justify-end">
              <button @click="chainTask" :disabled="isChaining || !chainPrompt.trim()" class="br-btn-primary" x-text="isChaining ? '执行中...' : '[ 启动链式派工 ]'"></button>
            </div>
          </article>
        </section>
```

- [ ] **Step 3: 浏览器验证**

刷新页面，点 `[ DISPATCH ]`。**预期：**
- 看到米底 + 黑字 + serif 字体的 DISPATCH 区
- N°01 单工位派工：select + textarea 用底线样式，按钮是黑底米字 `[ 发送任务 ]`
- N°02 链式派工：textarea + 文件输入卡片 + niuma-2 指令 + 启动按钮
- 试着发一个空 prompt → 按钮禁用
- 填一个简短 prompt（比如 "测试一下"）→ 看到顶部 alert 出现（黑边或深红边）

PIPELINE 标签下应当**不再**有派工 section（只剩统计卡、工位卡、配置弹窗、Timeline）。

- [ ] **Step 4: pytest**

```bash
pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add web/console.html
git commit -m "ui: move single + chain dispatch into DISPATCH tab with brutalist style"
```

---

## Task 5: PIPELINE 标签 — 统计卡 + 工位卡上下叠 + 合并规则按钮

**Files:**
- Modify: `web/console.html`（PIPELINE 区现存内容）

- [ ] **Step 1: 替换 4 张统计卡**

在 PIPELINE 标签内找到现在的 `<section class="grid gap-3 lg:grid-cols-4">` 那一段（4 张统计卡），整段替换为：

```html
          <section class="grid grid-cols-4 gap-3">
            <div class="br-card-tight">
              <div class="br-label">SERVER</div>
              <div class="mt-3 flex items-center gap-2">
                <span class="inline-block w-2 h-2" :class="health.status === 'ok' ? 'bg-[var(--success)]' : 'bg-[var(--accent)]'"></span>
                <span class="br-h3" x-text="health.status === 'ok' ? 'ONLINE' : 'UNKNOWN'"></span>
              </div>
              <p class="br-mono mt-2 break-all" x-text="baseUrl"></p>
            </div>
            <div class="br-card-tight">
              <div class="br-label">WORKERS</div>
              <p class="br-h1 mt-3 !text-3xl" x-text="`${workers.length} / ${health.workers_total || workers.length}`"></p>
              <p class="br-mono mt-2">已加载工位</p>
            </div>
            <div class="br-card-tight">
              <div class="br-label">API KEYS</div>
              <p class="br-h1 mt-3 !text-3xl" x-text="`${workersWithKeys()} / ${workers.length}`"></p>
              <p class="br-mono mt-2">已配置密钥</p>
            </div>
            <div class="br-card-tight">
              <div class="br-label">AUTO REFRESH</div>
              <button @click="toggleAutoRefresh" class="br-btn mt-3 w-full" x-text="autoRefresh ? '[ AUTO · ON ]' : '[ AUTO · OFF ]'"></button>
              <p class="br-mono mt-2">每 5 秒刷新</p>
            </div>
          </section>
```

- [ ] **Step 2: 替换牛马流水线 + 工位卡**

找到现在的 `<section class="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">` 那一段（这个 grid 现在只剩工位卡那一边，配置面板那一边因为 Task 4 删掉了大半）。整段（含里面的工位 article template）替换为：

```html
          <section>
            <div class="flex items-center justify-between">
              <div>
                <div class="br-label">PIPELINE</div>
                <h3 class="br-h3 mt-1">牛马流水线</h3>
              </div>
              <span class="br-tag">niuma-1 → niuma-2</span>
            </div>
            <div class="mt-4 space-y-4">
              <template x-for="(worker, index) in workers" :key="worker.worker_id">
                <article @click="selectedWorker = worker.worker_id" class="br-card cursor-pointer" :class="selectedWorker === worker.worker_id ? 'bg-[var(--paper)] border-[3px]' : ''">
                  <div class="flex items-start justify-between gap-4">
                    <div class="flex items-start gap-3 min-w-0">
                      <span class="br-tag-on shrink-0" x-text="`N°0${index + 1}`"></span>
                      <div class="min-w-0">
                        <div class="br-label" x-text="worker.worker_id === 'niuma-1' ? 'UNIT 01 · REVERSE' : 'UNIT 02 · WRITER'"></div>
                        <h3 class="br-h3 mt-1" x-text="worker.display_name"></h3>
                        <p class="text-sm text-[var(--ink-soft)] mt-2" x-text="worker.role"></p>
                      </div>
                    </div>
                    <div class="flex items-center gap-2 shrink-0">
                      <span :class="brStatusClass(worker.status)" x-text="`[ ${worker.status.toUpperCase()} ]`"></span>
                      <button @click.stop="openWorkerConfig(worker)" class="br-btn !py-1">[ 配置 ]</button>
                      <button x-show="worker.worker_id === 'niuma-1'" @click.stop="openDocumentInstall(worker)" class="br-btn !py-1">[ 规则 ]</button>
                    </div>
                  </div>

                  <div class="br-rule"></div>

                  <div class="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div class="br-label">PROVIDER / MODEL</div>
                      <p class="mt-1 truncate"><span x-text="worker.provider"></span> · <span x-text="worker.model"></span></p>
                    </div>
                    <div>
                      <div class="br-label">API KEY</div>
                      <p class="mt-1"><span class="br-mono" x-text="worker.api_key_env"></span> · <span :class="worker.api_key_configured ? 'text-[var(--success)]' : 'text-[var(--accent)]'" x-text="worker.api_key_configured ? '已配置' : '未配置'"></span></p>
                    </div>
                    <div class="col-span-2">
                      <div class="br-label">BASE URL</div>
                      <p class="mt-1 br-mono break-all" x-text="worker.base_url || '未配置'"></p>
                    </div>
                    <div class="col-span-2">
                      <div class="br-label">任务材料</div>
                      <div class="mt-2 flex flex-wrap gap-2">
                        <span :class="documentInstalled(worker, 'task_manual') ? 'br-tag-success' : 'br-tag-failed'" x-text="documentInstalled(worker, 'task_manual') ? '任务手册 ✓' : '缺任务手册'"></span>
                        <span :class="documentInstalled(worker, 'conversion_rules') ? 'br-tag-success' : 'br-tag-failed'" x-text="documentInstalled(worker, 'conversion_rules') ? '转换规则 ✓' : '缺转换规则'"></span>
                      </div>
                    </div>
                    <div class="col-span-2">
                      <div class="br-label">当前任务</div>
                      <p class="mt-1 text-[var(--ink-soft)] line-clamp-2" x-text="currentTaskPrompt(worker) || '— 空闲 —'"></p>
                    </div>
                  </div>
                </article>
              </template>
            </div>
          </section>
```

- [ ] **Step 3: 新增 brStatusClass 方法**

在 Alpine 数据模型里找到现有 `statusClass(status)` 方法（约第 648 行），紧接它**之后**新增：

```js
        brStatusClass(status) {
          if (status === 'succeeded') return 'br-tag-success';
          if (status === 'failed') return 'br-tag-failed';
          if (status === 'running') return 'br-tag-on';
          if (status === 'idle') return 'br-tag-muted';
          return 'br-tag';
        },
```

- [ ] **Step 4: 浏览器验证**

刷新 <http://127.0.0.1:8846/>。**预期：**
- PIPELINE 标签下：4 张统计卡 brutalist 风格（米底 + 黑边）
- AUTO 按钮显示 `[ AUTO · OFF ]`；点击后 `[ AUTO · ON ]`
- 两个工位卡**上下叠**（不是左右并排），每个卡里有 N°0X 黑底米字标签
- 每个工位卡只有**一个**「规则」按钮（牛马2 上则没有规则按钮，因为 `x-show` 条件）
- 任务材料标签是 brutalist 风格（绿框已安装 / 红框未安装）
- 状态徽章是 `[ RUNNING ]` 黑底反白等矩形

- [ ] **Step 5: pytest**

```bash
pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add web/console.html
git commit -m "ui: restyle pipeline stat cards and stacked worker cards, merge document button"
```

---

## Task 6: 配置 + 规则面板改为居中模态

**Files:**
- Modify: `web/console.html`（删除内联 panel + 在内容区外新增 modal）

**目标：** 现存 `<section x-show="configWorker">` 和 `<section x-show="documentInstallWorker">` 还在旧位置（Task 4 删掉的是派工 section，把这两段留下了）。把它们改成居中模态，并接 `configModalOpen` / `documentModalOpen` 标志位。

- [ ] **Step 1: 删除旧的内联面板**

在 `web/console.html` 里找到这两段：

```html
<section x-show="configWorker" class="panel border-indigo-400/30 bg-indigo-500/10">
  ...
</section>

<section x-show="documentInstallWorker" class="panel border-indigo-400/30 bg-indigo-500/10">
  ...
</section>
```

**完整删除**这两段。

- [ ] **Step 2: 在 `</main>` 之前新增两个模态**

在 `web/console.html` 的 `</main>` 闭合标签**之前**插入：

```html
      <!-- 配置模态 -->
      <div x-show="configModalOpen" x-transition.opacity class="br-modal-mask" @click.self="configModalOpen = false">
        <div class="br-modal">
          <div class="flex items-center justify-between">
            <div>
              <div class="br-label">CONFIG</div>
              <h3 class="br-h3 mt-1">工位配置</h3>
            </div>
            <button @click="configModalOpen = false" class="br-mono hover:text-[var(--accent)]">[ × ]</button>
          </div>
          <div class="br-rule"></div>
          <div class="space-y-3">
            <div>
              <div class="br-label">PROVIDER</div>
              <input x-model="configForm.provider" class="br-input">
            </div>
            <div>
              <div class="br-label">BASE URL</div>
              <input x-model="configForm.base_url" placeholder="http://host:port/v1" class="br-input-mono">
            </div>
            <div>
              <div class="br-label">MODEL</div>
              <input x-model="configForm.model" class="br-input">
            </div>
            <div>
              <div class="br-label">ROLE</div>
              <input x-model="configForm.role" class="br-input">
            </div>
            <div>
              <div class="br-label">API KEY</div>
              <input x-model="configForm.api_key" type="password" placeholder="留空则保留原 key" class="br-input-mono">
            </div>
            <p class="text-xs text-[var(--accent)]">本地试运行会把 key 保存到 runtime_config.json；不要分享这个文件。</p>
            <div class="flex justify-end pt-2">
              <button @click="saveWorkerConfig" :disabled="isSavingConfig" class="br-btn-primary" x-text="isSavingConfig ? '保存中...' : '[ 保存配置 ]'"></button>
            </div>
          </div>
        </div>
      </div>

      <!-- 规则模态 -->
      <div x-show="documentModalOpen" x-transition.opacity class="br-modal-mask" @click.self="documentModalOpen = false">
        <div class="br-modal">
          <div class="flex items-center justify-between">
            <div>
              <div class="br-label">DOCUMENTS</div>
              <h3 class="br-h3 mt-1">牛马1 任务材料</h3>
            </div>
            <button @click="documentModalOpen = false" class="br-mono hover:text-[var(--accent)]">[ × ]</button>
          </div>
          <div class="br-rule"></div>
          <p class="text-sm text-[var(--ink-soft)]">上传后会保存为牛马1 固定任务材料；执行前先读任务手册，再读转换规则。</p>

          <div class="mt-4 space-y-4">
            <div class="br-card-tight space-y-2">
              <div class="flex items-center justify-between">
                <div>
                  <div class="br-label">任务手册</div>
                  <p class="br-mono mt-1" x-text="installedDocumentText(documentInstallWorker, 'task_manual')"></p>
                </div>
                <span :class="documentInstalled(documentInstallWorker, 'task_manual') ? 'br-tag-success' : 'br-tag-failed'" x-text="documentInstalled(documentInstallWorker, 'task_manual') ? '[ 已安装 ]' : '[ 未安装 ]'"></span>
              </div>
              <input @change="installDocument($event, 'task_manual')" type="file" class="br-input-mono file:mr-3 file:border-0 file:bg-[var(--ink)] file:px-3 file:py-1 file:text-[var(--paper)] file:font-mono file:text-xs file:uppercase">
            </div>

            <div class="br-card-tight space-y-2">
              <div class="flex items-center justify-between">
                <div>
                  <div class="br-label">转换规则</div>
                  <p class="br-mono mt-1" x-text="installedDocumentText(documentInstallWorker, 'conversion_rules')"></p>
                </div>
                <span :class="documentInstalled(documentInstallWorker, 'conversion_rules') ? 'br-tag-success' : 'br-tag-failed'" x-text="documentInstalled(documentInstallWorker, 'conversion_rules') ? '[ 已安装 ]' : '[ 未安装 ]'"></span>
              </div>
              <input @change="installDocument($event, 'conversion_rules')" type="file" class="br-input-mono file:mr-3 file:border-0 file:bg-[var(--ink)] file:px-3 file:py-1 file:text-[var(--paper)] file:font-mono file:text-xs file:uppercase">
            </div>
          </div>
        </div>
      </div>
```

- [ ] **Step 3: 浏览器验证三种关闭方式**

刷新 <http://127.0.0.1:8846/>，进 PIPELINE 标签。

- 点工位卡上 `[ 配置 ]` → 配置模态居中弹出
  - 按 ESC → 关闭 ✓
  - 再点开，点蒙版（模态外的米色半透明区域）→ 关闭 ✓
  - 再点开，点 `[ × ]` → 关闭 ✓
- 点牛马1卡的 `[ 规则 ]` → 规则模态弹出
  - 同样三种关闭方式都验证 ✓

- [ ] **Step 4: pytest**

```bash
pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add web/console.html
git commit -m "ui: convert config and document panels to centered modals with esc/backdrop/× close"
```

---

## Task 7: 把任务历史 + 产物阅读器 移到 ARCHIVE 标签

**Files:**
- Modify: `web/console.html`（ARCHIVE 占位 + 历史/产物 section）

- [ ] **Step 1: 找到现在的历史 + 产物 section**

它现在在 PIPELINE 标签下。找到 `<section class="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">` 这一段（包含「任务历史」和「产物阅读器」），**整段删除**（包含外层 grid section）。

- [ ] **Step 2: 在 ARCHIVE 占位 section 里填充**

把之前 ARCHIVE 占位区替换为：

```html
        <!-- ARCHIVE -->
        <section x-show="activeTab === 'archive'" class="space-y-4">
          <div>
            <h2 class="br-h2">档案 · ARCHIVE</h2>
            <div class="br-divider"></div>
          </div>
          <div class="grid gap-5 grid-cols-[1fr_1.4fr]">
            <!-- 左：任务历史 -->
            <div>
              <div class="flex items-center justify-between">
                <div>
                  <div class="br-label">HISTORY</div>
                  <h3 class="br-h3 mt-1">任务历史</h3>
                </div>
                <div class="flex gap-2">
                  <select x-model="taskFilter.worker" class="br-input-mono !py-1 !w-36">
                    <option value="all">全部工位</option>
                    <template x-for="worker in workers" :key="worker.worker_id">
                      <option :value="worker.worker_id" x-text="worker.worker_id"></option>
                    </template>
                  </select>
                  <select x-model="taskFilter.status" class="br-input-mono !py-1 !w-36">
                    <option value="all">全部状态</option>
                    <option value="succeeded">succeeded</option>
                    <option value="failed">failed</option>
                    <option value="running">running</option>
                    <option value="pending">pending</option>
                  </select>
                </div>
              </div>
              <div class="mt-4 max-h-[640px] overflow-auto space-y-2 pr-1">
                <template x-for="task in filteredTasks()" :key="task.task_id">
                  <button @click="selectTask(task)" class="w-full text-left br-card-tight" :class="selectedTask && selectedTask.task_id === task.task_id ? 'border-[3px]' : ''">
                    <div class="flex items-center justify-between">
                      <span class="br-h3" x-text="task.worker_id"></span>
                      <span :class="brStatusClass(task.status)" x-text="`[ ${task.status.toUpperCase()} ]`"></span>
                    </div>
                    <p class="mt-2 text-sm line-clamp-2 text-[var(--ink-soft)]" x-text="task.prompt"></p>
                    <p class="mt-2 br-mono" x-text="task.task_id"></p>
                  </button>
                </template>
                <p x-show="filteredTasks().length === 0" class="br-card-tight text-center text-[var(--muted)]">— 暂无匹配任务 —</p>
              </div>
            </div>

            <!-- 右：产物阅读器 -->
            <div>
              <div class="flex items-center justify-between">
                <div>
                  <div class="br-label">ARTIFACT</div>
                  <h3 class="br-h3 mt-1">产物阅读器</h3>
                </div>
                <button @click="copyArtifact" :disabled="!artifactText()" class="br-btn !py-1">[ 复制产物 ]</button>
              </div>
              <template x-if="selectedTask">
                <div class="mt-4 space-y-3">
                  <div class="br-card-tight space-y-2">
                    <div class="flex flex-wrap gap-2">
                      <span class="br-tag" x-text="selectedTask.worker_id"></span>
                      <span :class="brStatusClass(selectedTask.status)" x-text="`[ ${selectedTask.status.toUpperCase()} ]`"></span>
                      <span class="br-tag" x-show="selectedTask.parent_task_id">[ HAS UPSTREAM ]</span>
                    </div>
                    <p class="br-mono" x-text="selectedTask.task_id"></p>
                    <p class="text-sm text-[var(--ink-soft)]" x-text="selectedTask.prompt"></p>
                    <p class="text-sm text-[var(--accent)]" x-show="selectedTask.error" x-text="selectedTask.error"></p>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <template x-for="artifactId in selectedTask.artifact_ids" :key="artifactId">
                      <button @click="loadArtifact(artifactId)" class="br-btn !py-1" x-text="artifactId"></button>
                    </template>
                  </div>
                  <pre class="max-h-[640px] overflow-auto whitespace-pre-wrap br-card-tight font-mono text-sm leading-7" x-text="artifactText() || '— 这个任务还没有产物 —'"></pre>
                </div>
              </template>
              <p x-show="!selectedTask" class="mt-4 br-card-tight text-center text-[var(--muted)]">— 选择左侧任务查看结果 —</p>
            </div>
          </div>
        </section>
```

- [ ] **Step 3: 浏览器验证**

刷新页面，点 `[ ARCHIVE ]`。**预期：**
- 左右两栏，左历史右产物
- 历史列表 brutalist 卡片，每条有 worker + 状态 + prompt + task_id
- 两个筛选下拉用底线样式
- 选一条任务 → 右侧产物区显示 meta + artifact_id 按钮 + 内容
- PIPELINE 标签下**不再**有历史/产物 section（只剩统计卡 + 工位卡 + Timeline）

- [ ] **Step 4: pytest**

```bash
pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add web/console.html
git commit -m "ui: move history and artifact reader into ARCHIVE tab with brutalist style"
```

---

## Task 8: PIPELINE 区底部 Timeline 重做

**Files:**
- Modify: `web/console.html`（Timeline section）

- [ ] **Step 1: 替换 Timeline section**

PIPELINE 标签下，找到现在最后一段 `<section class="panel"><h2>操作回执</h2>...` 那一段（原行 304–324），整段替换为：

```html
          <section>
            <div class="flex items-center justify-between">
              <div>
                <div class="br-label">TIMELINE</div>
                <h3 class="br-h3 mt-1">操作回执</h3>
              </div>
              <button @click="events = []" class="br-btn !py-1">[ 清空 ]</button>
            </div>
            <div class="mt-4 space-y-3">
              <template x-for="event in events" :key="event.id">
                <article class="br-card-tight">
                  <div class="flex items-center justify-between">
                    <span class="br-tag" x-text="event.type.toUpperCase()"></span>
                    <span class="br-mono" x-text="event.time"></span>
                  </div>
                  <pre class="mt-3 overflow-auto whitespace-pre-wrap text-sm leading-6 text-[var(--ink-soft)]" x-text="event.body"></pre>
                </article>
              </template>
              <p x-show="events.length === 0" class="br-mono">— 暂无操作回执 —</p>
            </div>
          </section>
```

- [ ] **Step 2: 浏览器验证**

刷新，进 PIPELINE 标签滚到底部。Timeline 显示 brutalist 风格事件卡。

- [ ] **Step 3: pytest**

```bash
pytest -q
```

- [ ] **Step 4: Commit**

```bash
git add web/console.html
git commit -m "ui: restyle timeline cards in pipeline tab"
```

---

## Task 9: 清理旧 CSS 类 + RUNBOOK 验证清单 + 端到端验收

**Files:**
- Modify: `web/console.html`（删除已无引用的旧类）
- Modify: `RUNBOOK.md`

- [ ] **Step 1: 检查旧类是否还有引用**

```bash
cd /d/claude-code/cclaude
grep -nE 'class="[^"]*\b(panel|panel-soft|btn-primary|btn-secondary|field|chip|status-dot)\b' web/console.html
```

Expected: 应当**没有**结果，或只有极少几处（说明几乎所有旧类已被 brutalist 类替换）。

- [ ] **Step 2: 删除已无引用的旧类**

如果上一步显示无引用，把 `web/console.html` 第 11–17 行（旧的 `.panel/.panel-soft/.btn-primary/.btn-secondary/.field/.chip/.status-dot` 那 7 行）整段删除。

如果还有引用：列出残留引用 → 把对应位置换成 brutalist 类 → 再删旧类。

- [ ] **Step 3: 在 RUNBOOK.md 末尾追加验证清单**

把以下内容追加到 `RUNBOOK.md` 末尾：

```markdown

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
```

- [ ] **Step 4: 端到端走一遍 RUNBOOK 清单**

按 RUNBOOK 的清单逐项执行，确保**每一项都打勾**。任何一项不通过 → 停下，定位问题 → 修 → 重跑清单。

- [ ] **Step 5: 跑后端测试**

```bash
pytest -q
```

Expected: 全绿。

- [ ] **Step 6: 用 git diff 自检（karpathy guideline）**

```bash
git diff main -- web/console.html | head -100
```

确认：
- 没有顺手"改进"的无关代码
- 没有引入新依赖
- 改动都对得上 spec 的某条决定

- [ ] **Step 7: Commit**

```bash
git add web/console.html RUNBOOK.md
git commit -m "ui: drop unused legacy classes and add manual verification checklist"
```

- [ ] **Step 8: 提示用户 push（不自动 push）**

告诉用户："实施全部完成、9 个 commit 都干净；如要同步到 GitHub 请说『push』"。

---

## 验收标准

完成全部任务时应当满足：

1. `web/console.html` 视觉为报刊野兽派（米/黑/灰 + 红绿克制 + 0 圆角 + serif + 等宽 + 1.5px 硬边）
2. 顶部三标签 DISPATCH / PIPELINE / ARCHIVE，PIPELINE 是默认且 localStorage 记忆
3. 工位卡上下叠；牛马1只有一个「规则」按钮
4. 配置/规则面板是居中模态，ESC + 蒙版 + × 三种关闭方式都生效
5. 后端代码、API、`runtime_config.json` 结构、依赖、构建链 完全没改
6. `pytest -q` 全绿
7. RUNBOOK 手动清单全部打勾
8. 9 个 commit，每个 commit message 简洁、专注于一项变动
