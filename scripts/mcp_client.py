#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦当劳中国 MCP 调用器（仅依赖标准库）。

用法:
    python3 mcp_client.py <tool_name> ['<json args>']   # 调用工具
    python3 mcp_client.py --doctor                      # 连通性自检

Token 来源（自动查找，见 common.load_token）：
    环境变量 MCD_MCP_TOKEN > skill/.env > ~/.workbuddy/mcd-magic-baby/.env（旧版 mcd-fortune-box / mcd-strategist 会自动沿用）
    > ~/.workbuddy/.env > mcp.json
输出全部经 redact() 脱敏，Token 明文不会打印。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_token, require_token, redact  # noqa: E402

# 官方地址为 https://mcp.mcd.cn（根路径）；显式设置 MCD_MCP_URL 时只用它
DEFAULT_CANDIDATES = ["https://mcp.mcd.cn", "https://mcp.mcd.cn/mcp", "https://mcp.mcd.cn/mcp/"]
PROTOCOL_VERSION = "2025-03-26"
_session_id = None
_active_url = {"v": None}


class RouteNotFound(Exception):
    """端点路径不存在，需要换候选地址重试。"""


def _candidates():
    explicit = os.environ.get("MCD_MCP_URL")
    if explicit:
        return [explicit]
    if _active_url["v"]:
        return [_active_url["v"]]
    return DEFAULT_CANDIDATES


def _check_url(url):
    if not url.lower().startswith("https://"):
        raise SystemExit("拒绝非 HTTPS 的 MCP 地址: %s" % url)
    if "mcd.cn" not in url and not os.environ.get("MCD_ALLOW_ANY_HOST"):
        print("⚠️  MCP 地址不在 mcd.cn 域内: %s（私有部署请设置 MCD_ALLOW_ANY_HOST=1）" % url, file=sys.stderr)


def _post_once(url, payload):
    global _session_id
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("Authorization", "Bearer " + require_token())
    if _session_id:
        req.add_header("Mcp-Session-Id", _session_id)
    try:
        resp = urllib.request.urlopen(req, timeout=30)  # 默认校验 TLS 证书
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            _session_id = sid
        return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = redact(e.read().decode("utf-8", "replace")[:500])
        code = e.code
        if code == 404:
            raise RouteNotFound(detail)
        if code == 429:
            # 官方限制 600 次/分钟，触发后短暂退避重试一次
            import time
            time.sleep(2)
            try:
                resp = urllib.request.urlopen(req, timeout=30)
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    _session_id = sid
                return resp.read().decode("utf-8", "replace")
            except urllib.error.HTTPError:
                raise RuntimeError("MCP 429 触发限流（600 次/分钟），请稍后重试")
        hint = "Token 无效或已过期 → 到 https://open.mcd.cn 控制台重新获取" if code in (401, 403) else None
        raise RuntimeError("MCP HTTP %s: %s%s" % (code, detail, (" | " + hint) if hint else ""))
    except urllib.error.URLError as e:
        raise RuntimeError("网络不可达: %s" % redact(str(e)))


def _post(payload):
    """按候选地址依次尝试；首个可用地址会被固定下来供后续调用复用。"""
    candidates = _candidates()
    last = None
    for i, url in enumerate(candidates):
        _check_url(url)
        try:
            body = _post_once(url, payload)
            _active_url["v"] = url
            return body
        except RouteNotFound as e:
            last = e
            if i < len(candidates) - 1:
                continue
            raise RuntimeError(
                "所有候选端点均返回 404：%s | 若控制台给了别的服务地址，用 MCD_MCP_URL 指定"
                % ", ".join(candidates))


def _init():
    _post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
        "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
        "clientInfo": {"name": "mcd-magic-baby", "version": "1.2.0"}}})
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"})


def extract_json(text):
    """把真实响应从 Markdown 说明里挖出来。

    麦当劳 MCP 的部分工具返回的是一段说明性 Markdown：
        "# API Response Information\\n...\\n## Original Response\\n\\n{...}"
    真正的业务 JSON 在 `## Original Response` 之后（有时包在 ```json 代码块里）。
    """
    if not isinstance(text, str):
        return text
    s = text.strip()
    try:
        return json.loads(s)
    except ValueError:
        pass
    m = re.search(r"##\s*Original\s*Response\s*(?:```(?:json)?\s*(.*?)```|(.*))", s, re.S | re.I)
    if m:
        blk = (m.group(1) or m.group(2) or "").strip()
        if blk:
            try:
                return json.loads(blk)
            except ValueError:
                pass
    m = re.search(r"[\{\[].*[\}\]]", s, re.S)
    if m:  # 末尾可能粘了多余文本，逐步截短再试
        blk = m.group(0)
        while blk:
            try:
                return json.loads(blk)
            except ValueError:
                i = max(blk.rfind("}"), blk.rfind("]"))
                if i <= 0:
                    break
                blk = blk[:i]
    return text


def call_tool(name, args=None):
    if _session_id is None:
        _init()
    body = _post({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": name, "arguments": args or {}}})
    if body.lstrip().startswith("{"):
        resp = json.loads(body)
    else:  # SSE 兼容
        resp = next((json.loads(l[5:].strip()) for l in body.splitlines() if l.startswith("data:")), {})
    if resp.get("error"):
        raise RuntimeError("MCP 错误: %s" % redact(json.dumps(resp["error"], ensure_ascii=False)))
    result = resp.get("result", {})
    if result.get("isError"):
        raise RuntimeError("工具执行失败: %s" % redact(json.dumps(result.get("content"), ensure_ascii=False)))
    texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
    raw = redact("\n".join(texts))
    data = extract_json(raw)
    # 业务层失败（如缺少必填参数）要显式抛错，避免脚本把错误体当数据处理
    if isinstance(data, dict) and data.get("success") is False:
        raise RuntimeError("工具 %s 返回失败：%s" % (
            name, redact(str(data.get("message") or data.get("code") or ""))))
    return data


def doctor():
    """连通性自检：Token 状态 → initialize → now-time-info。"""
    steps = []
    tok = None
    try:
        tok = require_token()
        from common import token_status
        steps.append(("Token", "ok", token_status()["source"]))
    except SystemExit as e:
        steps.append(("Token", "fail", str(e).strip()[:400]))
        print(json.dumps({"ok": False, "steps": [{"step": s, "status": st, "detail": d} for s, st, d in steps]},
                         ensure_ascii=False, indent=2))
        sys.exit(1)
    try:
        _init()
        steps.append(("连接 MCP 服务", "ok", _active_url["v"] or os.environ.get("MCD_MCP_URL", "?")))
        t = call_tool("now-time-info", {})
        steps.append(("now-time-info", "ok", redact(json.dumps(t, ensure_ascii=False))[:200]))
        ok = True
    except (RuntimeError, SystemExit) as e:
        steps.append(("连接 MCP 服务", "fail", redact(str(e))[:400]))
        ok = False
    del tok
    print(json.dumps({"ok": ok, "steps": [{"step": s, "status": st, "detail": d} for s, st, d in steps]},
                     ensure_ascii=False, indent=2))
    sys.exit(0 if ok else 1)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "--doctor":
        doctor()
    tool = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    try:
        out = call_tool(tool, args)
    except RuntimeError as e:
        print(redact(json.dumps({"error": str(e)}, ensure_ascii=False)))
        sys.exit(1)
    print(redact(json.dumps(out, ensure_ascii=False, indent=2) if not isinstance(out, str) else out))


if __name__ == "__main__":
    main()
