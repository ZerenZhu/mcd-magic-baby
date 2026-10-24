#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""神奇麦麦宝贝（mcd-magic-baby）· 公共层：Token 解析、脱敏、偏好读取、运行时目录。

设计原则（安全）：
1. Token 只从环境变量 / .env / MCP 配置读取，绝不写入日志、缓存或 zip 包。
2. 所有对外输出经过 redact()，Token 明文不会出现在任何 stdout。
3. 运行时隐私数据（订单缓存、账单、自动下单锁）一律写在 skill 目录之外。
"""
import json
import os
import re

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _runtime_dir():
    """运行时目录（永远不会被打包）：Token、订单缓存、运势缓存、图鉴、账单、幂等锁。

    默认 ~/.workbuddy/mcd-magic-baby/；若旧版目录（mcd-fortune-box / mcd-strategist）
    已存在则沿用，避免老用户已有的 .env 与历史数据失效。
    """
    if os.environ.get("MCD_HOME"):
        return os.environ["MCD_HOME"]
    base = os.path.expanduser("~/.workbuddy")
    new_dir = os.path.join(base, "mcd-magic-baby")
    for old in ("mcd-fortune-box", "mcd-strategist"):   # 兼容历史目录名
        old_dir = os.path.join(base, old)
        if os.path.isdir(old_dir):
            return old_dir
    return new_dir


RUNTIME_DIR = _runtime_dir()
CACHE_PATH = os.path.join(RUNTIME_DIR, "order_cache.json")
LOCK_PATH = os.path.join(RUNTIME_DIR, "auto_order_log.json")
REPORT_DIR = os.path.join(RUNTIME_DIR, "reports")
PREF_PATH = os.path.join(SKILL_DIR, "preferences.md")

TOKEN_KEY = "MCD_MCP_TOKEN"
# Token 查找顺序（先命中者生效）
ENV_FILES = [
    os.path.join(SKILL_DIR, ".env"),                                   # 1. skill 目录（方便，但打包风险高）
    os.path.join(RUNTIME_DIR, ".env"),                                 # 2. 运行时目录（推荐）
    os.path.join(os.path.expanduser("~/.workbuddy"), ".env"),          # 3. 全局兜底
]
MCP_JSON = os.path.join(os.path.expanduser("~/.workbuddy"), "mcp.json")

_TOKEN_CACHE = {"value": None, "source": None}


# ---------- Token 解析 ----------
def _parse_dotenv(path):
    """极简 .env 解析：支持 export 前缀、引号、注释；不执行任何代码。"""
    conf = {}
    if not os.path.exists(path):
        return conf
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            line = line[7:].strip() if line.startswith("export ") else line
            k, _, v = line.partition("=")
            conf[k.strip()] = v.strip().strip("'\"")
    return conf


def _scan_mcp_json():
    """从 ~/.workbuddy/mcp.json 里找麦当劳服务的 Token（用户若配置了官方连接器）。"""
    if not os.path.exists(MCP_JSON):
        return None
    try:
        cfg = json.load(open(MCP_JSON, encoding="utf-8"))
    except (ValueError, OSError):
        return None

    def walk(node, parent):
        found = None
        if isinstance(node, dict):
            for k, v in node.items():
                if found:
                    break
                if k == TOKEN_KEY and isinstance(v, str) and v.strip():
                    found = v.strip()
                elif k.lower() == "authorization" and isinstance(v, str) and v.startswith("Bearer "):
                    if "mcd" in json.dumps(parent, ensure_ascii=False).lower():
                        found = v[7:].strip()
                else:
                    found = walk(v, node)
        elif isinstance(node, list):
            for v in node:
                found = walk(v, parent)
                if found:
                    break
        return found
    return walk(cfg, {})


def load_token():
    """返回 (token, source)；未找到返回 (None, None)。"""
    if _TOKEN_CACHE["value"]:
        return _TOKEN_CACHE["value"], _TOKEN_CACHE["source"]
    env_val = os.environ.get(TOKEN_KEY, "").strip()
    if env_val:
        _TOKEN_CACHE.update(value=env_val, source="环境变量 %s" % TOKEN_KEY)
    else:
        for p in ENV_FILES:
            v = _parse_dotenv(p).get(TOKEN_KEY, "").strip()
            if v:
                warn = "（位于可打包目录，建议改放 %s）" % os.path.join(RUNTIME_DIR, ".env") \
                    if p.startswith(SKILL_DIR) else ""
                _TOKEN_CACHE.update(value=v, source="%s%s" % (p, warn))
                break
        else:
            v = _scan_mcp_json()
            if v:
                _TOKEN_CACHE.update(value=v, source=MCP_JSON)
    return _TOKEN_CACHE["value"], _TOKEN_CACHE["source"]


def require_token():
    token, source = load_token()
    if not token:
        raise SystemExit(json.dumps({
            "error": "未找到麦当劳 MCP Token",
            "how": "运行 python3 scripts/setup_token.py --token <你的Token> "
                   "写入 %s（权限 600）" % os.path.join(RUNTIME_DIR, ".env"),
            "get_token": "登录 https://open.mcd.cn → 控制台 → 复制 MCP Token",
        }, ensure_ascii=False, indent=2))
    return token


def token_status():
    """只返回是否存在 + 脱敏指纹，绝不返回明文。"""
    token, source = load_token()
    return {"configured": bool(token), "source": source, "fingerprint": mask(token) if token else None}


# ---------- 脱敏 ----------
def mask(secret, keep=4):
    if not secret:
        return None
    s = str(secret)
    return s[:keep] + "*" * max(6, len(s) - keep * 2) + s[-keep:] if len(s) > keep * 2 else "*" * len(s)


def redact(text, secrets=None):
    """抹掉文本中可能出现的 Token / Bearer 串，用于所有对外输出。"""
    out = str(text)
    secrets = list(secrets or [])
    tok, _ = load_token()
    if tok:
        secrets.append(tok)
    for s in set(secrets):
        if s and len(s) >= 6:
            out = out.replace(s, "***REDACTED***")
    return re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{6,}", r"\1***REDACTED***", out)


def mask_address(text):
    """地址/手机类信息展示时截断。"""
    if not text:
        return None
    s = str(text)
    return s[:6] + "…" if len(s) > 8 else s


# ---------- 偏好 ----------
def load_preferences():
    """解析 preferences.md：`- key: value  # 注释`，value 支持 JSON / 布尔 / 数字。"""
    prefs = {}
    if not os.path.exists(PREF_PATH):
        return prefs
    for line in open(PREF_PATH, encoding="utf-8"):
        m = re.match(r"^-\s*([A-Za-z_][\w]*)\s*:\s*(.*)$", line.rstrip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        # 去行尾注释（忽略引号/中括号内的 #）
        val = re.sub(r"\s+#.*$", "", val) if "#" in val and "[<?'\"]" not in val[:2] else val
        val = val.rstrip()
        if val.startswith("[") and val.endswith("]"):
            try:
                val = json.loads(val)
            except ValueError:
                val = []
        elif val.lower() in ("true", "false"):
            val = val.lower() == "true"
        elif re.fullmatch(r"-?\d+", val):
            # 门店编码/地址 ID 这类长数字必须保持整数精度，绝不能走 float
            val = int(val)
        elif re.fullmatch(r"-?\d+\.\d+", val):
            val = float(val)
        prefs[key] = val
    return prefs


def store_args(store="", be="", order_type=2, be_type=2):
    """构造门店参数。

    query-meals 必传 storeCode / orderType / beType，否则直接报「缺少参数」；
    外送与得来速场景还需 beCode。命令行没给门店时自动回落到 preferences.md 的默认门店。
      orderType: 1-到店（自取+得来速）  2-外送（麦乐送+团餐）
      beType:    1-到店取餐  2-麦乐送到家  5-得来速(DT)  6-企业团餐
    """
    prefs = load_preferences() if not (store and be) else {}

    def norm(v):  # 兼容历史配置里可能存在的 1990518.0 这类浮点写法
        if v is None:
            return ""
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return str(v).strip()

    store = norm(store or prefs.get("storeCode"))
    be = norm(be or prefs.get("beCode"))
    if not store:
        return {}
    args = {"storeCode": store, "orderType": int(order_type), "beType": int(be_type)}
    if be:
        args["beCode"] = be
    return args


def prefs_ready(prefs, keys):
    missing = []
    for k in keys:
        v = prefs.get(k)
        if v in (None, "", [], False) and v is not False:
            missing.append(k)
    return missing


# ---------- 真实响应适配层 ----------
# 麦当劳 MCP 各工具返回格式不统一：有 JSON、有 Markdown 说明文、还有类 CSV 文本。
# 这里统一解析为脚本好用的结构，避免每个脚本各自猜字段。

def _payload(raw):
    """剥掉 {success,code,message,data} 外壳，取出真正的业务体。"""
    if isinstance(raw, dict) and "data" in raw and ("success" in raw or "code" in raw):
        return raw["data"]
    return raw


def _text_of(raw):
    d = _payload(raw)
    if isinstance(d, str):
        return d
    if isinstance(d, (dict, list)):
        return json.dumps(d, ensure_ascii=False)
    return ""


def to_yuan(v):
    """价格归一化为「元」。

    官方菜单 currentPrice / 订单 realTotalAmount 是元的字符串（"15.5"、"20.48"）；
    算价类接口习惯用「分」的整数 —— 数值型按分换算，字符串型按元处理。
    """
    if v in (None, ""):
        return 0.0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return f if isinstance(v, str) else f / 100.0


def parse_menu(raw):
    """菜单 → [{"分类","名称","编码","价格","原价","标签","图片"}]（价格单位：元）。

    兼容三种结构：
    1) 官方真实：data.categories[].meals[].code + data.meals{code: 详情}
    2) 分类树：categories[].meals[] 自带 name/price
    3) 扁平列表
    """
    body = _payload(raw)
    items = []
    if isinstance(body, dict):
        cats = body.get("categories") or []
        detail = body.get("meals") if isinstance(body.get("meals"), dict) else {}
        if cats:
            for c in cats:
                cname = str(c.get("name") or "").replace("\n", "")
                for m in c.get("meals") or []:
                    code = str(m.get("code") or "")
                    info = detail.get(code) or detail.get(str(code)) or {}
                    src = info if isinstance(info, dict) and info.get("name") else m
                    items.append({
                        "分类": cname,
                        "名称": str(src.get("name") or src.get("productName") or code),
                        "编码": code,
                        "价格": to_yuan(src.get("currentPrice") or src.get("price") or src.get("amount")),
                        "原价": to_yuan(src.get("originalPrice") or 0) if src.get("originalPrice") else 0.0,
                        "标签": src.get("tags") or m.get("tags") or [],
                        "图片": src.get("image") or "",
                    })
            if items:
                return items
    for node in (body if isinstance(body, list) else [body]):
        if not isinstance(node, dict):
            continue
        child = next((node[k] for k in ("meals", "products", "items", "children")
                      if isinstance(node.get(k), list) and node[k]), None)
        if child:
            cname = str(node.get("categoryName") or node.get("category") or "").replace("\n", "")
            for c in child:
                if isinstance(c, dict):
                    items.append({
                        "分类": cname,
                        "名称": str(c.get("name") or c.get("productName") or c.get("mealName") or ""),
                        "编码": str(c.get("code") or c.get("productId") or ""),
                        "价格": to_yuan(c.get("currentPrice") or c.get("price") or c.get("salePrice") or 0),
                        "原价": to_yuan(c.get("originalPrice") or 0) if c.get("originalPrice") else 0.0,
                        "标签": c.get("tags") or [], "图片": c.get("image") or "",
                    })
        else:
            items.append({
                "分类": str(node.get("categoryName") or node.get("category") or "").replace("\n", ""),
                "名称": str(node.get("name") or node.get("productName") or node.get("mealName") or ""),
                "编码": str(node.get("code") or node.get("productId") or ""),
                "价格": to_yuan(node.get("currentPrice") or node.get("price") or 0),
                "原价": to_yuan(node.get("originalPrice") or 0) if node.get("originalPrice") else 0.0,
                "标签": node.get("tags") or [], "图片": node.get("image") or "",
            })
    return [i for i in items if i["名称"]]


NUTRITION_COLS = {"productName": "name", "energyKcal": "energy_kcal", "energyKj": "energy_kj",
                  "protein": "protein", "fat": "fat", "carbohydrate": "carbohydrate",
                  "sodium": "sodium", "calcium": "calcium"}


def parse_nutrition(raw):
    """营养表 → [{"name","energy_kcal","protein","fat","sodium",...}]（数值已转 float）。

    官方返回的是类 CSV 文本：
        [160]{productName,nutritionDescription,energyKj,energyKcal,...}:
          猪柳麦满分,null,1288,308,16,16,24,781,213
    """
    body = _payload(raw)
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("foods", "list", "items"):
            if isinstance(body.get(k), list):
                return body[k]
    text = _text_of(raw)
    m = re.search(r"\{([^}]*)\}", text)
    if not m:
        return []
    cols = [c.strip() for c in m.group(1).split(",")]

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "{" in line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(cols):
            continue
        head = len(parts) - (len(cols) - 1)   # 名称里可能有逗号 → 右侧对齐
        row = {}
        for c, v in zip(cols[1:], parts[head:]):
            row[c] = num(v) if c != "nutritionDescription" else (None if v == "null" else v)
        row[cols[0]] = ",".join(parts[:head])
        for src, dst in NUTRITION_COLS.items():   # 同时给一份内部统一字段名
            if src in row:
                row[dst] = row[src]
        if row.get("name"):
            rows.append(row)
    return rows


def parse_coupons(raw):
    """我的券 → [{"couponName","validEndTime","discount","tags"}]。

    官方返回 Markdown：
        # 您的优惠券列表
        共 6 张可用优惠券 | 第 1/1 页 | 每页 200 条
        ## 交行辣翅一对
        - **优惠**: ¥0 (用券价格)
        - **有效期**: 2026-10-18 00:00-2026-10-31 23:59 ...
    """
    body = _payload(raw)
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("coupons", "list", "data", "items"):
            if isinstance(body.get(k), list):
                return body[k]
    text = _text_of(raw)
    out = []
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            if cur:
                out.append(cur)
            cur = {"couponName": s[3:].strip(), "validEndTime": "", "discount": "", "tags": ""}
        elif cur and s.startswith("-"):
            body_txt = s.lstrip("-").strip()
            if "**优惠**" in body_txt:
                cur["discount"] = body_txt.split(":", 1)[-1].strip()
            elif "**有效期**" in body_txt:
                val = body_txt.split(":", 1)[-1].strip()
                m = re.search(r"(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}\s*-\s*(\d{4}-\d{2}-\d{2})", val)
                cur["validEndTime"] = m.group(2) if m else val[:10]
            elif "**标签**" in body_txt:
                cur["tags"] = body_txt.split(":", 1)[-1].strip()
    if cur:
        out.append(cur)
    return out


def parse_activities(raw):
    """活动日历 → [{"name","date"}]。官方返回 Markdown（#### 日期 + **活动标题**：xxx）。"""
    body = _payload(raw)
    if isinstance(body, list):
        return [a for a in body if isinstance(a, dict)]
    if isinstance(body, dict):
        for k in ("activities", "list", "data"):
            if isinstance(body.get(k), list):
                return [a for a in body[k] if isinstance(a, dict)]
    text = _text_of(raw)
    out, date = [], ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("####"):
            date = s.lstrip("#").strip()
        elif s.startswith("-") and "**活动标题**" in s:
            out.append({"name": s.split("：", 1)[-1].split(":", 1)[-1].strip(), "date": date})
    return out


def parse_account(raw):
    """积分账户 → {"availablePoints": float, "accumulativePoints": ..., "expiringPoints": ...}。

    官方字段是单数形式 availablePoint（字符串），这里统一成脚本使用的复数名。
    """
    body = _payload(raw)
    if not isinstance(body, dict):
        return {}
    for k in ("data", "account"):
        if isinstance(body.get(k), dict):
            body = body[k]
            break

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    return {
        "availablePoints": num(body.get("availablePoint") or body.get("availablePoints")
                               or body.get("points") or 0),
        "accumulativePoints": num(body.get("accumulativePoint") or body.get("accumulativePoints") or 0),
        "expiringPoints": num(body.get("currentMouthExpirePoint")
                              or body.get("expiringPoints") or body.get("expirePoint") or 0),
        "currency": body.get("currency") or "积分",
        "raw": body,
    }


# ---------- 运行时目录 ----------
def ensure_runtime_dir():
    os.makedirs(REPORT_DIR, exist_ok=True)
    return RUNTIME_DIR


def load_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return default


def save_json(path, data, mode=0o600):
    ensure_runtime_dir()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def emit(data, secrets=None):
    print(redact(json.dumps(data, ensure_ascii=False, indent=2), secrets))
