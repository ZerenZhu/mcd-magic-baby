#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""👥 团餐军师：把群里乱糟糟的接龙变成一张可下单的清单，并算出每人该付多少。

输入格式（每行一人，支持 x1 / *2 / 份 / 中文数字）:
    张三: 巨无霸x1, 中薯条
    李四: 板烧鸡腿堡*2、零度可乐x1
    王五 麦辣鸡翅 两份

用法:
    python3 group_order.py --file 接龙.txt                 # 从文件读
    echo "张三: 巨无霸x1" | python3 group_order.py         # 从标准输入读
    python3 group_order.py --file 接龙.txt --store X --be Y --assistance
                                                          # 指定门店并查询企业团餐助餐服务
输出: 汇总清单（可直接用于下单）+ 人均 AA 金额；**不会自动下单**。
"""
import argparse
import json
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from mcp_client import call_tool  # noqa: E402

CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
SEP = re.compile(r"[,，、;；\s]+")


def parse_qty(token):
    """从「巨无霸x2」「可乐两份」里拆出 (商品名, 数量)。"""
    m = re.search(r"[xX*×]\s*(\d+)\s*$", token)
    if m:
        return token[:m.start()].strip(), int(m.group(1))
    m = re.search(r"(\d+)\s*(份|个|杯|盒|块)$", token)
    if m:
        return token[:m.start()].strip(), int(m.group(1))
    m = re.search(r"([一二两三四五六七八九十])\s*(份|个|杯|盒|块)$", token)
    if m:
        return token[:m.start()].strip(), CN_NUM.get(m.group(1), 1)
    return token.strip(), 1


def parse_text(text):
    people = OrderedDict()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(.{1,12}?)\s*[:：]\s*(.+)$", line)
        if m:
            who, rest = m.group(1).strip(), m.group(2)
        else:
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            who, rest = parts[0], parts[1]
        items = []
        for token in SEP.split(rest):
            token = token.strip()
            if not token:
                continue
            name, qty = parse_qty(token)
            if not name and items and re.fullmatch(r"[一二两三四五六七八九十\d]+\s*(份|个|杯|盒|块)", token):
                items[-1]["数量"] = qty  # 形如「麦辣鸡翅 两份」的独立数量词，归属上一件
                continue
            if name:
                items.append({"名称": name, "数量": qty})
        if items:
            people.setdefault(who, []).extend(items)
    return people


def load_menu(store, be):
    return common.parse_menu(call_tool("query-meals", common.store_args(store, be)))


def match_code(menu, name):
    """模糊匹配商品编码与价格（菜单已由 common.parse_menu 统一，价格单位为元）。

    接龙里写「巨无霸」通常指单品而非「巨无霸四件套」，因此：
    精确同名 > 名字更短（更像单品） > 价格更低。
    """
    cands = []
    for m in menu:
        mname = str(m.get("名称") or "")
        if mname and (mname == name or name in mname or mname in name):
            cands.append((mname, m))
    if not cands:
        return None
    cands.sort(key=lambda x: (x[0] != name, len(x[0]), float(x[1].get("价格") or 0)))
    mname, m = cands[0]
    return {"名称": mname, "编码": m.get("编码", ""),
            "单价": round(float(m.get("价格") or 0), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--store", default="")
    ap.add_argument("--be", default="")
    ap.add_argument("--fee", type=float, default=0, help="配送费（元），按人头均摊")
    ap.add_argument("--assistance", action="store_true", help="查询企业团餐助餐服务")
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()

    text = open(opts.file, encoding="utf-8").read() if opts.file else sys.stdin.read()
    people = parse_text(text)
    if not people:
        print(json.dumps({"错误": "没解析出任何接龙内容", "示例": "张三: 巨无霸x1, 中薯条"}, ensure_ascii=False))
        sys.exit(2)

    menu = load_menu(opts.store, opts.be)
    total = 0.0
    agg = OrderedDict()
    per_person = OrderedDict()
    for who, items in people.items():
        rows, subtotal = [], 0.0
        for it in items:
            hit = match_code(menu, it["名称"])
            price = hit["单价"] if hit else 0.0
            line = price * it["数量"]
            subtotal += line
            rows.append({"名称": it["名称"], "数量": it["数量"],
                         "单价": price or None, "小计": round(line, 2),
                         "匹配到菜单": bool(hit)})
            agg[it["名称"]] = agg.get(it["名称"], 0) + it["数量"]
        per_person[who] = {"明细": rows, "小计": round(subtotal, 2)}
        total += subtotal

    headcount = len(people)
    share_fee = round(opts.fee / headcount, 2) if headcount else 0
    for who in per_person:
        per_person[who]["应付"] = round(per_person[who]["小计"] + share_fee, 2)

    assistance = None
    if opts.assistance:
        try:
            assistance = call_tool("query-meal-assistance", common.store_args(opts.store, opts.be))
        except RuntimeError as e:
            assistance = {"错误": common.redact(str(e))[:200]}

    if opts.json:
        print(json.dumps({"人数": headcount, "总金额": round(total + opts.fee, 2), "配送费": opts.fee,
                          "每人": per_person, "汇总清单": agg, "助餐服务": assistance},
                         ensure_ascii=False, indent=2))
        return
    print("👥 团餐接龙汇总 · %d 人\n" % headcount)
    for who, d in per_person.items():
        goods = "、".join("%s×%d" % (r["名称"], r["数量"]) for r in d["明细"])
        print("  %s：%s → ¥%.2f%s" % (who, goods, d["应付"],
                                      "" if d["小计"] else "（菜单未匹配到价格，需人工核价）"))
    print("\n汇总下单清单：")
    for name, cnt in agg.items():
        print("  • %s × %d" % (name, cnt))
    print("\n合计 ¥%.2f（含配送费 ¥%.2f，每人摊 ¥%.2f）" % (total + opts.fee, opts.fee, share_fee))
    if assistance:
        print("\n企业团餐助餐服务：%s" % json.dumps(assistance, ensure_ascii=False)[:300])
    print("\n下一步：用汇总清单走 calculate-price 算准确总价 → 大家确认 → 再 create-order（脚本绝不自动下单）")


if __name__ == "__main__":
    main()
