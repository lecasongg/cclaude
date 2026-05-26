# 牛马控制台重做 · 报刊野兽派 / 档案夹布局

**日期：** 2026-05-26
**范围：** `web/console.html` 视觉与布局重做（换皮 + 重排），功能不增不减，后端零改动
**实现路线：** 在现有单文件 Alpine + Tailwind CDN 基础上原地重写 HTML/CSS，新增 `activeTab` 状态做标签切换

---

## 1. 总体骨架

档案夹布局：左竖条 + 顶部报头 + 三标签 + 内容区。

```
┌────────────────────────────────────────────────────────────────────┐
│ ┃            [报头：粗黑标题 / 今日日期 / 岗位计数]             ┃ │
│ ┃ ──────────────────────────────────────────────────────────── ┃ │
│ N│                                                                ┃ │
│ ┃│ [DISPATCH]  [PIPELINE *]  [ARCHIVE]                            ┃ │
│ U│ ──────────────────────────────────────────────────────────── ┃ │
│ ┃│                                                                ┃ │
│ M│   <活跃标签的内容区(可滚)>                                     ┃ │
│ ┃│                                                                ┃ │
│ A│                                                                ┃ │
└────────────────────────────────────────────────────────────────────┘
   左 28–32px 窄条：垂直竖排 "NIUMA · WORKSHOP · N°01"，sticky
   顶部报头 + 标签：sticky；唯一滚动区域是内容区
```

- 单页 + Alpine 控制 `activeTab`，切换标签靠 `x-show`，不引入路由
- 首次进入默认 `activeTab = 'pipeline'`；切换写入 `localStorage['niuma.activeTab']`；下次 `init()` 读回
- **不做窄屏适配**（只在桌面用）

---

## 2. 视觉系统

| 元素 | 取值 |
|---|---|
| 底色 | `#f4f1ea`（米色纸张） |
| 主墨色 | `#111` |
| 副墨色 | `#3a3a3a`（正文灰） |
| 米灰 | `#7a7468`（idle / 占位） |
| 强调色 | `#b00020`（深红 · 仅错误、failed、重要标签） |
| 成功色 | `#1f6b3a`（墨绿 · succeeded、已配置） |
| 显示字 / 正文 | `Georgia, "Songti SC", "宋体", serif` |
| 等宽字 | `"Courier New", ui-monospace, monospace` |
| 边框 | 默认 `1.5px solid #111`；强调 `3px solid #111`；章节分隔 `3px double #111` |
| 圆角 | **0**（全局禁用） |
| 阴影 | **无** |
| 基线 | 8px |
| 正文行高 | 1.6 |

**组件取值：**

- `H1` 标题 — Georgia 900, 32–36px, letter-spacing -0.5px，下接 1.5px 黑横线
- 岗位卡 — 1.5px 黑边，纸色填充；卡角等宽小标如 `UNIT 01 · REVERSE` / `N°02`
- 状态徽章 — 矩形（非 pill），等宽字大写，例 `[ RUNNING ]` 反白填充黑底，`[ IDLE ]` 黑字白底
- 按钮 — 矩形 1.5px 黑边；hover 直接反相（黑底米字）；过渡 ≤80ms 或无
- 输入框 — 透明底 + 仅底边 1.5px 黑线；focus 时底线变 3px
- 章节分隔 — `border-top: 3px double #111`

**状态色映射：**

| 状态 | 样式 |
|---|---|
| running | 黑底 `#111` + 米字 `#f4f1ea`（反白），中性表达"正在做" |
| succeeded | 1.5px 墨绿边 + 墨绿字 `#1f6b3a` |
| failed | 1.5px 深红边 + 深红字 `#b00020` |
| pending | 1.5px 黑边 + 黑字 |
| idle | 米灰字 `#7a7468`，无边框 |

**反 AI 套路自检：**
- ❌ 紫渐变、圆角、Inter/Roboto、box-shadow、彩色 emoji
- ✅ 仅 serif + 等宽两族字体；色板仅米/黑/灰 + 红绿两个克制强调

---

## 3. 标签内部布局

### 3.1 `DISPATCH` — 派工入口

单列、上下两段（用单线分隔）：

1. **N°01 单工位派工** — 选工位 ▾ + textarea + `[ 发送任务 ]`
2. **N°02 链式派工** — niuma-1 prompt → 文件输入区（本机路径 + 上传 + 已载入列表 + 清空）→ niuma-2 instruction → `[ 启动链式派工 ]`

### 3.2 `PIPELINE` — 状态与运行面板（默认页）

按从上到下：

1. **4 张统计卡**（一排）：Server / Workers / API Keys / Auto Refresh
2. **两个工位卡上下叠**（不再左右并排）：
   - 卡内：编号 + UNIT 标签 + 显示名 + 状态徽章 + `[配置]` `[规则]` 两个按钮
   - 字段：Provider / Model · API Key 环境变量及配置状态 · Base URL · 任务材料(任务手册 / 转换规则)安装状态 · 当前任务 prompt
   - **「规则安装」「任务手册」两个按钮合并为单个「规则」按钮**（现有两个按钮指向同一个弹窗，是冗余）
3. **操作回执 / TIMELINE** — 列表式事件流，等宽字 type + 时间戳 + body

**Auto Refresh 按钮文案：** `[ AUTO · ON ]` / `[ AUTO · OFF ]`（等宽字大写）。

### 3.3 `ARCHIVE` — 历史与产物

左右两栏，比例约 1 : 1.4（产物区更宽）：

- **左：任务历史** — 顶部 `[▾全部工位] [▾全部状态]` 两个筛选；下方任务卡列表，可滚
- **右：产物阅读器** — meta 信息（worker · status · 是否有上游）+ task_id + prompt + 错误信息 + artifact_id 按钮组 + `<pre>` 产物正文；`[ 复制产物 ]` 在标题右

---

## 4. 模态弹窗

**配置 / 规则两个面板从侧栏内联改为居中模态：**

- 半透明纸色蒙版 `bg-[#f4f1ea]/80`
- 关闭方式三选一：ESC 键 / 点击蒙版 / 右上角 `[ × ]`
- 模态容器：1.5px 黑边矩形，纸底，宽度约 480–560px
- Alpine 新增显式 flag：`configModalOpen` / `documentModalOpen`

**规则模态内仍是两个独立上传区：**

- 任务手册（task_manual）
- 转换规则（conversion_rules）

---

## 5. 顶部 Alert

- 现状：indigo/red 渐变色卡
- 重做：1.5px 黑边矩形
  - 正常态：白底 + 黑字
  - 错误态：1.5px 深红边 + 深红字 `#b00020`
- 关闭按钮：右上等宽字 `[ × ]`

---

## 6. Alpine 数据模型差异

仅列**新增 / 变化**字段，其他保留：

```js
// 新增
activeTab: 'pipeline',           // 'dispatch' | 'pipeline' | 'archive'
configModalOpen: false,
documentModalOpen: false,

// init() 新增
const saved = localStorage.getItem('niuma.activeTab');
if (saved) this.activeTab = saved;

// setActiveTab(tab) 新增
this.activeTab = tab;
localStorage.setItem('niuma.activeTab', tab);
```

**没有变化的部分：**
- 所有 `requestJson` / fetch 调用
- 自动刷新计时器
- 任务过滤、artifact 加载、文件上传链路
- worker_server.py 后端、runtime_config.json 结构

---

## 7. 范围与非范围

**范围内（动）：**
- `web/console.html` 整文件重写（HTML 结构 + style 区 + Alpine state 新增）
- `RUNBOOK.md` 末尾追加"控制台手动验证清单"小节

**范围外（不动）：**
- `worker_server.py`、`core/**`、`tests/**`
- 现有 API 路径、payload、token 校验
- `runtime_config.json` 结构
- 静态资源加载方式（仍是 Tailwind CDN + Alpine CDN）
- 不引入 Vite / Tailwind CLI 等构建链
- 不做窄屏 / 移动端适配
- 不新增功能（搜索、暗色切换、快捷键面板、实时日志流等 一律不做）

---

## 8. 测试与验收

### 8.1 后端回归

不新增、不修改 pytest。完工后跑 `pytest -q` 作为兜底，确认没误伤。

### 8.2 前端手动验证清单（写入 RUNBOOK.md）

```
□ 默认进 PIPELINE 标签
□ 切到 DISPATCH，刷新页面后仍在 DISPATCH（localStorage 起效）
□ 4 张统计卡数据正确（Server online、Workers 2/2、Keys、AUTO 开关）
□ 工位卡上下叠展示；「规则」按钮存在且仅 1 个
□ 点「配置」→ 居中模态弹出，蒙版 / ESC / × 三种方式都能关
□ 点「规则」→ 居中模态弹出，任务手册和转换规则两个上传区都在
□ 单工位派工：选工位 + 填 prompt + 发送，成功并出现在 Timeline
□ 链式派工：填 prompt + 上传 1 个文件 + 启动，成功并能在 ARCHIVE 看到两条任务
□ ARCHIVE 左右两栏：选历史任务，右侧产物阅读器显示内容
□ 故意触发错误（空 prompt 发送 / 改坏 token），alert 显示深红边矩形
□ 视觉整体：米底 / 黑字 / serif / 0 圆角 / 无阴影 / 红绿克制
```

### 8.3 Karpathy guideline 验收

- 后端代码零改动
- 无新增依赖
- 无范围外的新功能
- 每行 CSS / HTML 都能追溯到"换皮 + 重排"

---

## 9. 决定速查表

| 项 | 决定 |
|---|---|
| 视觉方向 | 报刊野兽派 |
| 强调色 | 深红 `#b00020`（弃用 indigo） |
| 状态色 | running 黑底反白 / succeeded 墨绿 / failed 深红 / idle 米灰 |
| 布局骨架 | 档案夹：左竖条 + 顶报头 + 三标签 + 内容区 |
| 三标签分组 | DISPATCH(派工) / PIPELINE(状态+配置) / ARCHIVE(历史+产物) |
| 默认进入 | PIPELINE，localStorage 记忆 |
| 工位卡 | 上下叠 |
| 规则按钮 | 合并为 1 个「规则」（弹窗内仍 2 个上传区） |
| 配置 / 规则面板 | 居中模态（ESC + 点蒙版 + × 三种关闭） |
| 范围 | 只动 `web/console.html` 与 `RUNBOOK.md` |
| 实现 | Tailwind CDN + Alpine，不引入构建链 |
| 窄屏适配 | 不做 |
| 测试 | 现有 pytest 兜底 + 前端手动清单 |
