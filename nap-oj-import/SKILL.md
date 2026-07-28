---
name: nap-oj-import
version: 2.1.0
description: 从 OJ 平台搬运题目，生成标准化题目文件包；也可根据用户提供的题目仅生成测试数据
allowed-tools:
  - Read
  - Write
  - Edit
  - AskUserQuestion
  - WebFetch
  - Agent

metadata:
  slug: nap-oj-import
  trigger: OJ题目、搬题、算法题搬运、AtCoder、Codeforces、题目导入、测试点、生成数据、测试数据、难度分级、知识点标签
---

## Keywords

OJ题目、搬题、算法题搬运、AtCoder、Codeforces、测试点、测试数据、难度分级、知识点标签

## Summary

自OJ搬题，生标准化题包（题面+标程+数据）；或依用户所供，仅生测试数据（.in/.out）。

## Strategy

### 输出目录规则

⚠️ **所有题包必须输出到统一的子目录，禁止散落在根目录。**

- 默认输出目录：`{当前工作目录}/problems/`（如 `D:\problems\`）
- 用户指定目录时，以用户指定为准
- 工作目录 `work_{slug}` 和最终题包 `{slug}` 都在 `{OUTPUT_DIR}` 下

### 单题搬运

**Phase 1（串行）：获取题面**

1. 读 steps/00-detect-url.md → 辨类型
2. 初始化：`mkdir -p {OUTPUT_DIR}` + `cp -r question {OUTPUT_DIR}/work_{slug}`（详 01-init.md）
3. 取题面：按来源
   - URL：WebFetch 访问 → 解析
   - 文件：读 steps/10-from-file.md → 自本地文件取题面
   - 文本：读 steps/11-from-text.md → 自用户文本取题面

**Phase 2（并行）：初评 + 题面 + 边界分析**

以下三步**只依赖题面内容，彼此互不依赖，可并行执行**：

4. 读 steps/03-gesp.md → **初评**难度与标签（四维评分）
5. 读 steps/04-problem.md → 生题面（problem.md）
6. 读 steps/06-boundary.md → **边界分析**（产出风险目录 boundary.md）

Phase 2 全部完成后 → 汇聚到步骤 7

**Phase 3（串行）：配置 + 标程 + 数据 + 验证 + 打包**

7. 读 steps/05-config.md → 写配置（problem.json，difficulty 为初评值）
8. 读 steps/07-std.md → 实现标程 std.cpp + **边界验证** + **难度终评**（基于实际算法更新 difficulty + 重新筛选 boundary.md）
9. 读 steps/08-testdata.md → 生数据（⚠️ 只改 mkin.h，Hack 数据必须基于 boundary.md 中 ✅ 的风险；⚠️ 输出必须符合题面声明的约束）
10. 读 steps/8.5-validate.md → **独立对拍验证 + 输出约束检查**（写 validator.cpp 独立验证，用 check.py 对拍，失败数据自动重生成）
11. 清理工具文件（详 09-package.md）

### ⚠️ 比赛搬运（必先创题面汇总文件）

1. 读 steps/contest/01-list.md → 创题面汇总文件 `{contest_id}.md`
2. 读 steps/contest/02-problem.md → **逐题译之，追加写入汇总文件**
3. 读 steps/contest/03-move.md → **自文件读题面**，逐题生完整题包

### 批量并行搬运

用户提供多个题目（多个 URL / 多个文件 / 混合），一次性并行搬运。

**触发条件**：用户一次给出 2 个及以上题目信息。

**流程：**

1. 解析用户输入，拆分为 N 个独立题目（URL / 文件路径 / 文本）
2. 读 steps/batch-import.md → 获取子 Agent prompt 模板
3. 对每道题启动一个子 Agent，传入该题目信息 + prompt 模板
4. 各子 Agent 并行执行完整单题搬运流程（各自读 steps/ 文档）
5. 主 Agent 收集结果，汇总报告用户

**子 Agent 隔离**：每题独立工作目录 `work_{slug}`，互不干扰。

### 生成测试点

用户已有完整题面，仅需测试数据（.in/.out）。

**触发词**：用户言"生成测试点"、"出测试数据"、"想测试数据"、"写测试数据"等。

**流程：**

1. 读 steps/00-detect-url.md → 辨输入类型
2. 初始化：`cp -r question work_{slug}`（详 01-init.md）
3. 取题面信息：
   - URL：WebFetch 访问并解析
   - 文件：读 steps/10-from-file.md 取题面（仅内部参考，不生正式 problem.md）
   - 文本：读 steps/11-from-text.md 自文本取题面
4. 读 steps/12-testdata-only.md → **边界分析 + 实现标程 + 生测试数据 + 独立验证 + 交付**
5. **跳过**：题面格式化（04-problem.md）、难度定级（03-gesp.md）、配置写入（05-config.md）

## AVOID

- AVOID 不读步骤文档即执行
- AVOID 不按模板格式
- AVOID 测试数据只写样例：简单题至少 10 组，正常题 25 组
- AVOID 难度等级乱判：必用四维评分（知识点/复杂度/思维深度/洛谷参照），禁只看关键词定难度
- ⚠️ **AVOID 跳过难度终评：标程写完后必基于实际算法终评，初评仅供参考，以终评为准**
- ⚠️ **AVOID 终评后不更新 boundary.md：难度变化时必须重新筛选风险目录**
- AVOID 忘清理工作目录（`work_*`）
- AVOID PID 格式错误（用大写，如 ABC451A、B3921）
- ⚠️ **AVOID tag 只写难度等级：必含 1~3 个知识点标签（从 Tags 字典选），difficulty 字段单独存难度**
- ⚠️ **AVOID 自对话上下文记忆题面，必自文件读取**
- ⚠️ **AVOID 生成数据时修改 mkdata.cpp，只许修改 mkin.h**
- ⚠️ **AVOID 生成数据不遵守题面输出约束：大规模随机数据必须保证答案在题面声明范围内（如 $E \\le 2.1 \\times 10^9$），不可盲目使用输入最大值组合**
- ⚠️ **AVOID 跳过独立验证：测试数据生成后必须运行 check.py 对拍验证 + 约束检查，全部通过方可打包**
- ⚠️ **AVOID 只依赖 std.cpp 自证：必须用独立实现的 validator.cpp 重新对拍，std 自验等于没验**
- ⚠️ **AVOID Hack 数据凭感觉写：必须基于 boundary.md 中 ✅ 的风险条目设计，禁止使用通用模板**
- ⚠️ **AVOID 测试数据超出难度设计意图：boundary.md 中 ❌ 的风险禁止落地为测试点**
- ⚠️ **AVOID 跳过边界分析：写 std 前必须先做边界分析产出风险目录**
- ⚠️ **AVOID 写完 std 不验样例：所有样例输入逐一喂入，输出须与题面完全一致，全过方可进入数据生成**
- ⚠️ **AVOID 写完 std 不验边界：必须用 boundary.md 中 ✅ 的风险构造输入验证**
- ⚠️ **AVOID 修改样例：样例输入/输出必原样复制，禁增删改任何字符**
- ⚠️ **AVOID 删除图片链接：题面中 `![](url)`、`<img>` 标签等所有图片语法必原样保留**
- ⚠️ **AVOID 删除示意图：题面原有示意图、表格、公式必完整保留**
- ⚠️ **生成测试点时 AVOID 生成 problem.md、problem.json**
- ⚠️ **生成测试点时 AVOID 跳过 std.cpp：无标程则 .out 不出**
- ⚠️ **生成测试点时 AVOID 只写样例数据：简单题 10 组、正常题 25 组全覆盖（含 Hack）**
- ⚠️ **生成测试点时 AVOID 交付前不验证：必查 .in 格式、.out 与样例一致、文件成对存在，必运行 check.py 对拍 + 约束检查**
- ⚠️ **批量搬运时 AVOID 子 Agent 不读文档即执行：每步必引对应 steps/ 文档**
- ⚠️ **批量搬运时 AVOID 题目间共享工作目录：每题独立 `work_{slug}`**
- ⚠️ **AVOID 在根目录下直接创建题包目录：必用 `{OUTPUT_DIR}/` 统一收纳**
- ⚠️ **AVOID Phase 2 不并行：03-gesp / 04-problem / 06-boundary 三步必须并行启动，不可串行**

---

## 入口

读 steps/00-detect-url.md
