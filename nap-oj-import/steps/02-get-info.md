# Step 2: 获取题目信息

## 目标

根据输入来源获取题目信息（slug、标题、题面内容）。

## 来源类型

| 类型 | 处理 |
|------|------|
| URL | WebFetch 访问 → 解析 |
| 题号 | 直接匹配 slug 格式 |
| 文件 | 解析文件提取题目信息 |
| 文本 | 用户直接粘贴题面 |

## URL 获取

用 WebFetch 工具访问 URL，提取页面中的题目信息：

```
WebFetch(url, "提取题目标题、描述、输入格式、输出格式、样例、数据范围")
```

**WebFetch 失败时**（需登录、反爬等）：请用户手动复制题面内容粘贴给你。

## slug 提取

| 平台 | URL 格式 | slug 规则 |
|------|---------|---------|
| AtCoder | `/contests/abc451/tasks/abc451_a` | `ABC451A` |
| Codeforces | `/contest/71/problem/A` | `CF71A` |
| LeetCode | `/problems/two-sum` | `LC1` |
| Luogu | `/problem/P1001` | `P1001` |
| 自定义 OJ | 依实际 URL | 依实际规则 |

无法提取时 slug 填 `null`。

## 重命名工作目录（关键！）

提取到 slug 后，**立即重命名工作目录**：

### 如果当前目录是 `work`（即初始化时 slug 未知）：

```bash
mv work work_{slug}
# {WORK_DIR} = work_{slug}
```

### 如果当前目录已经是 `work_{slug}`：

无需操作，`{WORK_DIR}` 保持不变。

### 如果 slug 为 null（无法提取）：

保持 `{WORK_DIR}` 不变，后续步骤确定名称后再处理。

## 下一步

成功 → Phase 2 并行启动：
- `03-gesp.md`（初评难度）
- `04-problem.md`（生题面）
- `06-boundary.md`（边界分析）

三者只依赖题面内容，可并行执行。全部完成后汇聚到 `05-config.md`。

失败 → 询问用户其他来源
