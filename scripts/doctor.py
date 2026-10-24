#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键自检：Token 是否配置、能否连通 MCP、偏好是否填全。首次使用先跑这个。

用法:
    python3 doctor.py [--fix-hint]

退出码: 0 全部就绪 / 1 有未通过项
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

REQUIRED_PREFS = ["addressId", "storeCode", "beCode"]        # 下单必需
OPTIONAL_PREFS = ["budget_max", "avoid", "default_meal"]     # 强烈建议


def check_token():
    st = common.token_status()
    return {
        "项": "MCP Token",
        "状态": "✅" if st["configured"] else "❌",
        "说明": st["source"] or "未配置 → python3 scripts/setup_token.py --token <TOKEN>",
        "脱敏": st["fingerprint"],
    }


def check_connection():
    """用连接器的 --doctor 做连通性验证（子进程输出已脱敏）。"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_client.py")
    try:
        out = subprocess.run([sys.executable, script, "--doctor"], capture_output=True, text=True, timeout=60)
        data = json.loads(out.stdout or "{}")
        ok = bool(data.get("ok"))
        detail = " | ".join("%s %s%s" % (s["step"], s["status"],
                                         ("：%s" % s["detail"][:160]) if s["status"] != "ok" else "")
                            for s in data.get("steps", []))
        return {"项": "MCP 连通性", "状态": "✅" if ok else "❌", "说明": common.redact(detail) or "无输出"}
    except Exception as e:
        return {"项": "MCP 连通性", "状态": "❌", "说明": common.redact(str(e))[:200]}


def check_prefs():
    prefs = common.load_preferences()
    missing = common.prefs_ready(prefs, REQUIRED_PREFS)
    weak = common.prefs_ready(prefs, OPTIONAL_PREFS)
    return {
        "项": "偏好配置", "状态": "✅" if not missing else "⚠️",
        "说明": ("缺失下单必需字段: %s → 用 delivery-query-addresses 查询后回填 preferences.md" % missing)
                if missing else ("建议补全: %s" % weak if weak else "完整"),
    }


def main():
    checks = [check_token(), check_connection(), check_prefs()]
    ok = all(c["状态"] == "✅" for c in checks[:2])
    print(json.dumps({
        "神奇麦麦宝贝 · 环境自检": "全部就绪 🍟" if ok else "有项未通过，按下方说明处理",
        "运行时数据目录": common.RUNTIME_DIR,
        "检查结果": checks,
        "下一步": "省钱军师: coupon_harvest.py → 查看可领券；减脂军师: recommend.py --kcal <预算>",
    }, ensure_ascii=False, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
