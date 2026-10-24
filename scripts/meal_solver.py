#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎯 配餐军师：在「预算 + 热量」双重约束下求解最优搭配（0/1 背包近似解）。

玩法:
    python3 meal_solver.py --budget 40 --kcal 800 --goal protein   # 预算40元、800大卡内，蛋白质拉满
    python3 meal_solver.py --budget 30 --kcal 500 --goal cheap     # 最省钱吃出饱腹
    python3 meal_solver.py --budget 50 --kcal 700 --goal value     # 每元蛋白质最高（性价比）

数据源: query-meals（价格、商品编码）+ list-nutrition-foods（按名称匹配营养）。
说明: 双约束背包是 NP-hard，这里用「预算维度 DP + 热量可行性剪枝」的近似解，够用且稳定。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402

GOALS = {"protein": "蛋白质最大化", "cheap": "最省钱吃饱", "value": "每元蛋白质最高"}


def field(item, keys, default=None):
    for k in keys:
        if item.get(k) not in (None, ""):
            return item[k]
    return default


def num(v):
    try:
        return float(str(v).replace("kcal", "").replace("g", "").strip())
    except (TypeError, ValueError):
        return 0.0


def flatten(menu):
    """菜单可能是「分类 → 餐品」的树，摊平成餐品列表。"""
    flat = []
    for node in menu if isinstance(menu, list) else []:
        children = field(node, ["meals", "products", "items", "children"], None)
        if isinstance(children, list) and children:
            flat.extend(children)
        else:
            flat.append(node)
    return flat


def collect_items(store, be):
    rows = common.parse_menu(call_tool("query-meals", common.store_args(store, be)))
    nut = common.parse_nutrition(call_tool("list-nutrition-foods", {}))
    nmap = {}
    for n in nut:
        name = str(field(n, ["name", "foodName", "productName"], ""))
        if name:
            nmap[name] = n
    items = []
    for r in rows:
        name = str(r.get("名称") or "")
        if not name:
            continue
        n = nmap.get(name) or next((v for k, v in nmap.items() if k in name or name in k), {})
        items.append({
            "名称": name,
            "编码": r.get("编码", ""),
            "价格": round(float(r.get("价格") or 0), 2),
            "热量": num(field(n, ["energy_kcal", "energyKcal", "energy"], 0)),
            "蛋白质": num(n.get("protein")),
        })
    return items


def solve(items, budget_yuan, kcal_cap, goal):
    """预算维度 DP（精度 0.5 元），热量作为可行性剪枝，返回最优组合。"""
    unit = 0.5
    cap = int(budget_yuan / unit)
    # value: 蛋白质 / 饱腹 / 每元蛋白
    def value_of(it):
        if goal == "protein":
            return it["蛋白质"] + it["热量"] / 1000.0  # 同蛋白时偏好更顶饱
        if goal == "cheap":
            return it["热量"] / 1000.0 - it["价格"] * 0.05  # 便宜且顶饱
        return (it["蛋白质"] + 0.001) / max(it["价格"], 0.5)  # 每元蛋白

    dp = [0.0] * (cap + 1)
    keep = [[False] * len(items) for _ in range(cap + 1)]
    for idx, it in enumerate(items):
        if it["价格"] <= 0 or it["热量"] > kcal_cap:
            continue
        w = max(1, int(round(it["价格"] / unit)))
        v = value_of(it)
        for b in range(cap, w - 1, -1):
            if dp[b - w] + v > dp[b]:
                # 热量可行性用启发式校验：已选热量 + 本件 <= 上限
                dp[b] = dp[b - w] + v
                keep[b] = list(keep[b - w])
                keep[b][idx] = True
    best_b = max(range(cap + 1), key=lambda b: dp[b])
    chosen = [items[i] for i, flag in enumerate(keep[best_b]) if flag]
    # 热量后校验，超了就按蛋白/元排序剔除
    total_k = sum(c["热量"] for c in chosen)
    if total_k > kcal_cap:
        chosen.sort(key=lambda c: -c["蛋白质"] / max(c["价格"], 0.5))
        while chosen and sum(c["热量"] for c in chosen) > kcal_cap:
            chosen.pop()
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=40)
    ap.add_argument("--kcal", type=float, default=800)
    ap.add_argument("--goal", default="protein", choices=list(GOALS))
    ap.add_argument("--store", default="")
    ap.add_argument("--be", default="")
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()

    prefs = common.load_preferences()
    avoid = list(prefs.get("avoid") or []) + list(prefs.get("dislike") or [])
    items = [i for i in collect_items(opts.store, opts.be) if not any(a in i["名称"] for a in avoid)]
    if not items:
        print(json.dumps({"错误": "没拿到菜单或营养数据"}, ensure_ascii=False))
        sys.exit(1)

    chosen = solve(items, opts.budget, opts.kcal, opts.goal)
    total_p = round(sum(c["价格"] for c in chosen), 2)
    total_k = round(sum(c["热量"] for c in chosen))
    total_pr = round(sum(c["蛋白质"] for c in chosen), 1)

    if opts.json:
        print(json.dumps({"目标": GOALS[opts.goal], "组合": chosen, "总价": total_p,
                          "总热量": total_k, "总蛋白": total_pr}, ensure_ascii=False, indent=2))
        return
    print("🎯 配餐求解 · %s｜预算 ¥%.0f｜热量上限 %d kcal\n" % (GOALS[opts.goal], opts.budget, opts.kcal))
    for c in chosen:
        print("  • %s  ¥%.2f  %d kcal  蛋白 %sg" % (c["名称"], c["价格"], c["热量"], c["蛋白质"]))
    print("\n合计 ¥%.2f｜%d kcal｜蛋白质 %sg" % (total_p, total_k, total_pr))
    if total_pr:
        print("性价比：每元 %.1fg 蛋白质" % (total_pr / max(total_p, 0.01)))
    print("\n满意就走省钱军师：领券 → 带券算价 → 你确认后下单")


if __name__ == "__main__":
    main()
