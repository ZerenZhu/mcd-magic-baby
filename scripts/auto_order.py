#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""懒人军师：按 preferences.md 的默认搭配自动下单（供定时自动化调用）。

四道护栏:
  1. auto_order_enabled 必须为 true；
  2. 必须配置默认地址(addressId/storeCode/beCode)与 default_meal；
  3. 算价超 budget_max(元) 直接跳过；
  4. 幂等：同一天只允许成功下单一次（--force 可强制），避免定时任务重跑重复扣款。

用法:
    python3 auto_order.py            # 正式下单
    python3 auto_order.py --dry-run  # 只算价不下单（建议首次这样跑）
    python3 auto_order.py --force    # 忽略当天幂等锁
"""
import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402

TODAY = date.today().isoformat()


def read_lock():
    return common.load_json(common.LOCK_PATH, {"history": {}})


def write_lock(rec):
    common.save_json(common.LOCK_PATH, rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只算价不下单")
    ap.add_argument("--force", action="store_true", help="忽略当天幂等锁")
    opts = ap.parse_args()

    prefs = common.load_preferences()
    if not prefs.get("auto_order_enabled"):
        print(json.dumps({"跳过": "auto_order_enabled 未开启", "提示": "在 preferences.md 改为 true 才允许自动下单"},
                         ensure_ascii=False))
        sys.exit(2)
    missing = common.prefs_ready(prefs, ["addressId", "storeCode", "beCode", "default_meal"])
    if missing:
        print(json.dumps({"跳过": "偏好缺失", "缺失字段": missing}, ensure_ascii=False))
        sys.exit(2)

    lock = read_lock()
    if lock.get("history", {}).get(TODAY) and not opts.force:
        print(json.dumps({"跳过": "今天(%s)已下单过，幂等保护触发" % TODAY,
                          "上次记录": lock["history"][TODAY],
                          "如需重下": "python3 auto_order.py --force"}, ensure_ascii=False))
        sys.exit(0)

    store, be, addr = prefs["storeCode"], prefs["beCode"], prefs["addressId"]
    meal = prefs["default_meal"]
    meal = meal if isinstance(meal, list) else [meal]
    budget_max = float(prefs.get("budget_max") or 50)

    price = call_tool("calculate-price", {"storeCode": store, "beCode": be, "items": meal})
    payable = None
    for key in ("payAmount", "payableAmount", "totalPrice", "total"):
        if isinstance(price, dict) and price.get(key) is not None:
            payable = float(price[key]) / 100.0
            break
    if payable is None:
        print(json.dumps({"错误": "无法从算价结果识别应付金额，保守中止", "原始返回摘要": str(price)[:300]},
                         ensure_ascii=False))
        sys.exit(1)
    if payable > budget_max:
        print(json.dumps({"跳过": "应付 ¥%.2f 超过预算上限 ¥%.2f" % (payable, budget_max)}, ensure_ascii=False))
        sys.exit(3)

    if opts.dry_run:
        print(json.dumps({"dry_run": True, "应付": "¥%.2f" % payable, "明细": meal,
                          "收货地址ID": addr}, ensure_ascii=False, indent=2))
        return

    order = call_tool("create-order", {
        "storeCode": store, "beCode": be, "addressId": addr, "items": meal,
        "remark": prefs.get("remark") or "",
    })
    oid = None
    if isinstance(order, dict):
        oid = order.get("orderId") or order.get("orderNo")
    lock.setdefault("history", {})[TODAY] = {"time": TODAY, "pay_yuan": payable, "orderId": oid}
    write_lock(lock)
    print(common.redact(json.dumps({
        "✅ 已下单": {"应付": "¥%.2f" % payable, "订单号": oid},
        "支付链接": (order or {}).get("payUrl") if isinstance(order, dict) else None,
        "提示": "请把支付链接发给用户完成付款（脚本不代付）",
    }, ensure_ascii=False, indent=2)))


if __name__ == "__main__":
    main()
