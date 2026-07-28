# Step 5: 写配置

## 目标

写入 `{WORK_DIR}/problem.json`。

## pid 命名

```
用户指定 > 比赛自命名 > null
```

### 比赛自命名

格式：`{比赛简称}{场次}{题号}`

| 来源 | 例 |
|------|------|
| AtCoder ABC | `ABC453A` |
| AtCoder ARC | `ARC123A` |
| Codeforces | `CF789A` |
| LeetCode | `LC1234` |
| Luogu | `LGP1001` |

### 无比赛信息

单题搬运且无定来源：`slug: "P0000"`

## 配置格式

```json
{
  "slug": "P1012",
  "title": "[NOIP 1998 提高组] 拼数",
  "difficulty": "SILVER",
  "score": 35,
  "timeLimit": 1000,
  "memoryLimit": 128,
  "tags": [
    "排序算法",
    "贪心"
  ],
  "isPublic": true
}
```

## 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| slug | string | 题目 ID（如 `P1012`、`ABC453A`），必大写 |
| title | string | 题目标题，用原标题格式 |
| difficulty | string | 难度等级（大写），**此处为初评值**，step 6 标程写完后会终评并更新 |
| score | int | 分值，依据难度自动推荐，见下方分值表 |
| timeLimit | int | 时限（ms），如 1000 |
| memoryLimit | int | 内存限（MB），如 128 |
| tags | string[] | 1~4 个知识点标签，从 03-gesp.md Tags 字典中选 |
| isPublic | bool | 是否公开，默认 true |

⚠️ **difficulty 和 score 为初评值**：step 3 基于题面推测，step 7 标程写完后会基于实际算法终评并更新。以终评为准。

## 解析规则

从题面第一行提取限制（格式通常为 `时间限制: X.XXs | 内存限制: XXX.XXMB`）：

- `时间限制: X.XXs` → `timeLimit` = round(X.XX × 1000) ms
  - 例：`1.00s` → `1000`，`2.50s` → `2500`，`0.50s` → `500`
- `内存限制: XXX.XXMB` → `memoryLimit` = round(XXX.XX) MB
  - 例：`128.00MB` → `128`，`256.00MB` → `256`，`512.50MB` → `513`

## score 分值推荐

根据 difficulty 自动推荐默认分值，可在此基础上微调：

| 难度 | 默认分数 | 可调范围 |
|------|----------|----------|
| IRON | 10 | 5 ~ 19 |
| BRONZE | 20 | 10 ~ 34 |
| SILVER | 35 | 20 ~ 54 |
| GOLD | 55 | 35 ~ 79 |
| PLATINUM | 80 | 55 ~ 109 |
| DIAMOND | 110 | 80 ~ 149 |
| MASTER | 150 | 110 ~ 199 |
| CHAMPION | 200 | 150 ~ 269 |
| LEGENDARY | 270 | 200+ |

### 调分规则

1. **默认取表中默认分数**，无需特殊理由不调整
2. **同难度内可微调**：觉得偏简单可适当降分，偏难可适当加分
3. **严格不越界**：调整后分数必须严格小于下一难度的默认分数（如 GOLD 题最高 79，不可触及 PLATINUM 的 80）
4. **调分需有依据**：根据题面复杂度、代码量、思维深度综合判断，不可随意

## 注意

1. slug 按规而判，非无脑填 `P0000`
2. title 必用 `中文(英文)` 格式
3. **tags 必含 1~3 个知识点标签**，禁空数组敷衍
4. difficulty 必从九级中精确选择

## 下一步

成 → `07-std.md`
