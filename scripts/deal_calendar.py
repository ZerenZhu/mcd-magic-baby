#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""📅 薅羊毛日历：把活动、券到期、积分过期、抽奖次数合并成一份未来 N 天行动日历。

用法:
    python3 deal_calendar.py              # 默认未来 14 天
    python3 deal_calendar.py --days 7
    python3 deal_calendar.py --json

数据源: campaign-calendar（活动）+ query-my-coupons（券）+ query-my-account（积分）
      + query-lottery-info（抽奖次数）+ now-time-info（今天几号）
输出: 今天该薅什么的清单 + 未来日历 Markdown（写到运行时目录 reports/）
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402


def safe(tool, args=None, default=None):
    try:
        return call_tool(tool, args or {})
    except RuntimeError as e:
        return {"错误": common.redact(str(e))[:160]} if default is None else default


def as_list(d, keys=("activities", "coupons", "data", "list")):
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in keys:
            if isinstance(d.get(k), list):
                return d[k]
    return []


def field(d, keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return default


def days_left(expire):
    if not expire:
        return None
    s = str(expire)[:10]
    try:
        y, m, dd = (int(x) for x in s.split("-"))
        return (date(y, m, dd) - date.today()).days
    except (ValueError, TypeError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()

    today = date.today()
    horizon = today + timedelta(days=opts.days)
    cal = safe("campaign-calendar", {})
    coupons = common.parse_coupons(safe("query-my-coupons", {"page": "1", "pageSize": "200"}, []))
    account = common.parse_account(safe("query-my-account", {}, {}))
    lottery = safe("query-lottery-info", {})

    # 券：按到期日排序，标记临期
    urgent = []
    for c in coupons:
        name = field(c, ["couponName", "name", "title"], "未命名券")
        exp = field(c, ["validEndTime", "expireTime", "endTime"], "")
        left = days_left(exp)
        if left is not None and left <= opts.days:
            urgent.append({"券": name, "到期": str(exp)[:10], "剩余天数": left})
    urgent.sort(key=lambda x: x["剩余天数"])

    expiring_points = account.get("expiringPoints", 0)
    points = account.get("availablePoints", 0)
    # 官方抽奖信息在 data 里，状态字段是 activityStatusText，活动名是 activityName
    lot = lottery.get("data", lottery) if isinstance(lottery, dict) else {}
    lottery_status = field(lot, ["activityStatusText", "status", "activityStatus", "state"], "未知")
    lottery_name = field(lot, ["activityName", "name"], "")
    if lottery_name and lottery_status not in ("未知",):
        lottery_status = "%s · %s" % (lottery_status, lottery_name)

    acts = common.parse_activities(cal)
    upcoming = []
    for a in acts:
        start = str(field(a, ["startTime", "beginTime", "startDate"], ""))[:10]
        name = field(a, ["name", "activityName", "title"], "")
        if name and start:
            try:
                y, m, dd = (int(x) for x in start.split("-"))
                if today <= date(y, m, dd) <= horizon:
                    upcoming.append({"日期": start, "活动": name})
            except (ValueError, TypeError):
                continue

    if opts.json:
        print(json.dumps({"今天": today.isoformat(), "临期券": urgent, "即将过期积分": expiring_points,
                          "可用积分": points, "抽奖活动状态": lottery_status, "未来活动": upcoming},
                         ensure_ascii=False, indent=2))
        return

    print("📅 麦门薅羊毛日历 · 今天 %s\n" % today.isoformat())
    print("今日必做：")
    todo = False
    if urgent:
        todo = True
        for u in urgent[:5]:
            flag = "🔥 今天到期" if u["剩余天数"] <= 0 else "⏳ 还剩 %d 天" % u["剩余天数"]
            print("  • %s（%s）—— %s" % (u["券"], u["到期"], flag))
    if expiring_points:
        todo = True
        print("  • 有 %s 积分即将过期 → 去麦麦商城换掉（mall-points-products）" % expiring_points)
    if lottery_status not in ("未知", "结束", "已结束"):
        todo = True
        print("  • 抽奖活动 %s → python3 lottery.py 看看奖品池" % lottery_status)
    if not todo:
        print("  • 今天没什么羊毛，安心吃（或跑 coupon_harvest.py 领领看）")

    lines = ["# 📅 麦门薅羊毛日历 · 生成于 %s" % today.isoformat(), "",
             "| 日期 | 事项 |", "|---|---|"]
    for u in urgent:
        lines.append("| %s | 🎟️ %s 到期 |" % (u["到期"], u["券"]))
    for a in sorted(upcoming, key=lambda x: x["日期"]):
        lines.append("| %s | 🎪 %s 开始 |" % (a["日期"], a["活动"]))
    lines += ["", "可用积分：%s｜即将过期：%s" % (points, expiring_points)]

    common.ensure_runtime_dir()
    out = os.path.join(common.REPORT_DIR, "薅羊毛日历_%s.md" % today.isoformat())
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    print("\n📄 日历已生成：%s" % out)


if __name__ == "__main__":
    main()
