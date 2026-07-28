# Step 1: 环境初始化

## 目标

自模板目录复文件至工作目录。

## 工作目录命名

**最终格式：** `{slug}`（如 `P1057`、`ABC453A`、`B3921`）。slug 必用大写。

| 阶段 | 目录名 | 说明 |
|------|--------|------|
| 初始化时 | `work` 或 `work_{slug}` | slug 已知则径用，未知暂用 `work` |
| 得 slug 后（step 2） | `work_{slug}` | 自 URL 取 slug 后更名 |
| 最终交付 | `{slug}` | 去掉 `work_` 前缀 |

> **工作目录变量**：后诸步骤中，以 `{WORK_DIR}` 指当前工作目录名。
> AI 当于上下文中记 `{WORK_DIR}` 之值，所有文件操作皆基于此目录。

## 输出目录

⚠️ **禁止在根目录下直接创建工作目录。** 所有工作目录和题包必须放在统一的输出目录下。

- 默认：`{当前工作目录}/problems/`（如 `D:\problems\`）
- 用户指定时以用户为准
- 变量 `{OUTPUT_DIR}` 指此目录

## 命令

### 其一：slug 已知（自 URL 或上下文可定）

```bash
mkdir -p {OUTPUT_DIR}
rm -rf {OUTPUT_DIR}/work_{slug} 2>/dev/null
cp -r question {OUTPUT_DIR}/work_{slug}
# {WORK_DIR} = {OUTPUT_DIR}/work_{slug}
```

### 其二：slug 未知（首初始化）

```bash
mkdir -p {OUTPUT_DIR}
rm -rf {OUTPUT_DIR}/work 2>/dev/null
cp -r question {OUTPUT_DIR}/work
# {WORK_DIR} = {OUTPUT_DIR}/work（后得信息后更名）
```

## 模板位置

1. `SKILL.md 所在目录/question/`
2. `当前工作目录/question/`

## 模板文件

| 文件 | 用途 |
|------|------|
| `std.cpp` | 标程模板 |
| `mkdata.cpp` | 数据生成器模板 |
| `mkin.h` | 测试数据逻辑模板 |
| `problem.json` | 配置文件模板 |
| `problem.md` | 题面模板 |
| `check.py` | 对拍验证脚本（运行 std vs validator） |
| `constraints.json` | 输出约束配置模板 |

## 后续路径

后诸步骤引文件时用 `{WORK_DIR}/xxx` 而非 `work/xxx`。
AI 当记 `{WORK_DIR}` 之值，下步一致。

## 下一步

成 → `02-get-info.md`

败 → 查模板目录存否
