---
name: luogu-scrape
description: |
  从洛谷批量抓取题目，生成标准化 markdown 文件。支持单题、多题、整个题单/比赛的抓取，自动删除"题目背景"，保留 LaTeX 公式和代码块。使用 Kimi WebBridge 控制用户浏览器，利用洛谷页面的"复制 Markdown"按钮获取标准格式内容。
allowed-tools:
  - Bash
  - Write
  - Read
  - Agent
  - AskUserQuestion

metadata:
  slug: luogu-scrape
  trigger: 洛谷、luogu、抓题、题目抓取、导出题目、GESP、CSP、比赛题目
---

## Keywords

洛谷、luogu、抓题、题目导出、GESP、CSP、比赛题目、markdown、批量抓取

## Summary

从洛谷（luogu.com.cn）批量抓取题目，输出标准化 markdown 文件。利用页面"复制 Markdown"按钮获取完美格式（LaTeX、代码块、表格），智能判断"题目背景"段是否保留（仅当含无关跳转链接时删除）。

## 前置依赖

- **Kimi WebBridge**：必须已安装且 `kimi-webbridge status` 显示 `running: true` + `extension_connected: true`
- 若连接端口 10086 失败（curl exit code 7），执行以下命令启动 daemon：

**Git Bash / WSL：**
```bash
~/.kimi-webbridge/bin/kimi-webbridge start
```

**PowerShell：**
```powershell
& "$env:USERPROFILE\.kimi-webbridge\bin\kimi-webbridge.exe" start
```

- 浏览器需已登录洛谷（未登录也能抓，但部分题目可能受限）

## 核心流程

### 单题抓取

```
用户给出题目 slug/URL → 解析 slug → 导航 → 获取快照提取时间/空间限制 → 点击"复制 Markdown" → 读剪贴板 → 判断题目背景是否保留 → 提取一级标题作为文件名 → 组装内容并保存
```

详细步骤：

1. **导航到题目页**
```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"navigate","args":{"url":"https://www.luogu.com.cn/problem/{SLUG}","newTab":true},"session":"luogu-scrape"}'
```

2. **获取页面快照，提取时间/空间限制 + 定位"复制 Markdown"按钮**
```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"snapshot","args":{},"session":"luogu-scrape"}'
```

**提取时间/空间限制 + 难度**：在 snapshot 的 tree 中，banner 区域有如下结构：

- **时间/内存限制**：查找 `name` 为 `"时间限制"` 的 `StaticText` 节点，其相邻兄弟 `StaticText` 节点的 `name` 即为时间值（如 `"1.00s"`）；`"内存限制"` 同理，相邻兄弟的 `name` 即内存值（如 `"512.00MB"`）。两者位于同一个 4 节点的列表中：
```
提交 / {提交数}
通过 / {通过数}
时间限制 / {时间值}     ← 记录此值，如 "1.00s"
内存限制 / {内存值}     ← 记录此值，如 "512.00MB"
```

- **难度**：查找 `name` 为 `"难度"` 的 `StaticText` 节点，其相邻兄弟 `link` 节点的 `name` 即为难度值（如 `"省选/NOI−"`、`"提高+/省选-"`、`"普及/提高-"`、`"入门"` 等）。注意难度值的节点角色是 `link` 而非 `StaticText`。

**定位"复制 Markdown"按钮**：查找 `name` 为 `" 复制 Markdown"` 的元素，记录其 `ref`（如 `@e52`）。

3. **点击按钮**
```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"click","args":{"selector":"@eXX"},"session":"luogu-scrape"}'
```

4. **读取剪贴板**
```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"evaluate","args":{"code":"navigator.clipboard.readText()"},"session":"luogu-scrape"}'
```

5. **处理内容并保存**
   - 判断 `## 题目背景` 段是否保留：提取 `## 题目背景` 到下一个 `## ` 之间的内容，检查其中是否包含与题目无关的跳转链接（如考试选择题、判断题的链接，通常带有 `luogu.com.cn/contest/` 或 `luogu.com.cn/problem?type=choice` 等模式）。若包含此类无关链接，则删除整个题目背景段；否则保留。
   - 从内容中提取一级标题（`# ` 开头的行），用作文件名
   - 在一级标题后、`## 题目描述` 前，插入限制行：`时间限制: {值} | 内存限制: {值} | 难度: {值}`
   - 用 Write 工具保存到 `{OUTPUT_DIR}/{SLUG}/{一级标题}.md`

6. **关闭标签页**
```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"close_tab","args":{},"session":"luogu-scrape"}'
```

### 批量并行抓取

**触发条件**：用户一次给出 2 个及以上题目。

**流程**：

1. 解析用户输入，提取所有 slug（支持 URL 和纯 slug 格式）
2. 将题目分成 N 组（每组 ≤ 10 题，建议 3 个 Agent 并行）
3. 每个 Agent 使用独立 session（`luogu-batch1`、`luogu-batch2` ...）
4. 各 Agent 并行执行单题抓取流程
5. 主 Agent 收集结果，汇总报告

**Agent prompt 模板**：

```
你是一个题目抓取 agent。使用 Kimi WebBridge 从洛谷抓取题目并保存为 markdown 文件。

## 你的任务
抓取以下 {N} 道题，保存到 `{OUTPUT_DIR}\{slug}\{一级标题}.md`：
{题目列表}

## 每道题的操作步骤
1. curl navigate 打开 https://www.luogu.com.cn/problem/{SLUG}
2. curl snapshot 获取页面快照：
   - 在 banner 区域查找 `name` 为 `"时间限制"` 的 StaticText，其相邻兄弟 StaticText 的 name 即时间值
   - 查找 `name` 为 `"内存限制"` 的 StaticText，其相邻兄弟 StaticText 的 name 即内存值
   - 查找 `name` 为 `"难度"` 的 StaticText，其相邻兄弟 `link` 节点的 name 即难度值（如 `"省选/NOI−"`）
   - 找到"复制 Markdown"按钮的 ref
3. curl click 点击"复制 Markdown"按钮
4. curl evaluate 读取 navigator.clipboard.readText()
5. Write 保存文件：
   - 判断题目背景是否含无关链接决定是否删除
   - 文件名用一级标题
   - 在一级标题后插入 `时间限制: {值} | 内存限制: {值}`
6. curl close_tab 关闭标签页

## 注意事项
- session 固定用 `luogu-batch{N}`
- 每道题完成后立即保存
- 失败则记录错误继续下一题
- 题目背景段仅在包含无关跳转链接（考试选择题/判断题链接）时删除，否则保留
```

### 题单/比赛批量抓取

用户提供洛谷题单或比赛 URL：

1. 用 WebFetch 访问题单/比赛页面，提取所有题目 slug
2. 按批量并行流程处理

## 输出目录

- 默认：`{当前工作目录}/problems/{SLUG}/`
- 每个题目一个子目录，文件名为一级标题
- 用户指定时以用户为准
- 自动创建目录（`mkdir -p`）

## 输出格式

每个文件命名为 `{一级标题}.md`，包含：

```markdown
# {SLUG} {题目标题}

时间限制: {值} | 内存限制: {值} | 难度: {值}

## 题目描述
{...}

## 输入格式
{...}

## 输出格式
{...}

## 输入输出样例 #1
### 输入 #1
```
{...}
```
### 输出 #1
```
{...}
```

## 说明/提示（如有）
{...}
```

## 剪贴板读取失败的兜底

若 `navigator.clipboard.readText()` 报错 `Document is not focused`，改用注入拦截器：

```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"evaluate","args":{"code":"(() => { const orig = navigator.clipboard.writeText.bind(navigator.clipboard); navigator.clipboard.writeText = async (t) => { window.__clipboardCapture = t; return orig(t); }; return \\\"interceptor installed\\\"; })()"},"session":"luogu-batchN"}'
```

然后点击"复制 Markdown"后读取 `window.__clipboardCapture`：

```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"evaluate","args":{"code":"window.__clipboardCapture"},"session":"luogu-batchN"}'
```

## AVOID

- ⚠️ **AVOID 手动爬 DOM 解析题目**：洛谷的"复制 Markdown"按钮已输出标准格式，手动解析易出错且费时
- ⚠️ **AVOID 所有 Agent 共用同一 session**：会导致标签页混乱，每个 Agent 必须用独立 session
- ⚠️ **AVOID 不关闭标签页**：批量抓取会堆积大量标签，每题完成后必须 close_tab
- ⚠️ **AVOID 误删有价值的题目背景**：仅当题目背景含无关跳转链接（考试选择题/判断题链接）时才删除，有意义的题目背景必须保留
- ⚠️ **AVOID 输出目录散落**：所有文件必须放入统一目录，不得散落在根目录
