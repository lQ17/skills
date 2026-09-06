#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strip_blocks.py — 从 Scratch 3 的 .sb3 工程中删除全部积木块，保留资产信息。

产出「空白工程」：角色、造型、背景、声音、变量、列表、广播、扩展声明全部保留，
只有脚本积木和依附其上的注释被清空。原文件不修改。

用法:
    python strip_blocks.py 输入.sb3
    python strip_blocks.py 输入.sb3 -o 输出.sb3
    python strip_blocks.py a.sb3 b.sb3 c.sb3
    python strip_blocks.py 输入.sb3 --dry-run

仅用标准库，跨平台，Windows 下无外部命令依赖。
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import unicodedata
import zipfile

PROJECT_ENTRY = "project.json"


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------

def _safe_member(name):
    """防御 zip slip：拒绝绝对路径、盘符和 .. 逃逸。"""
    if name.startswith("/") or name.startswith("\\"):
        return False
    if len(name) > 1 and name[1] == ":":
        return False
    if ".." in name.replace("\\", "/").split("/"):
        return False
    return True


def _size(path):
    return os.path.getsize(path)


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0
    return "%.1f GB" % n


def _width(s):
    """显示宽度：全角字符算 2 列。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def _pad(s, width):
    """按显示宽度左对齐填充，解决中英混排对不齐的问题。"""
    s = str(s)
    return s + " " * max(0, width - _width(s))


# --------------------------------------------------------------------------
# 核心
# --------------------------------------------------------------------------

def strip_project(zf):
    """读取 project.json，清空每个 target 的 blocks 与 comments，返回 (data, stats)。"""
    raw = zf.read(PROJECT_ENTRY)
    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        data = json.loads(raw.decode("utf-8-sig"))

    targets = data.get("targets")
    if not isinstance(targets, list):
        raise ValueError("project.json 里没有 targets 数组，这可能不是有效的 sb3 工程")

    stats = []
    for t in targets:
        blocks = t.get("blocks") or {}
        comments = t.get("comments") or {}
        stats.append({
            "name": t.get("name") or "<未命名>",
            "isStage": bool(t.get("isStage")),
            "blocks": len(blocks),
            "comments": len(comments),
            "costumes": len(t.get("costumes") or []),
            "sounds": len(t.get("sounds") or []),
            "variables": len(t.get("variables") or {}),
            "lists": len(t.get("lists") or {}),
            "broadcasts": len(t.get("broadcasts") or {}),
        })
        t["blocks"] = {}
        t["comments"] = {}

    return data, stats


def rebuild(zf, data, names, out_path):
    """解压到临时目录 → 替换 project.json → 按原始顺序重新打包。素材一个字节不动。"""
    tmp = tempfile.mkdtemp(prefix="sb3strip_")
    try:
        for n in names:
            if n.endswith("/"):
                continue
            zf.extract(n, tmp)

        pj = os.path.join(tmp, PROJECT_ENTRY)
        with open(pj, "w", encoding="utf-8", newline="") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as out:
            for n in names:
                if n.endswith("/"):
                    continue
                out.write(os.path.join(tmp, n), n)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------

def verify(out_path, orig_names):
    """对产物做结构断言，返回问题列表（空列表表示通过）。"""
    problems = []
    with zipfile.ZipFile(out_path) as z:
        bad = z.testzip()
        if bad is not None:
            problems.append("zip 结构损坏，首个损坏条目: %s" % bad)
            return problems

        names = z.namelist()
        if names != orig_names:
            missing = [n for n in orig_names if n not in names]
            extra = [n for n in names if n not in orig_names]
            if missing:
                problems.append("丢失条目: %s" % ", ".join(missing[:5]))
            if extra:
                problems.append("多出条目: %s" % ", ".join(extra[:5]))

        if PROJECT_ENTRY not in names:
            problems.append("产物里没有 project.json")
            return problems

        try:
            data = json.loads(z.read(PROJECT_ENTRY).decode("utf-8"))
        except Exception as e:
            problems.append("project.json 无法解析: %s" % e)
            return problems

        name_set = set(names)
        for t in data.get("targets", []):
            label = t.get("name") or "<未命名>"
            if t.get("blocks"):
                problems.append("角色「%s」仍有 %d 个积木" % (label, len(t["blocks"])))
            if t.get("comments"):
                problems.append("角色「%s」仍有 %d 条注释" % (label, len(t["comments"])))
            for key in ("costumes", "sounds"):
                for asset in (t.get(key) or []):
                    md5 = asset.get("md5ext")
                    if md5 and md5 not in name_set:
                        problems.append("角色「%s」的%s文件缺失: %s" % (label, key, md5))

    return problems


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------

def print_report(src, dst, stats, data, problems, dry_run):
    print("=" * 60)
    print("输入: %s" % src)
    print("输出: %s" % ("（dry-run，未生成文件）" if dry_run else dst))
    print("=" * 60)

    NAME_W = 22
    print("\n[ 角色 ]")
    print("  %s %8s %8s %8s %8s"
          % (_pad("名称", NAME_W), "积木", "注释", "造型", "声音"))
    for s in stats:
        tag = "（舞台）" if s["isStage"] else ""
        print("  %s %8d %8d %8d %8d %s"
              % (_pad(s["name"][:NAME_W], NAME_W),
                 s["blocks"], s["comments"], s["costumes"], s["sounds"], tag))

    total_blocks = sum(s["blocks"] for s in stats)
    total_comments = sum(s["comments"] for s in stats)
    print("\n[ 合计 ]")
    print("  删除积木 %d 个，注释 %d 条" % (total_blocks, total_comments))
    print("  保留角色 %d 个（含舞台）、变量 %d 个、列表 %d 个、广播 %d 条"
          % (len(stats),
             sum(s["variables"] for s in stats),
             sum(s["lists"] for s in stats),
             sum(s["broadcasts"] for s in stats)))
    print("  monitors=%d extensions=%d（均原样保留）"
          % (len(data.get("monitors") or []),
             len(data.get("extensions") or [])))

    if not dry_run:
        print("  体积: %s → %s" % (_human(_size(src)), _human(_size(dst))))

    print("\n[ 校验 ]")
    if dry_run:
        print("  跳过（dry-run）")
    elif problems:
        for p in problems:
            print("  [失败] %s" % p)
    else:
        print("  全部通过：zip 完整、project.json 可解析、blocks/comments 已清空、素材引用齐全")


# --------------------------------------------------------------------------
# 单文件处理
# --------------------------------------------------------------------------

def process(src, out_path=None, dry_run=False):
    src = os.path.abspath(src)
    if not os.path.isfile(src):
        print("跳过（文件不存在）: %s" % src, file=sys.stderr)
        return False

    if out_path is None:
        base, _ = os.path.splitext(src)
        out_path = base + "_blank.sb3"

    try:
        with zipfile.ZipFile(src) as zf:
            names = zf.namelist()
            bad = [n for n in names if not _safe_member(n)]
            if bad:
                raise ValueError("压缩包内含不安全路径: %s" % bad[0])
            if PROJECT_ENTRY not in names:
                raise ValueError("压缩包里没有 project.json，这不是有效的 sb3 文件")

            data, stats = strip_project(zf)
            if not dry_run:
                rebuild(zf, data, names, out_path)
    except zipfile.BadZipFile:
        print("跳过（不是有效的 zip / sb3 文件）: %s" % src, file=sys.stderr)
        return False
    except Exception as e:
        print("失败: %s —— %s" % (src, e), file=sys.stderr)
        return False

    problems = [] if dry_run else verify(out_path, names)
    print_report(src, out_path, stats, data, problems, dry_run)
    print()
    return not problems


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(
        description="删除 .sb3 工程中的全部积木块，保留角色、背景、声音等资产信息。")
    ap.add_argument("inputs", nargs="+", help="一个或多个 .sb3 文件")
    ap.add_argument("-o", "--output", help="输出路径（仅在传入单个输入时有效）")
    ap.add_argument("--dry-run", action="store_true", help="只打印统计，不生成文件")
    args = ap.parse_args()

    if args.output and len(args.inputs) > 1:
        ap.error("-o 只能用于单个输入文件；批量处理时会自动命名为 <原名>_blank.sb3")

    ok = True
    for i, src in enumerate(args.inputs):
        out = args.output if (args.output and len(args.inputs) == 1) else None
        if i > 0:
            print("-" * 60 + "\n")
        if not process(src, out, args.dry_run):
            ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
