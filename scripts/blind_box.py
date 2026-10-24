#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎁 麦麦点餐盲盒 —— 神奇麦麦宝贝的第二主轴。

抽卡式点餐，稀有度由餐品价格/规格决定，概率受「今日运势」与「今日幸运单品」双重影响。

稀有度（按餐品价格/规格）:
    ✨SSR  ≥30 元  旗舰堡/大份全家桶   （基础 5%）
    🌟SR   18~30 元 主力堡/大份小食    （基础 15%）
    🔹R    9~18 元  小食/中份饮料      （基础 35%）
    ▪️N    <9 元   甜品/小杯饮料       （基础 45%）

与运势联动（fortune.py 算出的麦门指数 ★1~5）:
    ★5 → SSR ×2.2 / SR ×1.5    手气爆棚，今天适合赌一把
    ★4 → SSR ×1.6 / SR ×1.25
    ★3 → 不加不减
    ★2 → SSR ×0.7 / SR ×0.85
    ★1 → SSR ×0.5 / SR ×0.7    诸事不宜，老老实实点本命餐品

玩法:
    python3 blind_box.py                     # 今日一抽（日期为种子，同一天结果一致）
    python3 blind_box.py --mode 放纵         # 省着吃 / 正常 / 放纵 / 减脂
    python3 blind_box.py --seed 1024         # 换种子 = 换一抽
    python3 blind_box.py --ten               # 十连抽（保底至少一张 SR 以上）
    python3 blind_box.py --collection        # 查看我的图鉴与保底进度
    python3 blind_box.py --no-lucky          # 关闭今日幸运单品加权
    python3 blind_box.py --no-fortune        # 关闭运势手气加成（纯基础概率）

保底: 连续 5 抽没出 SR 以上，第 6 抽强制出货；十连必出一张 SR+。
"""
import argparse
import json
import os
import random
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402
import fortune  # noqa: E402

MODES = {
    "省着吃": {"groups": ["主食", "饮料"], "kcap": 700, "words": "省钱又顶饱"},
    "正常":   {"groups": ["主食", "小食", "饮料"], "kcap": 900, "words": "标准操作，稳"},
    "放纵":   {"groups": ["主食", "小食", "饮料", "甜品"], "kcap": 1600, "words": "今天不算热量"},
    "减脂":   {"groups": ["主食", "饮料"], "kcap": 450, "words": "管住嘴，明天称上见"},
}
# 分类别名：不同门店返回的分类名不同（真实门店见过：鸡肉汉堡/卷、小食甜品/其他、麦咖啡™、饮品）
ALIASES = {"主食": ["主食", "汉堡", "堡", "卷", "大堡"],
           "小食": ["小食", "炸鸡", "炸物", "薯", "鸡块", "翅", "小食类"],
           "饮料": ["饮料", "饮品", "咖啡", "可乐"],
           "甜品": ["甜品", "派", "冰品", "甜点", "旋风"]}
RARITY = [("SSR", 30, "✨", 5), ("SR", 18, "🌟", 15), ("R", 9, "🔹", 35), ("N", 0, "▪️", 45)]
# 今日运势(★1~5) → (SSR 权重倍率, SR 权重倍率)：运势越好越容易出货
LUCK_BOOST = {5: (2.2, 1.5), 4: (1.6, 1.25), 3: (1.0, 1.0), 2: (0.7, 0.85), 1: (0.5, 0.7)}
LUCK_HINT = {5: "五星大吉 —— 今天适合赌一把十连",
             4: "手气不错 —— 单抽出货概率明显偏高",
             3: "运势平平 —— 别慌，保底机制兜着你",
             2: "手气偏弱 —— 建议老实点回本命餐品",
             1: "诸事不宜 —— 不如明天再开，或先去领张券"}
HISTORY_PATH = os.path.join(common.RUNTIME_DIR, "box_history.json")


def field(item, keys, default=None):
    for k in keys:
        if item.get(k) not in (None, ""):
            return item[k]
    return default


def flatten(items):
    """统一后的菜单项 → [(分类, 餐品 dict)]（保留旧调用方式）。"""
    return [(i.get("分类", ""), i) for i in items]


def rarity_of(price, kcal, protein):
    """优先按价格定级；菜单没返回价格时，用热量/蛋白质兜底。"""
    if price:
        for name, threshold, _, _ in RARITY:
            if price >= threshold:
                return name
    if kcal and kcal >= 500:
        return "SR"
    if protein and protein >= 20:
        return "SR"
    return "R"


def meta(name):
    return next((r for r in RARITY if r[0] == name), RARITY[-1])


def load_history():
    return common.load_json(HISTORY_PATH, {"draws": [], "pity": 0})


def save_history(h):
    common.save_json(HISTORY_PATH, h)


def weighted_pick(candidates, rng, lucky_name, no_lucky, boost=(1.0, 1.0)):
    """两阶段抽卡：先按稀有度档位（SSR 5% / SR 15% / R 35% / N 45%，受运势倍率影响），
    再在档位内抽取 —— 今日幸运单品在档位内权重 ×4。"""
    if not candidates:
        return None
    ssr_mul, sr_mul = boost
    tiers = {}
    for c in candidates:
        tiers.setdefault(c["稀有度"], []).append(c)
    order_names = [r[0] for r in RARITY if r[0] in tiers]
    weights = []
    for n in order_names:
        w = float(meta(n)[3])
        w *= ssr_mul if n == "SSR" else sr_mul if n == "SR" else 1.0
        weights.append(max(w, 0.01))
    tier = rng.choices(order_names, weights=weights, k=1)[0]
    pool = tiers[tier]
    lw = [4 if (not no_lucky and c["名称"] == lucky_name) else 1 for c in pool]
    return rng.choices(pool, weights=lw, k=1)[0]


def group_match(cat, name, group):
    """优先按分类名匹配；分类为空时退化为按餐品名匹配。"""
    aliases = ALIASES.get(group, [group])
    text = (cat or "").strip()
    if text:
        return any(a in text for a in aliases)
    return any(a in (name or "") for a in aliases)


def build_pool(items, nut_list, groups, avoid):
    nmap = {}
    for n in nut_list:
        nm = str(field(n, ["name", "foodName", "productName"], ""))
        if nm:
            nmap[nm] = n
    pool = []
    for cat, item in flatten(items):
        name = str(field(item, ["名称", "name", "productName", "mealName"], ""))
        if not name or any(a in name for a in avoid):
            continue
        if not any(group_match(cat, name, g) for g in groups):
            continue
        price = float(item.get("价格") or 0)
        n = nmap.get(name) or next((v for k, v in nmap.items() if k in name or name in k), {})
        kcal = float(field(n, ["energy_kcal", "energyKcal", "energy"], 0) or 0)
        protein = float(field(n, ["protein"], 0) or 0)
        pool.append({"名称": name, "分类": cat, "价格": round(price, 2),
                     "热量": round(kcal), "蛋白质": round(protein, 1),
                     "稀有度": rarity_of(price, kcal, protein)})
    return pool


def draw_once(pool, rng, lucky, no_lucky, pity_forced, exclude=(), boost=(1.0, 1.0)):
    cand = [c for c in pool if c["名称"] not in exclude]
    if not cand:
        cand = pool
    if pity_forced:
        top = [c for c in cand if c["稀有度"] in ("SSR", "SR")] or cand
        return rng.choice(top)
    return weighted_pick(cand, rng, lucky, no_lucky, boost)


def draw_set(pool, rng, groups, lucky, no_lucky, pity_forced, kcap, boost=(1.0, 1.0)):
    """单抽：每个分类各抽一件，凑成能吃的一套（热量超上限就换轻的）。"""
    picks, kcal_total = [], 0
    used_cats = set()
    for g in groups:
        # 同一分类只抽一件，避免抽到两个汉堡
        cand = [c for c in pool if group_match(c["分类"], c["名称"], g)
                and (c["分类"] or c["名称"]) not in used_cats]
        if not cand:  # 分类被别的组占用（如「小食甜品/其他」）→ 退而按餐品名匹配
            used_names = {p["名称"] for p in picks}
            cand = [c for c in pool if c["名称"] not in used_names
                    and any(a in c["名称"] for a in ALIASES.get(g, [g]))]
        if not cand:
            continue
        forced = pity_forced and not any(c["稀有度"] in ("SSR", "SR") for c in picks)
        pick = draw_once(cand, rng, lucky, no_lucky, forced,
                         exclude=[p["名称"] for p in picks], boost=boost)
        if pick and kcap and kcal_total + pick["热量"] > kcap:
            light = [c for c in cand if kcal_total + c["热量"] <= kcap]
            if light:
                pick = rng.choice(light)
        if pick:
            picks.append(pick)
            kcal_total += pick["热量"]
            used_cats.add(pick["分类"] or pick["名称"])
    return picks, kcal_total


def best_combo(cards, groups):
    """从十连的卡里挑出能吃的一套（每分类取最高稀有度的一件，不重复）。"""
    combo, used_cats = [], set()
    for g in groups:
        cand = [c for c in cards if group_match(c["分类"], c["名称"], g)
                and (c["分类"] or c["名称"]) not in used_cats]
        if cand:
            top = max(cand, key=lambda c: (order.index(c["稀有度"]), c["蛋白质"]))
            combo.append(top)
            used_cats.add(top["分类"] or top["名称"])
    return combo


def fit_budget(pool, picks, budget, groups, keep=()):
    """超出预算时，从最贵的一件开始向下换同组餐品 —— 让命运向钱包低头。

    keep: 不参与降级的索引（十连/单抽里最稀有的那件战利品，不能被剥夺）。
    """
    picks = list(picks)
    keep_names = {picks[i]["名称"] for i in keep if 0 <= i < len(picks)}
    blocked = set()
    for _ in range(30):
        if sum(p["价格"] for p in picks) <= budget:
            break
        open_idx = [i for i in range(len(picks))
                    if i not in blocked and picks[i]["名称"] not in keep_names]
        if not open_idx:
            break
        idx = max(open_idx, key=lambda i: picks[i]["价格"])
        cur = picks[idx]
        g = next((g for g in groups if group_match(cur["分类"], cur["名称"], g)), None)
        used = {p["名称"] for p in picks}
        cand = [c for c in pool if c["名称"] not in used and c["价格"] < cur["价格"]
                and (group_match(c["分类"], c["名称"], g) if g else False)]
        if not cand:
            blocked.add(idx)      # 这组已经到底了，去降别的
            continue
        picks[idx] = min(cand, key=lambda c: c["价格"])
        blocked.clear()
    # 还是超 → 割掉一件配角，保住主堡
    while len(picks) > 1 and sum(p["价格"] for p in picks) > budget:
        side = [i for i, p in enumerate(picks)
                if not group_match(p["分类"], p["名称"], "主食")
                and p["名称"] not in keep_names]
        if not side:
            break
        del picks[max(side, key=lambda i: picks[i]["价格"])]
    return picks


order = ["N", "R", "SR", "SSR"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=None, choices=list(MODES), help="默认读 preferences.md 的 box_mode")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--ten", action="store_true", help="十连抽")
    ap.add_argument("--collection", action="store_true", help="查看图鉴与保底进度")
    ap.add_argument("--no-lucky", action="store_true", help="关闭今日幸运单品加权")
    ap.add_argument("--no-fortune", action="store_true", help="关闭运势手气加成")
    ap.add_argument("--rich", action="store_true", help="超预算也不妥协（今天就是要吃好的）")
    ap.add_argument("--store", default="")
    ap.add_argument("--be", default="")
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()

    if opts.collection:
        h = load_history()
        got = {}
        for d in h.get("draws", []):
            dist = d.get("分布")
            if dist:
                for r, n in dist.items():
                    got[r] = got.get(r, 0) + n
            else:
                r = d.get("最佳稀有度") or "N"
                got[r] = got.get(r, 0) + 1
        print("🎁 我的麦门图鉴\n")
        for name, _, icon, _ in RARITY:
            print("  %s %s：%d 次" % (icon, name, got.get(name, 0)))
        print("\n保底进度：%d/5（满 5 下一抽必出 SR+）" % min(h.get("pity", 0), 5))
        print("累计抽取：%d 次" % len(h.get("draws", [])))
        return

    prefs = common.load_preferences()
    avoid = list(prefs.get("avoid") or []) + list(prefs.get("dislike") or [])
    budget = float(prefs.get("box_budget") or prefs.get("budget") or 40)
    mode = opts.mode or str(prefs.get("box_mode") or "正常")
    if mode not in MODES:
        mode = "正常"
    opts.mode = mode
    lucky_on = prefs.get("lucky_boost") is not False and not opts.no_lucky
    fortune_on = prefs.get("fortune_boost") is not False and not opts.no_fortune
    today = date.today()
    seed = opts.seed if opts.seed is not None else int(today.strftime("%Y%m%d"))
    rng = random.Random(seed)
    cfg = MODES[mode]

    raw_menu = call_tool("query-meals", common.store_args(opts.store, opts.be))
    menu = common.parse_menu(raw_menu)          # 统一成 [{分类, 名称, 价格(元), ...}]
    try:
        nut_list = common.parse_nutrition(call_tool("list-nutrition-foods", {}))
    except RuntimeError:
        nut_list = []
    if not menu:
        print(json.dumps({"错误": "没拉到菜单，检查门店参数或 Token"}, ensure_ascii=False))
        sys.exit(1)

    pool = build_pool(menu, nut_list, cfg["groups"], avoid)
    if not pool:
        print(json.dumps({"错误": "菜单里没匹配到可抽的餐品（可能忌口太严或分类名不同）"}, ensure_ascii=False))
        sys.exit(1)

    # 今日运势 → 手气加成（compute 有当日缓存，与 fortune.py 同跑一天只拉一次 MCP）
    fort = None
    try:
        fort = fortune.compute(nut_list=nut_list)  # 有当日缓存，重复调用几乎零成本
    except RuntimeError:
        fort = None
    stars = int(fort.get("指数", 3)) if fort else 3
    boost = LUCK_BOOST.get(stars, (1.0, 1.0)) if (fort and fortune_on) else (1.0, 1.0)
    lucky = (fort or {}).get("今日幸运单品") or fortune.pick_lucky(nut_list, avoid, random.Random(seed))

    history = load_history()
    pity = history.get("pity", 0)
    cards = None
    if not opts.ten:
        # 单抽：抽出能吃的一套
        picks, kcal_total = draw_set(pool, rng, cfg["groups"], lucky, not lucky_on,
                                    pity >= 5, cfg["kcap"], boost)
    else:
        # 十连：抽 10 张卡（单品最多重复 2 次），保底至少一张 SR+
        cards, used = [], {}
        for _ in range(10):
            forced = pity >= 5
            pick = draw_once(pool, rng, lucky, not lucky_on, forced,
                             exclude=[k for k, v in used.items() if v >= 2], boost=boost)
            if not pick:
                break
            cards.append(pick)
            used[pick["名称"]] = used.get(pick["名称"], 0) + 1
            pity = 0 if pick["稀有度"] in ("SSR", "SR") else pity + 1
        if not any(c["稀有度"] in ("SSR", "SR") for c in cards):  # 十连保底
            top = [c for c in pool if c["稀有度"] in ("SSR", "SR")] or pool
            cards[-1] = rng.choice(top)
            pity = 0
        picks = best_combo(cards, cfg["groups"])  # 从 10 张卡里挑出能吃的一套
        kcal_total = sum(p["热量"] for p in picks)

    # 预算护栏：抽贵了就让命运向钱包低头（同组换便宜的，--rich 可拒绝妥协）
    downgraded, origin = False, None
    if picks and not opts.rich and sum(p["价格"] for p in picks) > budget:
        origin = {"合计": round(sum(p["价格"] for p in picks), 2),
                  "明细": [p["名称"] for p in picks]}
        top_i = max(range(len(picks)),
                    key=lambda i: (order.index(picks[i]["稀有度"]), picks[i]["价格"]))
        cheaper = fit_budget(pool, picks, budget, cfg["groups"], keep=(top_i,))
        if sum(c["价格"] for c in cheaper) < sum(p["价格"] for p in picks):
            picks, downgraded = cheaper, True
    spent = sum(p["价格"] for p in picks)
    kcal_total = sum(p["热量"] for p in picks)
    best = max((p["稀有度"] for p in picks), key=lambda r: order.index(r)) if picks else "N"

    dist = {}
    for c in (cards or picks):
        dist[c["稀有度"]] = dist.get(c["稀有度"], 0) + 1
    history.setdefault("draws", []).append({
        "日期": today.isoformat(), "模式": opts.mode, "种子": seed, "运势": stars,
        "最佳稀有度": best, "分布": dist, "件数": len(picks), "合计": round(spent, 2)})
    history["pity"] = pity
    history["draws"] = history["draws"][-200:]
    save_history(history)

    if opts.json:
        print(json.dumps({"模式": opts.mode, "种子": seed, "运势指数": stars,
                          "手气加成": {"SSR": boost[0], "SR": boost[1]},
                          "幸运单品": lucky, "十连卡池": cards, "推荐一套": picks,
                          "合计": round(spent, 2), "热量": kcal_total, "最佳稀有度": best},
                         ensure_ascii=False, indent=2))
        return

    title = "🎁 麦麦点餐盲盒 · %s" % ("十连" if opts.ten else "今日一抽")
    print("%s（%s模式｜种子 %d，同一天结果一致）\n" % (title, opts.mode, seed))
    if fort:
        print("🔮 今日运势 %s（%.1f/5）→ 手气加成 SSR×%.1f SR×%.1f%s"
              % (fort.get("麦门指数", "★★★☆☆"), fort.get("指数分", 0),
                 boost[0], boost[1], "（联动已关闭）" if not fortune_on else ""))
    print("🍀 幸运单品 %s（权重 ×4%s）\n" % (lucky, "，已关闭" if not lucky_on else ""))
    if cards:
        print("十连战果：")
        for i, c in enumerate(cards, 1):
            print("  %2d. %s %-3s %s  ¥%.2f" % (i, meta(c["稀有度"])[2], c["稀有度"], c["名称"], c["价格"]))
        print("\n推荐下单的一套：")
    for p in picks:
        icon = meta(p["稀有度"])[2]
        print("  %s %-3s %s  ¥%.2f  %s  %s"
              % (icon, p["稀有度"], p["名称"], p["价格"],
                 ("%d kcal" % p["热量"]) if p["热量"] else "热量 —",
                 ("蛋白 %sg" % p["蛋白质"]) if p["蛋白质"] else "蛋白 —"))
    print("\n合计 ¥%.2f｜%d kcal｜最佳 %s %s" % (spent, kcal_total, meta(best)[2], best))
    if downgraded:
        print("预算 ¥%.0f：原抽 ¥%.2f（%s）超了 → 保住最稀有的一件，降到 ¥%.2f%s"
              % (budget, origin["合计"], "/".join(origin["明细"]), spent,
                 "，仍超 —— 加 --rich 就吃它" if spent > budget else " ✅"))
    elif spent > budget:
        print("预算 ¥%.0f：⚠️ 超了 —— %s" % (budget, "--rich 已开启，今天就是要吃好的"
                                          if opts.rich else "换个种子试试"))
    else:
        print("预算 ¥%.0f：✅ 没超" % budget)
    print("保底进度：%d/5（满 5 下一抽必出 SR+）" % min(pity, 5))
    if fort:
        print("\n📜 今日麦门签：%s" % fort.get("今日签", ""))
        print("💡 %s" % LUCK_HINT.get(stars, ""))
    print("\n换一抽：--seed %d ｜ 看图鉴：--collection ｜ 看运势：fortune.py" % (seed + 1))


if __name__ == "__main__":
    main()
