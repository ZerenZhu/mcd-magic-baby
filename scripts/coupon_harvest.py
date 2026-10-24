#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""省钱军师·领券模块：一键领麦麦省全量券，并汇总我的可用券（按到期日排序）。

用法:
    python3 coupon_harvest.py            # 人话输出
    python3 coupon_harvest.py --json     # 机器可读
    python3 coupon_harvest.py --no-claim # 只查询，不自动领取
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402


def pick(c, keys):
    for k in keys:
        if c.get(k) not in (None, ""):
            return c[k]
    return None


def normalize(c):
    return {
        "名称": pick(c, ["couponName", "name", "title"]) or "未命名券",
        "优惠": pick(c, ["discountAmount", "amount", "discount"]),
        "门槛": pick(c, ["useCondition", "condition", "minAmount"]),
        "到期": pick(c, ["validEndTime", "expireTime", "endTime"]) or "9999",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-claim", action="store_true", help="不自动领券，只查询")
    opts = ap.parse_args()

    errors, claimed = [], None
    if not opts.no_claim:
        try:
            claimed = call_tool("auto-bind-coupons", {})
        except RuntimeError as e:
            errors.append("auto-bind-coupons: %s" % common.redact(str(e))[:200])

    mine = []
    try:
        # 官方工具名是 query-my-coupons（返回 Markdown），走统一解析层
        r = call_tool("query-my-coupons", {"page": "1", "pageSize": "200"})
        raw_list = common.parse_coupons(r)
        mine = sorted([normalize(c) for c in raw_list], key=lambda x: str(x["到期"]))
    except RuntimeError as e:
        errors.append("query-my-coupons: %s" % common.redact(str(e))[:200])

    if opts.json:
        print(json.dumps({"已领": claimed, "我的券": mine, "错误": errors}, ensure_ascii=False, indent=2))
        return
    print("🍟 可用优惠券 %d 张（按到期日排序）\n" % len(mine))
    for i, c in enumerate(mine, 1):
        disc = str(c["优惠"] or "").strip()
        if disc.isdigit():          # 分 → 元
            disc = "优惠 ¥%.2f" % (float(disc) / 100)
        extra = " | %s" % disc if disc else ""
        print("%d. %s | 到期 %s%s" % (i, c["名称"], c["到期"], extra))
    if errors:
        print("\n⚠️  部分步骤失败: %s" % "；".join(errors))
    print("\n下一步：查菜单(query-meals) → 带券算价(calculate-price) → 你确认后再下单")


if __name__ == "__main__":
    main()
