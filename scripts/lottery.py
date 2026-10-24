#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎡 抽奖军师：查看积分抽奖活动、奖品池与消耗规则，查我的奖品；抽奖必须显式确认。

用法:
    python3 lottery.py                 # 看活动信息 + 奖品池 + 我的积分 + 我的奖品
    python3 lottery.py --my            # 只看我中过的奖品
    python3 lottery.py --draw 1        # 抽 1 次（脚本会再次跟你确认；确认后加 --confirm）
    python3 lottery.py --draw 1 --confirm

安全: 抽奖会真实消耗积分/次数，默认只查询不抽取；--draw 必须配合 --confirm 才执行。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402


def field(d, keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return default


def luck_level(prizes):
    """按奖品池大小给个趣味「欧气值」，纯娱乐，不影响实际抽奖。"""
    n = len(prizes) if isinstance(prizes, list) else 0
    if n >= 10:
        return "欧气值 ★★★★☆（奖品池很肥）"
    if n >= 6:
        return "欧气值 ★★★☆☆"
    if n >= 3:
        return "欧气值 ★★☆☆☆"
    return "欧气值 ★☆☆☆☆（奖少，悠着点）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draw", type=int, default=0, help="抽奖次数")
    ap.add_argument("--confirm", action="store_true", help="确认真的要抽（会消耗积分）")
    ap.add_argument("--my", action="store_true", help="只看我的奖品")
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()

    if opts.my:
        prizes = call_tool("query-my-prizes", {})
        if opts.json:
            print(json.dumps(common.redact(json.dumps(prizes, ensure_ascii=False)), ensure_ascii=False, indent=2))
        else:
            print("🎁 我的奖品记录\n")
            print(common.redact(json.dumps(prizes, ensure_ascii=False, indent=2))[:1500])
        return

    info = call_tool("query-lottery-info", {})
    lot = info.get("data", info) if isinstance(info, dict) else {}   # 官方把内容放在 data 里
    account = None
    try:
        account = common.parse_account(call_tool("query-my-account", {}))
    except RuntimeError:
        pass
    prizes = field(lot, ["prizes", "prizeList", "prizeListVO"], []) or []
    status = field(lot, ["activityStatusText", "status", "activityStatus", "state"], "未知")
    name = field(lot, ["activityName", "name"], "")
    if name:
        status = "%s · %s" % (status, name)
    rule = field(lot, ["rule", "consumeRule", "costDesc", "drawTypeText"], "见活动说明")
    draw_point = field(lot, ["drawPoint"], "")
    if draw_point:
        rule = "%s（单次消耗 %s 积分）" % (rule, draw_point)
    points = (account or {}).get("availablePoints")

    if opts.draw and not opts.confirm:
        print(json.dumps({
            "⚠️ 未执行": "抽奖会消耗积分/次数，请确认后加 --confirm",
            "命令": "python3 lottery.py --draw %d --confirm" % opts.draw,
            "当前活动状态": status, "消耗规则": rule,
        }, ensure_ascii=False, indent=2))
        return

    result = None
    if opts.draw and opts.confirm:
        result = call_tool("draw-lottery", {"count": opts.draw})

    if opts.json:
        print(json.dumps({"活动状态": status, "消耗规则": rule, "奖品池": prizes,
                          "我的积分": points, "抽奖结果": result}, ensure_ascii=False, indent=2))
        return

    print("🎡 麦门抽奖中心\n")
    print("活动状态：%s" % status)
    print("消耗规则：%s" % rule)
    print("我的可用积分：%s" % (points if points is not None else "查询失败"))
    print(luck_level(prizes))
    if isinstance(prizes, list) and prizes:
        print("\n奖品池：")
        for i, p in enumerate(prizes[:12], 1):
            name = field(p, ["prizeName", "name", "title"], "未知奖品")
            level = field(p, ["level", "grade", "prizeLevel"], "")
            print("  %d. %s%s" % (i, name, ("（%s）" % level) if level else ""))
    if result is not None:
        print("\n🎰 抽奖结果：")
        print(common.redact(json.dumps(result, ensure_ascii=False, indent=2))[:800])
        print("\n用 python3 lottery.py --my 查看全部中奖记录")


if __name__ == "__main__":
    main()
