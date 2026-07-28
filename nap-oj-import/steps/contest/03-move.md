# Contest Step 3: 逐题全搬

## 目标

逐题生完整题包（题面、标程、测数、配）。

## 最高铁律：必自文件读题面

⚠️ 每搬一题前，必以 grep + read_file 自题面汇总文件读该题信息！

**禁**：
- ❌ 自对话上下文记取题面
- ❌ 自前译内容忆
- ❌ 伪记题内容径写

**必**：
- ✅ 用 `grep` 于题面文件中定位当前题
- ✅ 用 `read_file` 读该题全内
- ✅ 确读成后方始搬

## 步骤（对每题）

### Step 3-1 读题面

```bash
grep -n "## A -" abc453.md  # 定位题
read_file abc453.md         # 读内容
```

### Step 3-2 环境初始化

工作目录名：`work_{slug}`
PID 可自题明确（如 `abc453` 赛中 A 题 → `ABC453A`）。slug 必大写。

```bash
rm -rf work_{slug}
cp -r question work_{slug}
# {WORK_DIR} = work_{slug}
```

### Step 3-3 生题面

据读得信息生。生后更名目录加标题：

```bash
mv {WORK_DIR} {slug}
# {WORK_DIR} = {slug}
```

写入 `{WORK_DIR}/problem.md`。

### Step 3-4 写配

```json
{
  "slug": "ABC453A",
  "title": "中(英)",
  "difficulty": "silver",
  "score": 0,
  "timeLimit": 1000,
  "memoryLimit": 128,
  "tags": [
    "知识点标签1",
    "知识点标签2"
  ],
  "isPublic": true
}
```

⚠️ **tags 含 1~3 个知识点标签（从 Tags 字典选），difficulty 单独存难度等级**

写入 `{WORK_DIR}/problem.json`。

### Step 3-5 边界分析

按 `06-boundary.md` 方法，做约束枚举 + 错解分析，产出 `{WORK_DIR}/boundary.md`（风险目录）。

用汇总文件中已标注的难度作为初评难度筛选"当前题是否需测"。

### Step 3-6 实现标程

据题面编解法，写入 `{WORK_DIR}/std.cpp`。

### ⚠️ Step 3-7 验标程（铁律：生数前必行）

写完 std.cpp **必即**用全样例验 + 选定边界验，不跳：

```bash
cd {WORK_DIR}
g++ std.cpp -o std -std=c++17

# 逐样例入验出，一一对照题面
echo "【样例输入1】" | ./std
# 核出与题面否

echo "【样例输入2】" | ./std
# 核出与题面否
# ... 诸样例逐一验

# 边界验证：用 boundary.md 中 ✅ 的风险构造输入验证
```

**禁**：样例未全过便写 mkin.h / 生数
**必**：诸样例全过 + 边界验证通过，方入下步

### Step 3-8 难度终评

基于标程实际算法终评难度。若终评与初评不同，更新 problem.json + 重新筛选 boundary.md。

### Step 3-9 编测试数据

改 `{WORK_DIR}/mkin.h` 之 `test()` 函。

⚠️ **Hack 数据必须基于 boundary.md 中 ✅ 的风险条目设计，禁止凭感觉写通用 Hack。**

### Step 3-10 生测试数据

```bash
cd {WORK_DIR}
g++ -o mkdata mkdata.cpp -std=c++17
./mkdata
```

### Step 3-11 清理

```bash
rm -f {WORK_DIR}/std {WORK_DIR}/mkdata {WORK_DIR}/*.exe
rm -f {WORK_DIR}/std.cpp {WORK_DIR}/mkdata.cpp {WORK_DIR}/mkin.h {WORK_DIR}/boundary.md
```

## 成后

清思，备下题！

- ❌ 禁留上题上下文
- ✅ 每题独读题面信息

## 完成

N 个题包已生，务成！
