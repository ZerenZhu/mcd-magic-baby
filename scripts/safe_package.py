#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全打包：生成可分发的 zip，排除私密文件并对包体做密钥扫描。

为什么不用上游 package_skill.py：它会把目录内所有文件打进去，
skill 目录下的 .env / order_cache.json / __pycache__ 会一起泄漏。

用法:
    python3 safe_package.py [输出目录]          # 默认输出到当前目录
    python3 safe_package.py --check             # 只做检查，不生成 zip
"""
import json
import os
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SKILL_PATH = common.SKILL_DIR
EXCLUDE_NAMES = {".env", ".env.local", ".env.*", ".DS_Store", "*.pyc", "order_cache.json",
                 "auto_order_log.json", "*.md.bak"}
EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", "node_modules", "data"}
SECRET_PATTERNS = [
    (re.compile(r"MCD_MCP_TOKEN\s*=\s*['\"]?([A-Za-z0-9._\-]{8,})"), "硬编码 Token"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}"), "Bearer 串"),
]


def should_skip(rel_path):
    parts = Path(rel_path).parts
    if any(p in EXCLUDE_DIRS for p in parts[:-1]):
        return True
    name = parts[-1]
    # 排除私密环境变量文件，但保留 .env.example 这类分发模板
    if name == ".env" or (name.startswith(".env.") and not name.endswith(".example")):
        return True
    if name in EXCLUDE_NAMES:
        return True
    return name.endswith((".pyc", ".bak")) or name.startswith("麦门账单_")


def scan_secrets(files):
    """对准备入包的文件做密钥扫描；同时检查已知 Token 是否出现在文本里。"""
    hits = []
    tok, _ = common.load_token()
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append({"file": str(f.relative_to(SKILL_PATH)), "reason": label})
        if tok and tok in text:
            hits.append({"file": str(f.relative_to(SKILL_PATH)), "reason": "包含本机 Token 明文"})
    return hits


def package(output_dir):
    files = [p for p in Path(SKILL_PATH).rglob("*") if p.is_file() and not should_skip(p.relative_to(SKILL_PATH))]
    hits = scan_secrets(files)
    st = common.token_status()
    checks = {
        "私密文件已排除": sorted({str(p.relative_to(SKILL_PATH)) for p in Path(SKILL_PATH).rglob("*")
                            if p.is_file() and should_skip(p.relative_to(SKILL_PATH))}),
        "Token 配置位置": st["source"] or "未配置",
        "订单缓存/账单目录": common.RUNTIME_DIR,
    }
    if hits:
        print(json.dumps({"打包中止": "检测到疑似密钥", "hits": hits}, ensure_ascii=False, indent=2))
        sys.exit(1)
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / ("%s.zip" % Path(SKILL_PATH).name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f.relative_to(Path(SKILL_PATH).parent))
    print(json.dumps({
        "✅ 打包完成": str(zip_path),
        "入包文件数": len(files),
        "安全检查": checks,
        "密钥扫描": "通过（未发现 Token 明文）",
    }, ensure_ascii=False, indent=2))
    return zip_path


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
    out = args[0] if args else "."
    if "--check" in sys.argv:
        files = [p for p in Path(SKILL_PATH).rglob("*") if p.is_file() and not should_skip(p.relative_to(SKILL_PATH))]
        hits = scan_secrets(files)
        print(json.dumps({"结果": "✅ 检查通过，可安全发布" if not hits else "❌ 发现密钥泄漏风险",
                          "hits": hits or None,
                          "files": [str(f.relative_to(SKILL_PATH)) for f in files]},
                         ensure_ascii=False, indent=2))
        sys.exit(1 if hits else 0)
    package(out)


if __name__ == "__main__":
    main()
