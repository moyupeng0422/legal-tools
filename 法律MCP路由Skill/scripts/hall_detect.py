#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hall_detect.py — 元典幻觉检测 HTTP API 直调脚本

背景（pitfall-checklist #18）：元典 hall_detect 未封装为 MCP 工具（list_apis 无此接口），
归属元典MCP范畴（计费50分/次），但需走 HTTP API 直接调用。

接口（用户2026-08-04提供）：
  POST https://open.chineselaw.com/open/hall_detect
  Content-Type: application/json; charset=utf-8
  Accept: application/json
  X-API-Key: <api_key>

用途：防幻觉判定（AI回答法条真实性），返回"一致/不一致/无法判断"（实测4场景全对）。
⚠️ 50分/次是元典最贵服务——仅关键结论校验用，且达到元典单任务50分上限，调用前须用户确认。

用法：
  # 方式1：命令行传参
  python scripts/hall_detect.py --title "中华人民共和国民法典" --article-number "577" --text "当事人一方不履行合同义务应当承担违约责任"

  # 方式2：传JSON文件（复杂场景）
  python scripts/hall_detect.py --json-file citations.json

  # API Key：优先 --api-key 参数，其次环境变量 YUANDIAN_API_KEY，其次 scripts/.env 中 YUANDIAN_API_KEY
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

# Windows GBK 终端 emoji 编码修复（P0，CC审核2026-08-13）
# 不加此块：print("🔍/✅/❌ ...") 在 GBK 终端崩 UnicodeEncodeError → exit code=1
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

API_URL = "https://open.chineselaw.com/open/hall_detect"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_api_key(cli_key: str) -> str:
    """API Key 优先级：CLI参数 > 环境变量 > scripts/.env"""
    if cli_key:
        return cli_key
    env_key = os.environ.get("YUANDIAN_API_KEY")
    if env_key:
        return env_key
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("YUANDIAN_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def call_hall_detect(payload: dict, api_key: str) -> dict:
    """调用 hall_detect 接口"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Accept", "application/json")
    req.add_header("X-API-Key", api_key)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return {"status": resp.status, "body": json.loads(body) if body else None}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"status": e.code, "body": body, "error": True}
    except urllib.error.URLError as e:
        return {"status": 0, "body": str(e.reason), "error": True}


def main():
    parser = argparse.ArgumentParser(description="元典幻觉检测（防幻觉判定，50分/次）")
    parser.add_argument("--title", help="法规名称（如 中华人民共和国民法典）——拼接进text供上下文参考")
    parser.add_argument("--article-number", help="条号（如 577 或 第五百七十七条）——拼接进text供上下文参考")
    parser.add_argument("--text", required=True, help="AI回答中引用的法条文本（必填，接口核心字段）")
    parser.add_argument("--json-file", help="JSON文件（含text等字段，优先于命令行）")
    parser.add_argument("--api-key", default=None, help="API Key（优先于环境变量/.env）")
    args = parser.parse_args()

    # 构造 payload：优先 json-file，其次命令行
    # ⚠️ 2026-08-13 核实（官方文档）：hall_detect 请求体 = {"text": "待核验法律文本"}，单字段！
    # 原实现传 {title, article_number, text} 三字段为错误格式，已修正。
    if args.json_file:
        with open(args.json_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        text = args.text or ""
        # title/article_number 仅作上下文拼接进 text（服务端按整段文本做校验）
        ctx = []
        if args.title:
            ctx.append(args.title)
        if args.article_number:
            ctx.append(args.article_number)
        if ctx:
            text = f"{'/'.join(ctx)}。{text}"
        payload = {"text": text}

    if not payload.get("text"):
        print("⚠️ 未提供待校验文本（--text 必填 或 --json-file 含text）", file=sys.stderr)
        sys.exit(1)

    api_key = load_api_key(args.api_key)
    if not api_key:
        print("⚠️ 未找到 YUANDIAN_API_KEY（--api-key 参数 / 环境变量 / scripts/.env）", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 调用 hall_detect（50分/次，元典最贵服务，应已获用户确认）")
    print(f"   payload: {json.dumps(payload, ensure_ascii=False)}")
    result = call_hall_detect(payload, api_key)

    if result.get("error"):
        print(f"❌ 调用失败 HTTP {result['status']}: {result['body']}", file=sys.stderr)
        sys.exit(1)

    print(f"✅ HTTP {result['status']}")
    print(json.dumps(result["body"], ensure_ascii=False, indent=2))

    # 提示：判定结果（一致/不一致/无法判断）以返回体为准，主agent据此决定是否修正引用
    print("\n💡 判定结果用于输出审核：若'不一致'，发回子agent补正（≤2次）")


if __name__ == "__main__":
    main()
