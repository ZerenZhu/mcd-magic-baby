#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""账单军师：生成月度账单 Markdown 报告。

用法:
    python3 monthly_report.py [YYYY-MM]   # 缺省为当前月
    python3 monthly_report.py --json      # 只输出统计 JSON

隐私: 订单明细只保留「时间/金额/商品」，地址与手机号不入缓存；
      缓存与报告都写在 skill 目录之外的运行时目录（默认 ~/.workbuddy/mcd-magic-baby/），不会被打包。
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402

RANKS = [(0, "麦门路人"), (80, "麦门常客"), (200, "麦门信徒"), (400, "麦门长老"), (800, "麦门本门")]


def fetch_month_orders(month):
    """官方历史订单工具是 order-list，返回 data.list[]。"""
    data = call_tool("order-list", {})
    if isinstance(data, list):
        rows = data
    else:
        inner = data.get("data", data) if isinstance(data, dict) else {}
        rows = next((inner[k] for k in ("list", "orders", "orderList")
                     if isinstance(inner, dict) and isinstance(inner.get(k), list)), [])
    return [o for o in rows if str(o.get("createTime") or "").startswith(month)]


def normalize(order):
    items = order.get("items") or order.get("orderProductList") or order.get("productList") or []
    names = [str(i.get("name") or i.get("productName")) for i in items
             if i.get("name") or i.get("productName")]
    pay = order.get("realTotalAmount") or order.get("payAmount") or order.get(
        "payableAmount") or order.get("totalPrice") or 0
    return {
        "id": str(order.get("orderId") or order.get("orderNo") or ""),
        "time": order.get("createTime") or order.get("orderTime") or "",
        "pay_yuan": round(common.to_yuan(pay), 2),
        "items": names,  # 只存商品名，不存地址/手机/支付流水
    }


def rank_of(yuan):
    name = RANKS[0][1]
    for th, label in RANKS:
        if yuan >= th:
            name = label
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("month", nargs="?", default=date.today().strftime("%Y-%m"))
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()
    month = opts.month

    cache = common.load_json(common.CACHE_PATH, {"orders": {}})
    try:
        raw = fetch_month_orders(month)
    except RuntimeError as e:
        print(json.dumps({"错误": common.redact(str(e)),
                          "提示": "Token 失效就跑 python3 scripts/doctor.py 自检"}, ensure_ascii=False))
        sys.exit(1)
    for o in raw:
        n = normalize(o)
        if n["id"]:
            cache["orders"][n["id"]] = n
    common.save_json(common.CACHE_PATH, cache)

    orders = sorted([o for o in cache["orders"].values() if o["time"].startswith(month)],
                    key=lambda x: x["time"])
    total = round(sum(o["pay_yuan"] for o in orders), 2)
    cnt = len(orders)
    avg = round(total / cnt, 2) if cnt else 0
    top5 = Counter(i for o in orders for i in o["items"]).most_common(5)

    if opts.json:
        print(json.dumps({"月份": month, "总花费": total, "订单数": cnt, "客单价": avg,
                          "麦门成色": rank_of(total), "Top5": top5}, ensure_ascii=False, indent=2))
        return

    lines = ["# 🍟 麦门月度账单 · %s" % month, "",
             "| 指标 | 数值 |", "|---|---|",
             "| 总花费 | ¥%.2f |" % total, "| 订单数 | %d 单 |" % cnt,
             "| 客单价 | ¥%.2f |" % avg, "| 麦门成色 | **%s** |" % rank_of(total), "",
             "## 最常点的 Top 5", ""]
    lines += ["%d. %s × %d" % (i + 1, n, c) for i, (n, c) in enumerate(top5)] or ["本月还没点过麦当劳。"]
    lines += ["", "## 订单明细", ""]
    lines += ["- %s  ¥%.2f  %s" % (o["time"] or o["id"], o["pay_yuan"], "、".join(o["items"]) or "(无明细)")
              for o in orders] or ["(空)"]

    common.ensure_runtime_dir()
    out_path = os.path.join(common.REPORT_DIR, "麦门账单_%s.md" % month)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(json.dumps({"📄 账单已生成": out_path, "总花费": "¥%.2f" % total, "订单数": cnt,
                      "麦门成色": rank_of(total)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
