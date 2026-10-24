#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔮 麦麦运势分析 —— 神奇麦麦宝贝的第一主轴。

用真实数据算今日「麦门指数」，给出本命餐品、幸运单品、宜忌、吉时与财气，
并把结果当日缓存，供点餐盲盒作为「今日手气」加成使用。

用法（「麦麦启动」开机口令即调本脚本）:
    python3 fortune.py                     # 今日运势（同一天结果稳定）
    python3 fortune.py --json              # 机器可读
    python3 fortune.py --lucky-only        # 只输出今日幸运单品（供盲盒加权调用）
    python3 fortune.py --refresh           # 忽略当日缓存重算

数据源（全部失败也不崩，会降级为只用本地缓存）:
    now-time-info(时间) + query-my-coupons(财气) + campaign-calendar(活动)
    + query-my-account(积分) + list-nutrition-foods(幸运单品池) + 本地订单缓存(本命餐品)

算法: 指数 = 券(最多2★) + 活动(1★) + 积分(1★) + 时段(0.5~1★) + 日期玄学(±)，同一天同一结果。
"""
import argparse
import json
import os
import random
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402

WEEKDAY = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
LUCKY_WORDS = ["大吉", "中吉", "小吉", "末吉", "平", "吉"]
宜忌库 = [
    ("宜带券下单，能省则省", "忌临时加购薯条，钠容易爆表"),
    ("宜试试新品，今天运气正盛", "忌重复昨天的搭配，会腻"),
    ("宜点本命餐品，稳定发挥", "忌空腹喝冰可乐"),
    ("宜加份玉米杯，平衡一下", "忌为了凑满减多点一份"),
    ("宜分享给同事，团单更划算", "忌临近打烊才下单"),
    ("宜慢慢吃，今天不赶时间", "忌连续第三天吃炸物"),
]
CACHE_PATH = os.path.join(common.RUNTIME_DIR, "fortune_cache.json")


def safe(tool, args=None):
    try:
        return call_tool(tool, args or {})
    except RuntimeError:
        return None


def field(d, keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return default


def as_list(d, keys=("coupons", "activities", "foods", "data", "list")):
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in keys:
            if isinstance(d.get(k), list):
                return d[k]
    return []


def read_order_cache():
    cache = common.load_json(common.CACHE_PATH, {"orders": {}})
    orders = list(cache.get("orders", {}).values())
    counter = {}
    for o in orders:
        for name in o.get("items", []):
            counter[name] = counter.get(name, 0) + 1
    return orders, counter


def hour_slot(now):
    h = now.hour
    if 6 <= h < 10:
        return "早餐时段", "吉时 07:30-09:30，早餐卡最划算"
    if 10 <= h < 11:
        return "早午餐缝隙", "吉时 11:00 前下单，避开午高峰"
    if 11 <= h < 14:
        return "午市高峰", "吉时 13:00 后下单，出餐更快"
    if 14 <= h < 17:
        return "下午茶时段", "吉时 14:00-16:00，1+1 随心配常在这时候"
    if 17 <= h < 21:
        return "晚餐时段", "吉时 17:30 前下单，赶上第一波现炸"
    return "夜宵时段", "吉时 21:00 前下单，晚班门店可能售罄"


def calc_index(coupon_cnt, has_activity, points, slot_bonus, rng):
    score = 1.5                                 # 底分：人人都有基础运
    score += min(coupon_cnt, 4) * 0.375         # 券最多 +1.5★
    score += 1 if has_activity else 0           # 有活动 +1★
    score += 0.5 if (points or 0) >= 500 else 0  # 积分充足 +0.5★
    score += slot_bonus                         # 时段 0.5~1★
    score += rng.uniform(-0.5, 0.5)             # 玄学浮动
    stars = max(1, min(5, round(score)))
    return stars, round(max(0.0, min(5.0, score)), 1)


def improvement_tips(coupon_cnt, has_activity, points, slot):
    """运势是可以改的：缺哪个因子就给哪条建议（每条都对应一个真实脚本）。"""
    tips = []
    if coupon_cnt == 0:
        tips.append("去麦麦省领券 → coupon_harvest.py（最多 +1.5★）")
    elif coupon_cnt < 4:
        tips.append("再领 %d 张券还能加分" % (4 - coupon_cnt))
    if not has_activity:
        tips.append("今日无活动，用 deal_calendar.py 蹲下一个（+1★）")
    if (points or 0) < 500:
        tips.append("积分攒到 500 可 +0.5★（下单记得积分）")
    if "高峰" in slot:
        tips.append("错峰下单可 +0.5★（现在正是%s）" % slot)
    return tips


def pick_lucky(nut_list, avoid, rng, fallback=("巨无霸", "板烧鸡腿堡", "麦辣鸡翅")):
    """从营养/菜单池里挑今日幸运单品（确定性，同一天结果一致）。"""
    pool = [str(field(n, ["name", "foodName"], "")) for n in nut_list
            if field(n, ["name", "foodName"]) and not any(a in str(field(n, ["name", "foodName"], "")) for a in avoid)]
    return rng.choice(pool) if pool else rng.choice(list(fallback))


def compute(nut_list=None, use_cache=True):
    """算出今日运势。同一天结果稳定；结果当日缓存，供盲盒复用（不重复拉 MCP）。

    返回 dict。关键字段：
        指数        1~5 的数值星数（盲盒按它调稀有度权重）
        指数分      0~5 的原始分
        麦门指数    ★★★★☆ 形式
        今日幸运单品 / 本命餐品 / 宜 / 忌 / 吉时 / 财气 / 今日签
    """
    today = date.today()
    if use_cache:
        cached = common.load_json(CACHE_PATH, {})
        if cached.get("日期") == today.isoformat():
            return cached

    prefs = common.load_preferences()
    avoid = list(prefs.get("avoid") or []) + list(prefs.get("dislike") or [])
    rng = random.Random(int(today.strftime("%Y%m%d")))

    safe("now-time-info", {})
    now = datetime.now()
    weekday = WEEKDAY[now.weekday()]

    coupons = common.parse_coupons(safe("query-my-coupons", {"page": "1", "pageSize": "200"}) or [])
    urgent = 0
    for c in coupons:
        exp = str(field(c, ["validEndTime", "expireTime", "endTime"], ""))[:10]
        try:
            y, m, d = (int(x) for x in exp.split("-"))
            if 0 <= (date(y, m, d) - today).days <= 3:
                urgent += 1
        except (ValueError, TypeError):
            continue
    account = common.parse_account(safe("query-my-account", {}) or {})
    points = account.get("availablePoints", 0) or 0
    expiring = account.get("expiringPoints", 0) or 0
    acts = common.parse_activities(safe("campaign-calendar", {}) or {})
    has_activity = bool(acts)

    if nut_list is None:
        nut_list = common.parse_nutrition(safe("list-nutrition-foods", {}) or [])
    lucky_item = pick_lucky(nut_list, avoid, rng)

    orders, counter = read_order_cache()
    soulmate = max(counter, key=counter.get) if counter else None
    month_spend = round(sum(o.get("pay_yuan", 0) for o in orders
                            if str(o.get("time", "")).startswith(today.strftime("%Y-%m"))), 2)

    slot, slot_tip = hour_slot(now)
    slot_bonus = 1.0 if "高峰" not in slot else 0.5
    stars, raw = calc_index(len(coupons), has_activity, points, slot_bonus, rng)

    yi, ji = rng.choice(宜忌库)
    result = {
        "日期": today.isoformat(), "星期": weekday, "时段": slot, "吉时": slot_tip,
        "麦门指数": "★" * stars + "☆" * (5 - stars), "指数": stars, "指数分": raw,
        "本命餐品": soulmate or "还没攒够数据，多点几次就知道了",
        "今日幸运单品": lucky_item,
        "宜": yi, "忌": ji,
        "财气": {"可用券": len(coupons), "3天内到期": urgent},
        "积分": points, "本月将过期积分": expiring, "本月已消费": month_spend,
        "改运指南": improvement_tips(len(coupons), has_activity, points, slot),
        "今日签": rng.choice(LUCKY_WORDS) + " · " + rng.choice(
            ["优惠券会乖乖生效", "薯条是现炸的", "取餐柜还有空位", "这次不用排队", "套餐搭配刚好"]),
    }
    if use_cache:
        try:
            common.save_json(CACHE_PATH, result)
        except OSError:
            pass
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lucky-only", action="store_true", help="只输出今日幸运单品（供盲盒加权调用）")
    ap.add_argument("--refresh", action="store_true", help="忽略当日缓存重算")
    opts = ap.parse_args()

    result = compute(use_cache=not opts.refresh)
    lucky_item = result["今日幸运单品"]
    raw = result["指数分"]

    if opts.lucky_only:
        print(lucky_item)
        return
    if opts.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("🔮 麦麦运势 · %s %s｜%s\n" % (result["日期"], result["星期"], result["时段"]))
    print("麦门指数  %s（%.1f/5）" % (result["麦门指数"], raw))
    print("本命餐品  %s" % result["本命餐品"])
    print("幸运单品  %s  ← 今天抽盲盒更容易遇到它" % lucky_item)
    print("今日宜忌  %s｜%s" % (result["宜"], result["忌"]))
    print("吉时      %s" % result["吉时"])
    print("财气      可用券 %d 张%s" % (result["财气"]["可用券"],
                                    ("，其中 %d 张 3 天内到期，优先用掉" % result["财气"]["3天内到期"])
                                    if result["财气"]["3天内到期"] else ""))
    print("积分      %s｜本月已消费 ¥%.2f%s" % (
        result["积分"], result["本月已消费"],
        ("｜⚠️ %s 积分本月过期" % result["本月将过期积分"]) if result["本月将过期积分"] else ""))
    print("\n今日麦门签：%s" % result["今日签"])
    if result["改运指南"]:
        print("\n🪄 改运指南（运势是可以刷的）：")
        for t in result["改运指南"]:
            print("   · %s" % t)
    print("\n让命运拍板 → python3 blind_box.py（运势越好，出货越欧）")


if __name__ == "__main__":
    main()
