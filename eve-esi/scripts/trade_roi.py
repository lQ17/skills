#!/usr/bin/env python3
"""EVE 交易 ROI 快速计算器（含销量维度，默认吉他 Jita）。

针对"两边挂单倒卖"模型：
  单件利润 = S*(1-SF-ST) - B*(1+BF)          （B=买入价 S=卖出价）
  ROI      = 利润 / 投入成本(B*(1+BF))
默认费率 = Maybe Master 当前值：BF=1.8% SF=1.8% ST=4.2%（可用参数覆盖）

销量维度：最近日成交量 + 近7日均成交量 + 买/卖盘余量 + 日利润潜力(单件利润×日均成交量)

用法:
  python trade_roi.py "Power Circuit"                    # 按名字（精确/自动变体）
  python trade_roi.py berserker                          # 模糊（内置清单前缀/包含匹配）
  python trade_roi.py --id 25617 3841 2478               # 按 type_id，可多个
  python trade_roi.py "Power Circuit" --qty 100          # 指定单笔数量（算总利润）
  python trade_roi.py "Power Circuit" --bf 1.8 --sf 1.8 --st 4.2   # 自定义费率
  python trade_roi.py --region 10000002 "Power Circuit"  # 指定区域（默认吉他 The Forge）
  python trade_roi.py --min-roi 5 -- "A" "B"             # 只看 ROI>=5% 的
  python trade_roi.py --list                             # 列出内置常用物品（模糊匹配用）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import format_isk  # noqa: E402

BASE = "https://esi.evetech.net/latest"
UA = "OpenClaw-ESI-Skill/1.0 (trade_roi)"
REGION_JITA = 10000002

# 默认费率（Maybe Master：Accounting L4 / Broker Relations L4 / 声望0）
DEFAULT_BF = 1.8
DEFAULT_SF = 1.8
DEFAULT_ST = 4.2

# 内置常用物品（type_id 已核实），用于模糊匹配
COMMON = {
    "Tritanium": 34, "Pyerite": 35, "Mexallon": 36, "Isogen": 37, "Nocxium": 38,
    "Zydrine": 39, "Megacyte": 40, "Carbon": 9826,
    "Large Shield Extender II": 3841, "Medium Shield Extender II": 3831,
    "Small Shield Extender II": 380, "Large Shield Extender I": 3839,
    "1600mm Steel Plates II": 20353, "Damage Control II": 2048, "Damage Control I": 2046,
    "Gyrostabilizer II": 519, "Gyrostabilizer I": 520, "Heat Sink II": 2364,
    "Magnetic Field Stabilizer II": 10190, "Ballistic Control System II": 22291,
    "Tracking Computer II": 1978, "Tracking Enhancer II": 1999,
    "Berserker II": 2478, "Berserker I": 2476, "Warrior II": 2488, "Hobgoblin II": 2456,
    "Hammerhead II": 2185, "Valkyrie II": 21640, "Infiltrator II": 2175,
    "Acolyte II": 2205, "Praetor II": 2195, "Garde II": 28211, "Curator II": 28213,
    "Bouncer II": 28215, "Warden II": 28209,
    "Power Circuit": 25617, "Logic Circuit": 25619, "Micro Circuit": 25618,
    "Trigger Unit": 25612, "Burned Logic Circuit": 25600,
    "Nanite Repair Paste": 28668, "Nitrogen Fuel Block": 4051, "Coolant": 9832,
    "Mechanical Parts": 3689, "Construction Blocks": 3828, "Robotics": 9848,
    "Antimatter Charge S": 222, "Antimatter Charge M": 230, "Antimatter Charge L": 238,
    "Venture": 32880, "Vexor": 626, "Hurricane": 24702, "Noctis": 2998,
    "Procurer": 17480, "Retriever": 17478, "Covetor": 17476, "Hulk": 22544,
    "Mackinaw": 22548, "Orca": 28606, "Porpoise": 42244, "Tayra": 649,
    "Accounting": 16622, "Broker Relations": 3446, "Trade": 3443, "Retail": 3444,
    "Wholesale": 16596, "Marketing": 16598, "Daytrading": 16595,
    "Procurement": 16594, "Contracting": 25235, "Corporation Contracting": 25233,
    "Tycoon": 18580, "Visibility": 3447, "Advanced Broker Relations": 16597,
}


def _get(url: str, retries: int = 3) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (420, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def _post(url: str, body: list) -> dict | list:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\x20-\x7E]+", " ", s)).strip()


def roman_variants(s: str) -> list[str]:
    to_digit = s
    for rom, dig in (("III", "3"), ("II", "2"), ("IV", "4"), ("V", "5"), ("I", "1")):
        to_digit = re.sub(r"\b" + rom + r"\b", dig, to_digit)
    to_roman = s
    for dig, rom in (("2", "II"), ("1", "I"), ("3", "III"), ("4", "IV"), ("5", "V")):
        to_roman = re.sub(dig, rom, to_roman)
    return list(dict.fromkeys([s, to_digit, to_roman]))


def resolve_type_id(raw: str) -> int | None:
    name = normalize(raw)
    if not name:
        return None
    if name.isdigit():
        return int(name)
    if name in COMMON:
        return COMMON[name]
    for v in roman_variants(name):
        if v in COMMON:
            return COMMON[v]
    try:
        j = _post(BASE + "/universe/ids/", roman_variants(name))
        hits = (j or {}).get("inventory_types") or []
        if hits:
            return hits[0]["id"]
    except Exception:
        pass
    try:
        j = _get(BASE + "/search/?categories=inventory_type&search="
                 + urllib.parse.quote(name) + "&strict=false")
        ids = (j or {}).get("inventory_type") or []
        if ids:
            return ids[0]
    except Exception:
        pass
    low = name.lower()
    if len(low) >= 3:
        for k, tid in COMMON.items():
            kl = k.lower()
            if kl.startswith(low) or low in kl:
                return tid
    return None


def fetch_market(tid: int, region: int) -> dict:
    orders = _get(f"{BASE}/markets/{region}/orders/?type_id={tid}&order_type=all")
    buys = [o for o in orders if o["is_buy_order"]]
    sells = [o for o in orders if not o["is_buy_order"]]
    best_buy = max((o["price"] for o in buys), default=None)
    best_sell = min((o["price"] for o in sells), default=None)
    buy_vol = sum(o["volume_remain"] for o in buys)
    sell_vol = sum(o["volume_remain"] for o in sells)
    hist = []
    try:
        hist = _get(f"{BASE}/markets/{region}/history/?type_id={tid}")
    except Exception:
        pass
    vols = [h["volume"] for h in hist if isinstance(h, dict) and h.get("volume") is not None]
    last_vol = vols[-1] if vols else 0
    avg7 = sum(vols[-7:]) / min(len(vols[-7:]), 7) if vols else 0
    return {"best_buy": best_buy, "best_sell": best_sell,
            "buy_vol": buy_vol, "sell_vol": sell_vol,
            "last_vol": last_vol, "avg7": avg7}


def compute(tid: int, region: int, qty: int, bf: float, sf: float, st: float) -> dict:
    info = _get(f"{BASE}/universe/types/{tid}/")
    m = fetch_market(tid, region)
    B, S = m["best_buy"], m["best_sell"]
    bf, sf, st = bf / 100, sf / 100, st / 100
    if B is None or S is None:
        return {"tid": tid, "name": info.get("name", str(tid)),
                "ok": False, "why": "该物品在本区域无挂单"}
    denom = 1 - sf - st
    cost_unit = B * (1 + bf)
    net_unit = S * denom
    profit_unit = net_unit - cost_unit
    cost = cost_unit * qty
    profit = profit_unit * qty
    roi = profit / cost * 100 if cost else 0
    gross = (S - B) / B * 100
    breakeven = B * (1 + bf) / denom
    daily_potential = profit_unit * m["avg7"]
    return {"tid": tid, "name": info.get("name", str(tid)), "ok": True,
            "B": B, "S": S, "qty": qty, "gross": gross,
            "profit_unit": profit_unit, "profit": profit, "roi": roi,
            "breakeven": breakeven, "last_vol": m["last_vol"], "avg7": m["avg7"],
            "buy_vol": m["buy_vol"], "sell_vol": m["sell_vol"],
            "daily_potential": daily_potential}


def verdict(r: dict) -> str:
    if not r["ok"]:
        return r["why"]
    roi = r["roi"]
    if roi <= 0:
        return "亏损，不要碰"
    tags = []
    if r["avg7"] < 10:
        tags.append("量极小")
    elif r["avg7"] < 100:
        tags.append("量小")
    if roi >= 10:
        tags.append("高ROI，查假价/成交")
    elif roi >= 5:
        tags.append("好")
    elif roi >= 3:
        tags.append("可做")
    else:
        tags.append("勉强")
    return "，".join(tags)


def main() -> None:
    ap = argparse.ArgumentParser(description="EVE 交易 ROI 快速计算（吉他默认）")
    ap.add_argument("items", nargs="*", help="物品名（可模糊）或 --id 列表")
    ap.add_argument("--id", dest="ids", nargs="+", type=int, help="按 type_id")
    ap.add_argument("--qty", type=int, default=1, help="单笔数量（默认1）")
    ap.add_argument("--bf", type=float, default=DEFAULT_BF, help=f"买单经纪费% (默认{DEFAULT_BF})")
    ap.add_argument("--sf", type=float, default=DEFAULT_SF, help=f"卖单经纪费% (默认{DEFAULT_SF})")
    ap.add_argument("--st", type=float, default=DEFAULT_ST, help=f"销售税% (默认{DEFAULT_ST})")
    ap.add_argument("--region", type=int, default=REGION_JITA, help="区域ID (默认吉他10000002)")
    ap.add_argument("--min-roi", type=float, default=None, help="只显示 ROI>= 此值的（默认显示全部，含亏损）")
    ap.add_argument("--sort", choices=["roi", "potential"], default="potential", help="排序")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--list", action="store_true", help="列出内置常用物品")
    args = ap.parse_args()

    if args.list:
        for k in sorted(COMMON):
            print(f"  {k:<34} {COMMON[k]}")
        return

    tids: list[int] = list(args.ids or [])
    for it in args.items:
        tid = resolve_type_id(it)
        if tid is None:
            print(f"✗ 无法解析: {it}", file=sys.stderr)
        else:
            tids.append(tid)
    if not tids:
        ap.error("请提供物品名或 --id")

    results = []
    for tid in tids:
        try:
            r = compute(tid, args.region, args.qty, args.bf, args.sf, args.st)
            results.append(r)
        except Exception as e:
            print(f"✗ type {tid} 查询失败: {e}", file=sys.stderr)

    if args.min_roi is not None:
        results = [r for r in results if r["ok"] and r["roi"] >= args.min_roi]
    results.sort(key=lambda r: (r["daily_potential"] if args.sort == "potential" else r["roi"]),
                 reverse=True)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"费率: BF={args.bf}% SF={args.sf}% ST={args.st}% | Q={args.qty} | 区域 {args.region} | "
          f"按{'日利润潜力' if args.sort=='potential' else 'ROI'}排序")
    print()
    hdr = f'{"物品":<26}{"毛价差":>8}{"单件利润":>12}{"ROI":>8}{"总利润":>14}{"日成交":>10}{"日利润潜力":>14}  判定'
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        print(f'{r["name"][:26]:<26}'
              f'{r["gross"]:>7.1f}%'
              f'{(r["profit_unit"]>=0 and "+" or "")+format_isk(r["profit_unit"]):>12}'
              f'{r["roi"]:>+7.2f}%'
              f'{(r["profit"]>=0 and "+" or "")+format_isk(r["profit"]):>14}'
              f'{r["avg7"]:>10,.0f}'
              f'{(r["daily_potential"]>=0 and "+" or "")+format_isk(r["daily_potential"]):>14}  '
              f'{verdict(r)}')
    print()
    print("日成交 = 近7日日均成交量(件)；日利润潜力 = 单件利润 × 日成交（理论日收益上限，实际受挂单/价格波动影响）")
    print(f"保本卖价参考：B×(1+BF)/(1-SF-ST)；更多细节见 eve-trade-calculator.html")


if __name__ == "__main__":
    main()
