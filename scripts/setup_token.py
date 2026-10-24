#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置麦当劳 MCP Token（写入 .env，权限 600，不入 git、不入 zip）。

用法:
    python3 setup_token.py --token <TOKEN>        # 写入默认安全位置
    python3 setup_token.py --token <TOKEN> --in-skill-dir   # 写入 skill 目录（不推荐）
    python3 setup_token.py --status               # 查看是否已配置（脱敏显示）
    python3 setup_token.py --remove               # 删除默认位置的 .env

Token 获取: 登录 https://open.mcd.cn → 控制台 → 复制 MCP Token
安全说明: 脚本不会把 Token 打印到终端，也不会写进任何缓存文件。
"""
import argparse
import json
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DEFAULT_ENV = os.path.join(common.RUNTIME_DIR, ".env")
SKILL_ENV = os.path.join(common.SKILL_DIR, ".env")


def write_env(path, token):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = ""
    if os.path.exists(path):
        old = open(path, encoding="utf-8").read()
        lines = [l for l in old.splitlines()
                 if not l.lstrip().startswith(("export " + common.TOKEN_KEY, common.TOKEN_KEY))]
    else:
        lines = ["# 麦当劳中国 MCP Token —— 私密文件，请勿提交 GitHub 或打包分享",
                 "# 获取: https://open.mcd.cn 控制台", ""]
    lines.append("%s=%s" % (common.TOKEN_KEY, token))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", help="open.mcd.cn 控制台获取的 MCP Token")
    ap.add_argument("--in-skill-dir", action="store_true", help="写入 skill 目录（可被打包，仅自用）")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--remove", action="store_true")
    opts = ap.parse_args()

    if opts.status:
        st = common.token_status()
        print(json.dumps({"已配置": st["configured"], "来源": st["source"], "Token（脱敏）": st["fingerprint"]},
                         ensure_ascii=False, indent=2))
        return

    target = SKILL_ENV if opts.in_skill_dir else DEFAULT_ENV
    if opts.remove:
        if os.path.exists(target):
            os.remove(target)
            print(json.dumps({"removed": target}, ensure_ascii=False))
        else:
            print(json.dumps({"removed": None, "note": "文件不存在: %s" % target}, ensure_ascii=False))
        return

    token = opts.token or os.environ.get("MCD_TOKEN_INPUT", "").strip()
    if not token:
        print(__doc__)
        print("❌ 缺少 --token。注意：不要把 Token 直接贴在聊天里，用命令行参数更安全。")
        sys.exit(2)
    if len(token) < 8 or "\n" in token:
        print("❌ Token 格式异常（过短或含换行），请重新复制")
        sys.exit(2)

    path = write_env(target, token)
    del token
    common._TOKEN_CACHE.update(value=None, source=None)  # 让下次调用重新读取
    st = common.token_status()
    mode = stat.S_IMODE(os.stat(path).st_mode)
    print(json.dumps({
        "已写入": path,
        "文件权限": oct(mode),
        "Token（脱敏）": st["fingerprint"],
        "下一步": "python3 scripts/doctor.py   # 自检连通性",
        "安全提示": "该文件已在 .gitignore 中；打包请一律用 scripts/safe_package.py（会排除 .env 并做密钥扫描）",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
