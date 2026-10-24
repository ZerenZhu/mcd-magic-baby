#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎉 派对军师：麦当劳派对/品鉴会的引导式预约。

官方真实流程（工具名与参数已按 tools/list 的 schema 校正）：
    spuId（来自商城商品）→ 城市(code) → 门店(storeCode) → 日期(dateStr) → 场次(id) → 下单

用法（逐级填参数，每跑一步自动打印下一步候选）:
    python3 party_book.py                                   # 先找派对类商品 → 拿到 spuId
    python3 party_book.py --spu 123                         # 第 1 步：可参与城市
    python3 party_book.py --spu 123 --city 深圳              # 第 2 步：该城市门店
    python3 party_book.py --spu 123 --city 深圳 --store 1990518   # 第 3 步：可预约日期
    python3 party_book.py --spu 123 --city 深圳 --store 1990518 --date 2026-11-01  # 第 4 步：场次
    ... --session 3 --count 6 --confirm                     # 最后一步：创建订单（必须 --confirm）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402


def body_of(data):
    """官方返回 {success,code,data}；城市接口返回 data[] 数组。"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        d = data.get("data", data)
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ("cities", "stores", "dates", "sessions", "list", "items"):
                if isinstance(d.get(k), list):
                    return d[k]
            return [d]
    return []


def field(d, keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return default


def find_spu():
    """派对预约的第一步是拿到 spuId：从积分商城商品里找「派对/品鉴」类。"""
    try:
        goods = call_tool("mall-points-products", {})
    except RuntimeError as e:
        print("⚠️ 查询商城商品失败：%s" % common.redact(str(e))[:200])
        return []
    rows = body_of(goods)
    hits = [g for g in rows if any(k in json.dumps(g, ensure_ascii=False)
                                   for k in ("派对", "品鉴", "生日", "Party"))]
    return hits or rows


def goods_line(g):
    """商城商品展示：品鉴会/派对类商品字段为 spuName / catName / price / point。"""
    name = field(g, ["spuName", "name", "productName", "title"], "?")
    cat = field(g, ["catName", "categoryName"], "")
    price = field(g, ["price"], "")
    point = field(g, ["point"], "")
    tail = []
    if cat:
        tail.append(cat)
    if price not in (None, "", "0"):
        tail.append("¥%s" % price)
    if point not in (None, "", "0"):
        tail.append("%s 积分" % point)
    return "%s%s" % (name, ("（%s）" % "｜".join(tail)) if tail else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spu", default="", help="派对商品 spuId（第 0 步不带参数时会帮你找）")
    ap.add_argument("--city", default="", help="城市 code（第 1 步返回的 code）")
    ap.add_argument("--store", default="", help="门店 storeCode")
    ap.add_argument("--date", default="", help="预约日期 YYYY-MM-DD")
    ap.add_argument("--session", default="", help="场次 id")
    ap.add_argument("--count", type=int, default=1, help="预约人数/份数")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()

    if not opts.spu:
        hits = find_spu()
        if opts.json:
            print(json.dumps({"候选派对商品": hits}, ensure_ascii=False, indent=2))
            return
        print("🎉 派对预约 · 第 0 步：选一个派对商品（拿到 spuId）\n")
        if not hits:
            print("（没查到派对类商品，可直接用 --spu <spuId> 指定）")
            return
        for i, g in enumerate(hits[:20], 1):
            print("  %2d. %s  [spuId=%s]" % (i, goods_line(g),
                                             field(g, ["spuId", "id", "productId"], "?")))
        print("\n下一步：python3 party_book.py --spu <spuId>")
        return

    spu = int(opts.spu) if str(opts.spu).isdigit() else opts.spu
    if not opts.city:
        step, data = "城市", call_tool("query-party-city", {"spuId": spu})
    elif not opts.store:
        step, data = "门店", call_tool("query-party-store", {"spuId": spu, "code": opts.city})
    elif not opts.date:
        step, data = "日期", call_tool("query-party-store-date",
                                       {"spuId": spu, "storeCode": opts.store})
    elif not opts.session:
        step, data = "场次", call_tool("query-party-store-session",
                                       {"spuId": spu, "storeCode": opts.store, "dateStr": opts.date})
    else:
        if not opts.confirm:
            print(json.dumps({"⚠️ 未下单": "创建派对订单需显式确认，加 --confirm 执行",
                              "将提交": {"spuId": spu, "城市": opts.city, "门店": opts.store,
                                         "日期": opts.date, "场次": opts.session, "份数": opts.count}},
                             ensure_ascii=False, indent=2))
            return
        order = call_tool("party-order-create", {
            "code": opts.city, "spuId": spu, "storeCode": opts.store,
            "dateStr": opts.date, "id": int(opts.session), "count": opts.count})
        print(common.redact(json.dumps({"✅ 派对订单已创建": order}, ensure_ascii=False, indent=2)))
        return

    rows = body_of(data)
    if opts.json:
        print(json.dumps({"当前步骤": step, "候选": rows}, ensure_ascii=False, indent=2))
        return

    print("🎉 派对预约 · 选择%s\n" % step)
    if not rows:
        print("（接口未返回候选，原始返回：%s）" % common.redact(json.dumps(data, ensure_ascii=False))[:300])
        return
    for i, r in enumerate(rows[:30], 1):
        name = field(r, ["name", "cityName", "storeName", "date", "dateStr", "sessionName", "title"], "")
        ident = field(r, ["id", "code", "cityCode", "storeCode", "sessionId"], "")
        extra = field(r, ["leftNum", "remainNum"], "")
        print("  %2d. %s%s%s" % (i, name, ("  [id=%s]" % ident) if ident else "",
                                 ("  余位 %s" % extra) if extra not in (None, "") else ""))
    nxt = {"城市": "--city <城市code>", "门店": "--store <storeCode>",
           "日期": "--date <YYYY-MM-DD>", "场次": "--session <场次id> --count %d --confirm" % opts.count}[step]
    print("\n下一步：python3 party_book.py %s" % (
        " ".join([a for a in ["--spu %s" % opts.spu,
                              "--city %s" % opts.city if opts.city else "",
                              "--store %s" % opts.store if opts.store else "",
                              "--date %s" % opts.date if opts.date else "", nxt] if a])))


if __name__ == "__main__":
    main()
