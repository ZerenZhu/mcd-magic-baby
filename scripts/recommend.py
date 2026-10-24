#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""减脂军师：按卡路里预算从麦当劳营养数据挑能吃的。

用法:
    python3 recommend.py --kcal 500                 # 默认人话输出
    python3 recommend.py --kcal 500 --json          # 机器可读
    python3 recommend.py --kcal 600 --protein-min 25 --limit 5

筛选: 自动合并 preferences.md 的 avoid 忌口词与 dislike 清单。
打分: 贴近预算(饱腹) + 蛋白质优先 - 钠超标惩罚。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402

DEFAULT_AVOID = ["圆椒", "香菜"]


def num(v):
    try:
        return float(str(v).replace("mg", "").replace("g", "").replace("kcal", "").strip())
    except (TypeError, ValueError, AttributeError):
        return None


def get_field(item, keys):
    for k in keys:
        if item.get(k) is not None:
            return item[k]
    return None


def score_item(item, kcal_budget):
    kcal = num(get_field(item, ["energy_kcal", "energyKcal", "energy", "energyKJ"]))
    protein = num(item.get("protein")) or 0
    sodium = num(item.get("sodium")) or 0
    if not kcal or kcal <= 0 or kcal > kcal_budget:
        return None
    s = 40 - abs(kcal_budget - kcal) / kcal_budget * 40
    s += min(protein, 40)
    if sodium > 800:
        s -= (sodium - 800) / 100
    return round(s, 1)


def collect_avoid():
    prefs = common.load_preferences()
    words = list(DEFAULT_AVOID)
    for key in ("avoid", "dislike"):
        v = prefs.get(key)
        if isinstance(v, list):
            words += [str(x) for x in v]
        elif isinstance(v, str) and v:
            words += [x.strip() for x in v.split(",")]
    return [w for w in words if w]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kcal", type=int, default=500, help="单餐卡路里预算")
    ap.add_argument("--protein-min", type=float, default=0)
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--avoid", default="", help="额外忌口词，逗号分隔")
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()

    data = call_tool("list-nutrition-foods", {})
    items = common.parse_nutrition(data)   # 官方返回类 CSV 文本，走统一解析层
    if not items:
        print(json.dumps({"错误": "营养列表为空或返回结构未知", "原始摘要": str(data)[:400]}, ensure_ascii=False))
        sys.exit(1)

    avoid = collect_avoid() + [w for w in opts.avoid.split(",") if w]
    ranked = []
    for it in items:
        name = str(get_field(it, ["name", "foodName", "productName"]) or "")
        if not name or any(w in name for w in avoid):
            continue
        protein = num(it.get("protein")) or 0
        if opts.protein_min and protein < opts.protein_min:
            continue
        s = score_item(it, opts.kcal)
        if s is not None:
            ranked.append((s, name, it))

    ranked.sort(reverse=True, key=lambda x: x[0])
    picks = [{"名称": n, "评分": s,
              "热量kcal": num(get_field(it, ["energy_kcal", "energyKcal", "energy"])),
              "蛋白质g": num(it.get("protein")), "脂肪g": num(it.get("fat")),
              "钠mg": num(it.get("sodium"))} for s, n, it in ranked[: opts.limit]]

    if opts.json:
        print(json.dumps({"预算kcal": opts.kcal, "忌口词": avoid, "推荐": picks}, ensure_ascii=False, indent=2))
        return
    if not picks:
        print("🍟 预算 %d kcal 内没找到合适的（可能忌口太严或预算太低）。" % opts.kcal)
        print("   试试: --kcal %d --protein-min 0，或放宽忌口" % int(opts.kcal * 1.5))
        return
    print("🍟 神奇麦麦宝贝 · %d kcal 内能吃什么\n" % opts.kcal)
    for i, p in enumerate(picks, 1):
        print("%d. %s — %s kcal | 蛋白 %sg | 脂肪 %sg | 钠 %smg"
              % (i, p["名称"], p["热量kcal"], p["蛋白质g"], p["脂肪g"], p["钠mg"]))
    print("\n忌口已过滤: %s" % "、".join(avoid))
    print("决定好了就走省钱军师：领券 → 算价 → 确认后下单（下单一定会先问你）")


if __name__ == "__main__":
    main()
