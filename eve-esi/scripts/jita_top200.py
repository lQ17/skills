#!/usr/bin/env python3
"""Jita 日均成交量 Top-N 扫描 + ROI 计算（当前/7日/30日均）+ 中文名 + 判定。

增量缓存设计（缓存目录默认 ~/.eve-esi/cache/）：
  - orderbook.json : 全吉他挂单簿聚合（含 saved_at 时间戳），默认 12 小时内复用，超时才重扫 408 页
  - history.json   : 各候选物品近 40 天日成交，按"最新日期是否 >= 昨天"判断，过期才单条补抓
  - 中文名：优先用本地本地化表 D:/eve中英文对照/eve_localization.json（en->zh，全量覆盖），无需请求 API

用法:
  python scripts/jita_top200.py                                  # 全流程（缓存优先，增量更新）
  python scripts/jita_top200.py --fresh                          # 强制重扫挂单簿 + 重抓全部历史
  python scripts/jita_top200.py --ob-hours 6 --hist-hours 6     # 自定义缓存新鲜度
  python scripts/jita_top200.py --top 100 --sort roi30           # 榜单位数/排序(roi7|roi30|volume)
  python scripts/jita_top200.py --csv "Jita-Top200.csv"          # 输出路径（默认当前目录）
  python scripts/jita_top200.py --no-zh --json                   # 不带中文名 / 机器可读
  python scripts/jita_top200.py --cache D:/my/cache              # 自定义缓存目录

输出列：排名,物品,中文名,type_id,7日均成交量(件),最近日成交量(件),当前最高买价,当前最低卖价,
       毛价差%,单件利润,ROI%,7日平均ROI%,30日平均ROI%,判定
判定规则（按 7日平均ROI%）：>=5 好 / >=3 可做 / >0 勉强 / <=0 亏
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

BASE = "https://esi.evetech.net/latest"
UA = "OpenClaw-ESI-Skill/1.0 (jita_top200)"
REGION = 10000002
DEFAULT_LOC = Path("D:/eve中英文对照/eve_localization.json")
BF = SF = 0.018          # Maybe Master 当前费率
ST = 0.042
DENOM = 1 - SF - ST
BF1 = 1 + BF
OB_HOURS_DEFAULT = 12
HIST_HOURS_DEFAULT = 24
CANDIDATES = 600
OB_WORKERS = 8
HIST_WORKERS = 4

HEADERS = ["排名", "物品", "中文名", "type_id", "7日均成交量(件)", "最近日成交量(件)",
           "当前最高买价", "当前最低卖价", "毛价差%", "单件利润", "ROI%",
           "7日平均ROI%", "30日平均ROI%", "判定"]


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def get(url, retries=6):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8")), r.headers
        except urllib.error.HTTPError as e:
            if e.code == 420 and a < retries - 1:
                time.sleep(min(5, 30)); continue
            if e.code in (502, 503, 504) and a < retries - 1:
                time.sleep(2 ** a); continue
            if e.code == 404:
                return None, {}
            raise
        except (urllib.error.URLError, ConnectionError, OSError):
            if a < retries - 1:
                time.sleep(1.5 * (a + 1)); continue
            raise
    raise RuntimeError("unreachable")


def cache_paths(cache_dir: Path) -> tuple[Path, Path]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "orderbook.json", cache_dir / "history.json"


def load_orderbook(cache_dir: Path, max_age_hours: int, fresh: bool) -> dict:
    ob_path, _ = cache_paths(cache_dir)
    if not fresh and ob_path.exists():
        try:
            data = json.loads(ob_path.read_text(encoding="utf-8"))
            saved = data.get("saved_at", 0)
            if time.time() - saved < max_age_hours * 3600:
                log(f"orderbook 缓存命中（{max_age_hours}h 内），{len(data['book'])} 种")
                return data["book"]
        except Exception:
            pass
    log("重扫全吉他挂单簿（多线程）...")
    _, h = get(f"{BASE}/markets/{REGION}/orders/?page=1")
    pages = int(h.get("x-pages", "1"))
    book = {}

    def scan_page(p):
        data, _ = get(f"{BASE}/markets/{REGION}/orders/?page={p}")
        return data

    done = [0]
    with ThreadPoolExecutor(max_workers=OB_WORKERS) as ex:
        futs = {ex.submit(scan_page, p): p for p in range(1, pages + 1)}
        for fu in as_completed(futs):
            try:
                for o in fu.result():
                    e = book.setdefault(str(o["type_id"]), {"buy": 0, "sell": 0, "bb": None, "bs": None})
                    if o["is_buy_order"]:
                        e["buy"] += o["volume_remain"]
                        if e["bb"] is None or o["price"] > e["bb"]:
                            e["bb"] = o["price"]
                    else:
                        e["sell"] += o["volume_remain"]
                        if e["bs"] is None or o["price"] < e["bs"]:
                            e["bs"] = o["price"]
            except Exception:
                pass
            done[0] += 1
            if done[0] % 80 == 0:
                log(f"  ob {done[0]}/{pages}")
    ob_path.write_text(json.dumps({"saved_at": int(time.time()), "book": book}), encoding="utf-8")
    log(f"orderbook 完成：{len(book)} 种（已缓存）")
    return book


def ensure_history(cache_dir: Path, tids: list[str], max_age_hours: float, fresh: bool) -> dict:
    _, hist_path = cache_paths(cache_dir)
    raw = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}
    if "data" not in raw:  # v1 -> v2 迁移
        raw = {"fetched_at": {t: time.time() for t in raw}, "data": raw}
    hist, fetched_at = raw["data"], raw.get("fetched_at", {})
    # ESI 市场历史滞后约 2 天，过期线取"前天"
    cutoff = (date.today() - timedelta(days=2)).isoformat()
    todo = []
    for t in tids:
        if fresh:
            todo.append(t)
            continue
        es = [x for x in hist.get(t, []) if isinstance(x, dict) and x.get("date")]
        if not es:
            todo.append(t)
            continue
        last_date = max(e["date"] for e in es)
        last_fetch = fetched_at.get(t, 0)
        if last_date < cutoff and time.time() - last_fetch > max_age_hours * 3600:
            todo.append(t)
    if not todo:
        log(f"history 缓存全部新鲜（{len(tids)} 种），无需补抓")
        return hist
    log(f"history 需补抓 {len(todo)} 种（多线程，失败可断点续跑）...")

    def fetch(tid):
        data, _ = get(f"{BASE}/markets/{REGION}/history/?type_id={tid}")
        return str(tid), ([x for x in data[-40:]] if isinstance(data, list) else [])

    done = [0]
    with ThreadPoolExecutor(max_workers=HIST_WORKERS) as ex:
        futs = {ex.submit(fetch, t): t for t in todo}
        for fu in as_completed(futs):
            tid, entries = fu.result()
            hist[tid] = entries
            fetched_at[tid] = time.time()
            done[0] += 1
            if done[0] % 25 == 0:
                hist_path.write_text(json.dumps({"fetched_at": fetched_at, "data": hist},
                                                 ensure_ascii=False), encoding="utf-8")
                log(f"  hist {done[0]}/{len(todo)}（已增量保存）")
    hist_path.write_text(json.dumps({"fetched_at": fetched_at, "data": hist},
                                     ensure_ascii=False), encoding="utf-8")
    log("history 缓存已更新")
    return hist


def load_zh_map(loc_path: Path | None, enabled: bool) -> dict:
    if not enabled or not loc_path or not loc_path.exists():
        return {}
    d = json.loads(loc_path.read_text(encoding="utf-8"))
    en2zh, best = {}, {}
    for v in d.values():
        en, zh, st = v.get("en"), v.get("zh"), v.get("status")
        if not en or not zh:
            continue
        if en not in en2zh:
            en2zh[en] = zh
            best[en] = st == "matched"
        elif st == "matched" and not best.get(en):
            en2zh[en] = zh
            best[en] = True
    log(f"本地化表加载 {len(en2zh)} 个 en->zh")
    return en2zh


def avg_vol(entries: list[dict]) -> float:
    vs = [x["volume"] for x in entries if isinstance(x, dict) and x.get("volume") is not None]
    return (sum(vs[-7:]) / max(len(vs[-7:]), 1)) if vs else 0


def roi_n(entries: list[dict], n: int) -> float | None:
    days = [e for e in entries[-60:] if isinstance(e, dict)
            and e.get("volume", 0) > 0 and (e.get("lowest") or 0) > 0][-n:]
    if not days:
        return None
    rois = []
    for e in days:
        low = e.get("lowest") or e["average"]
        high = e.get("highest") or e["average"]
        rois.append((high * DENOM - low * BF1) / (low * BF1) * 100)
    return sum(rois) / len(rois)


def verdict(v7: float | None) -> str:
    if v7 is None:
        return "—"
    if v7 >= 5:
        return "好"
    if v7 >= 3:
        return "可做"
    if v7 > 0:
        return "勉强"
    return "亏"


def main() -> None:
    ap = argparse.ArgumentParser(description="Jita 日均成交量 Top-N + ROI 全流程（增量缓存）")
    ap.add_argument("--top", type=int, default=200)
    ap.add_argument("--fresh", action="store_true", help="强制重扫挂单簿并重抓全部历史")
    ap.add_argument("--ob-hours", type=float, default=OB_HOURS_DEFAULT, help="挂单簿缓存有效期（小时）")
    ap.add_argument("--hist-hours", type=float, default=HIST_HOURS_DEFAULT, help="历史缓存有效期（小时）")
    ap.add_argument("--sort", choices=["roi7", "roi30", "volume"], default="roi7")
    ap.add_argument("--csv", default=None, help="输出 CSV 路径（默认 ./Jita-Top{N}-roi7.csv）")
    ap.add_argument("--cache", default=None, help="缓存目录（默认 ~/.eve-esi/cache）")
    ap.add_argument("--loc", default=str(DEFAULT_LOC), help="本地化 JSON 路径")
    ap.add_argument("--no-zh", action="store_true", help="不加载中文名")
    ap.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    ap.add_argument("--region", type=int, default=REGION)
    args = ap.parse_args()

    cache_dir = Path(args.cache) if args.cache else Path.home() / ".eve-esi" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    book = load_orderbook(cache_dir, args.ob_hours, args.fresh)
    cands = sorted(book.items(), key=lambda kv: kv[1]["buy"] + kv[1]["sell"], reverse=True)[:CANDIDATES]
    cids = [k for k, _ in cands]
    hist = ensure_history(cache_dir, cids, args.hist_hours, args.fresh)

    rows = []
    for tid, o in book.items():
        es = hist.get(tid, [])
        v7v = avg_vol(es)
        if v7v <= 0:
            continue
        rows.append({"tid": int(tid), "v7": v7v,
                     "last": es[-1]["volume"] if es else 0, "ob": o, "es": es})
    rows.sort(key=lambda r: -r["v7"])
    rows = rows[: args.top]

    names = {}
    try:
        body = json.dumps([r["tid"] for r in rows]).encode("utf-8")
        req = urllib.request.Request(BASE + "/universe/names/", data=body, method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            for it in json.loads(resp.read().decode("utf-8")):
                names[it["id"]] = it["name"]
    except Exception:
        pass

    en2zh = load_zh_map(Path(args.loc), not args.no_zh)
    out_rows = []
    for r in rows:
        o = r["ob"]
        bb, bs = o["bb"], o["bs"]
        v7 = roi_n(r["es"], 7)
        v30 = roi_n(r["es"], 30)
        row = {
            "物品": names.get(r["tid"], str(r["tid"])),
            "中文名": en2zh.get(names.get(r["tid"], ""), "") if en2zh else "",
            "type_id": r["tid"],
            "7日均成交量(件)": f'{r["v7"]:,.0f}',
            "最近日成交量(件)": f'{r["last"]:,.0f}',
            "当前最高买价": f'{bb:,.0f}' if bb else "-",
            "当前最低卖价": f'{bs:,.0f}' if bs else "-",
            "毛价差%": f'{(bs - bb) / bb * 100:.2f}' if bb and bs and bb > 0 else "-",
            "单件利润": f'{bs * DENOM - bb * BF1:+,.0f}' if bb and bs else "-",
            "ROI%": f'{((bs * DENOM - bb * BF1) / (bb * BF1) * 100):+.2f}' if bb and bs and bb > 0 else "-",
            "7日平均ROI%": f"{v7:+.2f}" if v7 is not None else "-",
            "30日平均ROI%": f"{v30:+.2f}" if v30 is not None else "-",
            "判定": verdict(v7),
        }
        out_rows.append(row)

    keyfn = {"roi7": lambda r: float(r["7日平均ROI%"]) if r["7日平均ROI%"] not in ("-",) else float("-inf"),
             "roi30": lambda r: float(r["30日平均ROI%"]) if r["30日平均ROI%"] not in ("-",) else float("-inf"),
             "volume": lambda r: float(r["7日均成交量(件)"].replace(",", ""))}[args.sort]
    out_rows.sort(key=keyfn, reverse=True)
    for i, r in enumerate(out_rows, 1):
        r["排名"] = i
    out_rows = [{**{"排名": r["排名"]}, **{k: v for k, v in r.items() if k != "排名"}} for r in out_rows]

    if args.json:
        print(json.dumps(out_rows, ensure_ascii=False, indent=2))
        return

    csv_path = Path(args.csv) if args.csv else Path(f"./Jita-Top{args.top}-{args.sort}.csv")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(out_rows)

    print()
    print(f"费率 BF={BF*100}% SF={SF*100}% ST={ST*100}% | 榜单 {args.top} 名 | 排序 {args.sort} | 缓存 {cache_dir}")
    print(f'{"排名":>3} {"中文名":<16}{"英文名":<26}{"7日均ROI":>9}{"30日均ROI":>9}{"7日均量":>13}{"判定":>4}')
    print("-" * 92)
    for r in out_rows[:25]:
        print(f"{r['排名']:>3} {r['中文名'][:16]:<16}{r['物品'][:26]:<26}"
              f"{r['7日平均ROI%']:>9}{r['30日平均ROI%']:>9}"
              f"{r['7日均成交量(件)']:>13}  {r['判定']}")
    print()
    print(f"完整 {args.top} 行已存: {csv_path}")
    print("下次更新直接重跑本脚本即可（挂单簿/历史走缓存，仅增量补抓）")


if __name__ == "__main__":
    main()
