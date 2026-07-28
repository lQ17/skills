# Step 12: 仅生测试点

## 目标

用户已供题，**仅需测试数据（.in / .out）**，不要题面文件、不要 problem.json、不要打包。

## ⚠️ 核心原则

```
标程 + mkin.h = 测试数据（.in + .out）
缺标程 → .out 不出
缺 mkin.h → .in 不出
两样皆写 → 编译 → 运行 → testcases/ 到手
```

## 流程

### 1. 析题

自用户材取以下信息（**必遍查，缺一不可**），记至 `{WORK_DIR}/problem.md`（仅自参，不作交付）：

| 信息 | 说明 |
|------|------|
| 入格式 | 每行表何、量名及型、空格/换行分隔 |
| 出格式 | 出何、每行几数、精度求 |
| 数据范围 | N/值之上下限、极值 |
| 时/内存限 | 决数据规上限 |
| 算法类 | 决 Hack 数据向 |
| 难度预估 | 决 Hack 数据严苛程度 |

若用户所供不足以定上任一，**必问用户补**。

### 2. 边界分析 → 产出 `{WORK_DIR}/boundary.md`

按 `06-boundary.md` 的方法做边界分析：

1. **约束枚举**：从数据范围穷举所有边界值及组合
2. **错解分析**：针对本题分析可能错误解法
3. **产出风险目录**：列出所有风险，每条标注最低难度
4. **按难度筛选**：用预估难度筛选"当前题是否需测"

⚠️ 难度不确定时，默认按 SILVER 筛选。用户明确说了难度等级则按用户说的。

### 3. 写标程 `{WORK_DIR}/std.cpp`

标程乃生 .out 之独法，必保：

- 算法**正**（能过全部测试数据）
- 用 `std.cpp` 为文件名，置 `{WORK_DIR}/` 目录
- OI 风格：简变量名、全局变量、`ios::sync_with_stdio(false)`
- 时复杂度对标题限（勿写出比正解更慢版）
- 注：Hack 数据乃为**选手码**掘坑，标程必能正跑过诸 Hack
- **标程本身必须正确处理所有风险**（包括不测的风险）——标程是参考答案

#### 验证标程

1. **样例验证**：所有样例输入逐一喂入，输出须与题面完全一致
2. **边界验证**：用 boundary.md 中 ✅ 的风险构造输入验证
3. **可选对拍**：SILVER 及以上难度，写暴力程序对拍

样例未全过 → 修 std → 重验。全过方可继续。

### 4. 设计测试数据

编 `{WORK_DIR}/mkin.h` 之 `test()` 函。正常题 25 组，简单题 10 组。

⚠️ **Hack 数据必须基于 boundary.md 中 ✅ 的风险条目设计，禁止凭感觉写通用 Hack。**
⚠️ **boundary.md 中 ❌ 的风险禁止出现在测试数据中（会超出题目难度设计意图）。**
⚠️ **输出必须符合题面声明的约束**：大规模数据时缩小随机值范围，确保答案在题面声明范围内。

**分组方案（5 子任，总 100）：**

| Subtask | 用例编号 | 类 | 分值 | 数据来源 |
|---------|---------|------|------|---------|
| 0 | 1-2 | 样例 | 10 | 题面 |
| 1 | 3-8 | 小规模 + 特性 | 20 | 随机 + boundary.md ✅ |
| 2 | 9-11 | Hack 数据 | 15 | boundary.md ✅ 错解风险 |
| 3 | 12-20 | 中大规模 | 30 | 随机 + 边界极值 |
| 4 | 21-25 | 随机复测 | 25 | 混合随机 |

**⚠️ 改 `test()` 分组时同更：**
1. `mkin.h` 顶 `SUBTASKS[]` 数组
2. 总分持 100

### 简单题方案：10 组

题目过于简单（签到题、纯模拟、无复杂边界）时，10 组即可：

| 用例编号 | 类型 | 说明 | 分值 | 数据来源 |
|---------|------|------|------|---------|
| 1-2 | 样例 | 直接复制题面 | 20 | 题面 |
| 3-4 | 边界 | 来自 boundary.md ✅ | 20 | boundary.md |
| 5-6 | 特殊性质 | 来自 boundary.md ✅ | 20 | boundary.md |
| 7-8 | Hack | 来自 boundary.md ✅ 错解风险 | 20 | boundary.md |
| 9-10 | 中大规模 | N 接近题目上限 | 20 | 随机 |

```cpp
void test(int case_num, ofstream& fout) {
    if (case_num == 1) {
        // 样例1：从题面复制
    }
    else if (case_num == 2) {
        // 样例2
    }
    else if (case_num == 3) {
        // 边界：来自 boundary.md 风险 #X
    }
    else if (case_num == 4) {
        // 边界：来自 boundary.md 风险 #Y
    }
    else if (case_num == 5) {
        // 特殊性质：来自 boundary.md 风险 #Z
    }
    else if (case_num == 6) {
        // 特殊性质：来自 boundary.md 风险 #W
    }
    else if (case_num == 7) {
        // Hack：来自 boundary.md 风险 #V（针对 [错法描述]）
    }
    else if (case_num == 8) {
        // Hack：来自 boundary.md 风险 #U（针对 [错法描述]）
    }
    else if (case_num == 9) {
        // 中规模：N 接近上限
    }
    else {
        // 大规模：N = 上限值
    }
}
```

#### 4a. 样例数据（case 1-2）

径复用户供样例入/出。用户未供样例时，自构**最简可验数据**。

```cpp
if (case_num == 1) {
    // 样例1：自用户供题面复，逐字一致
    fout << "5 3" << endl;
    fout << "1 2 3 4 5" << endl;
}
else if (case_num == 2) {
    // 样例2
}
```

#### 4b. 小规模随机（case 3-5）

N 取题范围**最小规模**（如 1~10），验基本功正。

```cpp
else if (case_num >= 3 && case_num <= 5) {
    int N = rand() % 5 + 1;
    int M = rand() % 5 + 1;
    fout << N << " " << M << endl;
    // 据题异生随机数据
}
```

#### 4c. 特性质数据（case 6-8）

**必须引用 boundary.md 中 ✅ 的风险条目**，禁止使用通用模板。

| 性质 | 说明 | 最低难度 | 当前题是否设计 |
|------|------|---------|-------------|
| 单调性 | 入有序（递增/递减） | BRONZE | 看 boundary.md |
| 全同 | 诸值等 | BRONZE | 看 boundary.md |
| 极值集 | 大量极值（如全 0/1） | BRONZE | 看 boundary.md |
| 素数密 | 大量素数 | SILVER | 看 boundary.md |
| 特定图构 | 链/菊/全图 | SILVER | 看 boundary.md |

每个 ✅ 的特性风险对应一用例。

```cpp
else if (case_num == 6) {
    // 特性1：来自 boundary.md 风险 #X — 单调递增
    int N = 100;
    fout << N << endl;
    for (int i = 1; i <= N; i++) fout << i << " \n"[i==N];
}
else if (case_num == 7) {
    // 特性2：来自 boundary.md 风险 #Y — 诸值同
    int N = 1000;
    fout << N << endl;
    for (int i = 1; i <= N; i++) fout << 5 << " \n"[i==N];
}
else if (case_num == 8) {
    // 特性3：来自 boundary.md 风险 #Z
}
```

#### 4d. Hack 数据（case 9-11）

**必须引用 boundary.md 中 ✅ 的错解风险，禁止使用通用 Hack 模板。**

| 常见错 | 最低难度 | 当前题是否测 |
|---------|---------|------------|
| int 溢出 | SILVER | 看 boundary.md |
| 边界漏判 | BRONZE | 看 boundary.md |
| 精度误 | SILVER | 看 boundary.md |
| 超时炸 | SILVER | 看 boundary.md |
| 错贪心 | GOLD | 看 boundary.md |
| 模数阱 | GOLD | 看 boundary.md |

```cpp
else if (case_num == 9) {
    // Hack 1: 来自 boundary.md 风险 #A — [具体错法描述]
    // 构造触发该错法的特定数据
}
else if (case_num == 10) {
    // Hack 2: 来自 boundary.md 风险 #B — [具体错法描述]
}
else if (case_num == 11) {
    // Hack 3: 来自 boundary.md 风险 #C — [具体错法描述]
}
```

#### 4e. 中大规数据（case 12-20）

| 用例 | 规模 | 的 |
|------|------|------|
| 12-15 | N = 100 ~ 10000 | 中规，验效 |
| 16-18 | N 近上限 80% | 大压测 |
| 19-20 | N = 上限值 | 极压测 |

```cpp
else if (case_num >= 12 && case_num <= 15) {
    int N = rand() % 1000 + 100;
    // 随机数据
}
else if (case_num >= 16 && case_num <= 20) {
    int N = 200000;  // 或题上限
    // 近极数据
}
```

#### 4f. 随机复测（case 21-25）

诸类数混搭，覆不复景：

```cpp
else {
    int N = rand() % 100000 + 1;
    // 自由随机
}
```

### 5. 编译运行

```bash
cd {WORK_DIR}
g++ std.cpp -o std -std=c++17    # 编译标程（为 mkdata 所调）
g++ mkdata.cpp -o mkdata -std=c++17
./mkdata
```

预期出：
```
编译标准程序成功
开始生成输入数据...
生成【01.in】数据成功
...
输入数据生成完成
开始生成输出数据...
处理测试用例 【01】... 完成
...
输出数据生成完成
```

### 6. 验证

⚠️ **必做独立对拍验证 + 输出约束检查**，仅靠 std.cpp 自验无效。

#### 6a. 提取输出约束

从题面读取输出约束，写入 `{WORK_DIR}/constraints.json`（格式见 `8.5-validate.md`）。

#### 6b. 运行对拍验证

```bash
cd {WORK_DIR}
python check.py --validator validator.cpp --constraints constraints.json
```

若用户提供了标程，优先用用户标程作为 validator；否则按 `8.5-validate.md` 第二步独立实现。

#### 6c. 基础验证

必验下诸项：

- [ ] {WORK_DIR}/testcases/ 目录下 .in 与 .out 成对存
- [ ] 前 2 组数与样例题完全一致（用 `diff` 或 `read_file` 较）
- [ ] 每组 .in 格合同题入格式述
- [ ] Hack 数据确实来自 boundary.md ✅ 风险，未混入 ❌ 风险
- [ ] check.py 全部通过（对拍 + 约束）

失败则按 `8.5-validate.md` 第四步处理，重新生成并重验。最多重试 3 轮。

### 7. 交付

告用户测数已生：
- `{WORK_DIR}/testcases/` 目录：N 组 `.in` + N 组 `.out`（纯文件对，无 config.yaml）

## 与常流之别

| 项 | 常搬题 | 仅生测试点 |
|------|---------|-------------|
| 题面 problem.md | 生 | **跳**（或仅内参） |
| problem.json | 写 | **跳** |
| boundary.md | 生 | **生**（决定 Hack 数据方向） |
| std.cpp | 写 | **写**（生 .out 必需） |
| mkin.h | 编 | **编**（基于 boundary.md 筛选结果） |
| mkdata + 运 | 行 | **行** |
| 交付 | 打全 {WORK_DIR}/ zip | **只交 testcases/ 目录** |
