# 批量并行搬运

## 目标

用户一次提供多个题目，并行启动子 Agent 搬运，各自独立完成。

## 输入解析

从用户消息中提取题目列表。常见格式：

```
https://atcoder.jp/contests/abc300/tasks/abc300_a
https://atcoder.jp/contests/abc300/tasks/abc300_b
https://atcoder.jp/contests/abc300/tasks/abc300_c
```

或逗号分隔、逐条列出、混合文件路径等。拆分为 N 个独立条目。

## prompt 模板

每个子 Agent 使用以下 prompt（`{PROBLEM_INFO}` 替换为具体题目信息）：

```
你是题目搬运子 agent。请独立完成以下题目的完整搬运。

题目信息：{PROBLEM_INFO}
输出目录：{OUTPUT_DIR}（默认为当前工作目录下的 problems/ 子目录）

⚠️ 所有文件操作必须在 {OUTPUT_DIR} 下进行，禁止在根目录创建任何目录或文件。

按以下阶段执行，每步读对应文档：

**Phase 1（串行）：获取题面**
1. 读 steps/00-detect-url.md → 辨类型（URL / 文件 / 文本）
2. 读 steps/01-init.md → 初始化工作目录 mkdir -p {OUTPUT_DIR} && cp -r question {OUTPUT_DIR}/work_{slug}
3. 取题面：
   - URL：WebFetch 访问 → 解析
   - 文件：读 steps/10-from-file.md → 自本地文件取题面
   - 文本：读 steps/11-from-text.md → 自用户文本取题面

**Phase 2（并行）：初评 + 题面 + 边界分析**
以下三步只依赖题面内容，必须并行启动：
4. 读 steps/03-gesp.md → **初评**难度与标签（四维评分）
5. 读 steps/04-problem.md → 生题面（problem.md）
6. 读 steps/06-boundary.md → **边界分析**（产出风险目录 boundary.md）
Phase 2 全部完成后方可继续。

**Phase 3（串行）：配置 + 标程 + 数据 + 验证 + 打包**
7. 读 steps/05-config.md → 写配置（problem.json，difficulty 为初评值）
8. 读 steps/07-std.md → 实现标程 std.cpp + 边界验证 + **难度终评**（终评变化时更新 boundary.md）
9. 验标程：所有样例输入逐一喂入 std，输出须与题面完全一致，全过方可继续
10. 读 steps/08-testdata.md → 生数据（⚠️ 只改 mkin.h，Hack 数据必须基于 boundary.md 中 ✅ 的风险；⚠️ 输出必须符合题面声明的约束）
11. 读 steps/8.5-validate.md → **独立对拍验证 + 输出约束检查**（写 validator.cpp 独立验证，用 check.py 对拍，失败数据自动重生成，最多重试 3 轮）
12. 读 steps/09-package.md → 清理工具文件

完成后返回：
- 状态：成功 / 失败
- slug：题目标识
- 目录：work_{slug} 路径
- 失败原因（如有）
```

## 并行调度

### ⚠️ 并发上限：每批最多 2-3 个子 Agent

实测 14 个并行会触发 API 429 限流，导致大量失败。**每批启动 2-3 个子 Agent，等完成后再启动下一批。**

```
# ✅ 正：分批执行（每批 2-3 个）
# 第 1 批
Agent(prompt=problem_1, description="搬运题目 1")
Agent(prompt=problem_2, description="搬运题目 2")
# ← 等待完成 →
# 第 2 批
Agent(prompt=problem_3, description="搬运题目 3")
Agent(prompt=problem_4, description="搬运题目 4")
# ← 等待完成 →
# ... 依此类推

# ❌ 误：全部同时启动（触发 429）
Agent(prompt=problem_1, ...)
Agent(prompt=problem_2, ...)
...
Agent(prompt=problem_14, ...)  # 炸了
```

### 调度节奏

| 总题数 | 每批 | 批次 |
|--------|------|------|
| 1-3 | 全部 | 1 批 |
| 4-6 | 2-3 个 | 2 批 |
| 7-10 | 2-3 个 | 3-4 批 |
| 10+ | 2-3 个 | 分批至完成 |

## 结果汇总

每批完成后收集子 Agent 返回，向用户报告：

```
批量搬运完成：
✅ ABC300A → work_ABC300A/
✅ ABC300B → work_ABC300B/
❌ ABC300C → 失败：xxx
```

## AVOID

- 禁子 Agent 间共享状态或工作目录
- 禁不读步骤文档即执行
- 每题独立 `work_{slug}`，互不干扰
- ⚠️ **禁一次启动超过 3 个子 Agent（触发 429 限流），必分批执行**
