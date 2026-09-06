---
name: sb3-strip
description: Use when creating a blank Scratch .sb3 project from an existing one — strips all block scripts while keeping sprites, costumes, backdrops, sounds, variables, lists and broadcasts
---

# 生成空白 Scratch 工程

## Overview

输入一个完整的 `.sb3`，输出一个**删除全部积木块、保留资产信息**的空白工程，可直接用 Scratch 3 打开。

`.sb3` 就是 zip 包，核心是 `project.json`。脚本做的事：解压 → 把每个 target 的 `blocks` 和 `comments` 置空 → 其余字段与素材原样透传 → 重新打包。原文件不修改。

典型用途：把成品工程改造成给学生做的空白作业，学生从零搭积木，但角色、背景、声音、变量名、广播名都在。

## When to Use

- 需要把 Scratch 成品工程改成学生用的空白作业
- 需要批量去掉一批工程的脚本，只留素材
- 想看一个工程"去掉逻辑后还剩什么"

需要读取（而非删除）积木内容时，用 `sb3-to-text`；需要 Word 文档时用 `sb3-to-docx`。

## Workflow

```
输入.sb3 ──zip 解压──→ project.json ──清空 blocks/comments──→ 重新打包 ──→ 输入_blank.sb3
                            │                                      │
                      其余字段原样透传                        素材一个字节不动
                                                                   │
                                                          5 项结构校验 + 统计报告
```

## 用法

```bash
python <skill-dir>/strip_blocks.py 输入.sb3
python <skill-dir>/strip_blocks.py 输入.sb3 -o 输出.sb3
python <skill-dir>/strip_blocks.py a.sb3 b.sb3 c.sb3
python <skill-dir>/strip_blocks.py 输入.sb3 --dry-run
```

Windows 下用托管 Python：

```bash
C:/Users/vcom/.workbuddy/binaries/python/versions/3.13.12/python.exe \
  C:/Users/vcom/.workbuddy/skills/sb3-strip/strip_blocks.py "D:/path/项目.sb3"
```

| 参数 | 说明 |
|------|------|
| 默认 | 产物为 `<原名>_blank.sb3`，与输入同目录 |
| `-o` | 指定输出路径，仅在单个输入时可用 |
| 多文件 | 批量处理，逐个自动命名 |
| `--dry-run` | 只打印统计，不生成文件 |

## 保留 / 删除清单

| 对象 | 处理 | 说明 |
|------|------|------|
| `targets[].blocks` | **清空** | 全部脚本积木 |
| `targets[].comments` | **清空** | 依附于积木的注释 |
| `variables` / `lists` / `broadcasts` | 保留 | 变量名和广播名是任务线索 |
| `monitors` | 保留 | 变量都在，引用有效，不会报错 |
| `costumes` / `sounds` 及素材文件 | 保留，一字节不动 | 包括 Scratch 未回收的孤儿素材 |
| `extensions` | 保留 | 学生打开即有画笔/音乐等分类 |
| `x` `y` `size` `direction` `visible` `layerOrder` `currentCostume` `volume` `draggable` `rotationStyle` | 保留，含 `visible: false` | 最小改动原则 |
| 顶层 `meta` | 保留 | Scratch 版本标记 |
| 素材文件 | 原样复制 | 产物 namelist 与输入完全一致 |

净改动只有两个字段，这是最不容易出错的形态。

## 内置校验

产物生成后自动跑，任一项失败则退出码非 0：

1. `testzip()` —— zip 结构完整
2. `project.json` 可解析
3. 所有 target 的 `blocks` 和 `comments` 均为空
4. 所有 `costumes` / `sounds` 的 `md5ext` 指向的文件都存在于包内
5. 产物 namelist 与输入完全一致

## 输出示例

```
============================================================
输入: D:/demo.sb3
输出: D:/demo_blank.sb3
============================================================

[ 角色 ]
  名称                         积木       注释       造型       声音
  Stage                         2        1        1        1 （舞台）
  小松鼠                        5        2        2        1

[ 合计 ]
  删除积木 7 个，注释 3 条
  保留角色 2 个（含舞台）、变量 3 个、列表 1 个、广播 2 条
  monitors=2 extensions=1（均原样保留）
  体积: 2.4 KB → 2.0 KB

[ 校验 ]
  全部通过：zip 完整、project.json 可解析、blocks/comments 已清空、素材引用齐全
```

非 sb3 文件会被跳过并打到 stderr，退出码非 0。

## 实现要点

- **用 Python `zipfile`，不要用 Node**。Node 标准库没有 zip 打包能力，只有 `zlib`，手写 local file header + central directory 得上百行。
- **不要用系统 `zip` 命令**。Windows 的 Git Bash 有 `unzip` 但通常没有 `zip`。
- **先解压到临时目录再打包**，不要全量读进内存 —— 大工程的素材可能几百 MB。
- **`md5ext` 即文件名**，形如 `83a9787d4cb6f3b7632b4ddfebf74367.svg`，直接作为 namelist 的键比对。
- **紧凑序列化**：`separators=(',', ':')` + `ensure_ascii=False`，与 Scratch 官方保存格式一致，中文不转义。
- **zip slip 防护**：解压前校验 namelist 无绝对路径、盘符和 `..`。

## 已知限制

- 无法真正启动 Scratch GUI 验证兼容性，只做结构断言。首次使用建议人工打开产物确认一次。
- 集合工具有隐藏角色（`visible: false`）时，空白工程里它照样隐藏，学生可能以为少了个角色。需要的话在 Scratch 里手动显示，或改脚本加一步。
- 扩展积木在原始工程中的使用情况不会保留，`extensions` 声明在但积木分类为空。

## Common Mistakes

| 错误 | 正确做法 |
|------|----------|
| 用 Node 手写 zip | 用 Python `zipfile`，十行搞定 |
| 调用系统 `zip` 命令 | Windows 上通常不存在该命令 |
| 顺手清掉变量/列表/广播 | 默认全部保留，这是设计决策不是疏漏 |
| 素材"顺手"瘦身 | 默认原样保留；用户需要瘦身先问过再说 |
| 直接改原文件 | 一律输出副本，原文件不动 |
