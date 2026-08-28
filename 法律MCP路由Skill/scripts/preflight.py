#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""法律MCP 凭证预检脚本（hook 自动化方向3，2026-08-28）

用途: 路由 Skill 第0步开工前预检凭证状态，把凭证过期故障链
     （任务中途 5 轮 auto_login 90-120s）压缩为开工前 1 次探测（<1s 本地推算）。

设计要点（详见 discussions/2026-08-28-凭证预检实施方案.md）:
  - 范围 = profile enabled MCP ∩ 本脚本可探能力（不写死库清单，动态求交集）
  - 报告强制分【已探/未探】两段，禁止"全部正常"总评（防假象性全绿）
  - 本脚本只探测+报告，绝不自动刷新（刷新由 LLM 按报告指引调 MCP auto_login 工具）
  - 纯 stdlib，0 网络默认模式

用法:
  python preflight.py             # 默认 markdown 报告
  python preflight.py --json      # 结构化输出
  python preflight.py --yuanndian # 附加元典余额查询（需环境变量 YUANDIAN_API_KEY/YUANDIAN_API_BASE，缺则跳过）

退出码: 0 = 已探项无 🟡/🔴 | 1 = 已探项存在 🟡/🔴
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = SKILL_DIR.parent  # 法信MCP/ 人民法院案例库MCP/ 为 SKILL_DIR 的兄弟目录

# 阈值常量（分钟）。法信 cookie 有效期为经验值（~1h），以实测报错校准；
# 权威判定始终以检索报错 / check_token 远程 probe 为准，本脚本结论均为推算值。
THRESHOLDS = {
    "faxin": {"green_max": 30, "yellow_max": 55},    # 距上次刷新: <30 🟢 | 30-55 🟡 | >55 🔴
    "rmfyalk": {"green_min": 30, "yellow_min": 15},  # JWT 剩余: >30 🟢 | 15-30 🟡 | <15 或已过 🔴
}

# 可探能力注册表: mcp_inventory 键 → (显示名, tokens.json 相对 REPO_DIR 路径, 判定器)
PROBABLE = {
    "faxin": ("法信(法规+案例,共享凭证)", "法信MCP/tokens.json", "faxin"),
    "rmfyalk": ("人民法院案例库", "人民法院案例库MCP/tokens.json", "rmfyalk"),
}
# 无法本地预检（Bearer 配在 mcp.json / 远程 key）→ 未探段
UNPROBABLE_NOTE = "Bearer/远程Key 无法本地预检，失效时按运行时降级处理"


def _reconfigure_stdio():
    """Windows 控制台 GBK 坑: 强制 UTF-8 输出（hook auto_log 同款教训）。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def _decode_jwt_exp(token: str):
    """解码 JWT payload 的 exp（unix 秒）。失败返回 None。不校验签名（预检只读元信息）。"""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        return float(exp) if exp else None
    except Exception:
        return None


def judge_faxin(tokens: dict):
    """法信判定器: timestamp(刷新时刻) + 经验有效期 1h 推算。"""
    ts_raw = tokens.get("timestamp")
    if not ts_raw:
        return "⚪", "tokens.json 无 timestamp 字段", None
    try:
        refreshed_at = time.mktime(time.strptime(str(ts_raw), "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return "⚪", f"timestamp 解析失败: {ts_raw!r}", None
    elapsed_min = (time.time() - refreshed_at) / 60
    th = THRESHOLDS["faxin"]
    level = tokens.get("level", "?")
    basis = f"(刷新于 {ts_raw}, 级别{level}, 经验有效期1h)"
    if elapsed_min < th["green_max"]:
        return "🟢", f"推算剩余 ~{th['green_max'] - elapsed_min:.0f}min {basis}", elapsed_min
    if elapsed_min < th["yellow_max"]:
        return "🟡", f"推算剩余 ~{th['yellow_max'] - elapsed_min:.0f}min {basis}", elapsed_min
    return "🔴", f"已超经验有效期, 距刷新 {elapsed_min:.0f}min {basis}", elapsed_min


def judge_rmfyalk(tokens: dict):
    """rmfyalk 判定器: JWT exp 本地解析（0 网络）。"""
    entry = tokens.get("rmfyalk") or {}
    token = entry.get("token") or ""
    if not token:
        return "⚪", "tokens.json 无 token 字段", None
    exp = _decode_jwt_exp(token)
    if exp is None:
        return "⚪", "JWT 解析失败（非标准格式）", None
    remain_min = (exp - time.time()) / 60
    th = THRESHOLDS["rmfyalk"]
    remain_show = f"{remain_min:.0f}" if abs(remain_min) < 1000 else "≈0"
    basis = f"JWT exp 本地解析, 剩余 {remain_show}min"
    if remain_min > th["green_min"]:
        return "🟢", basis, remain_min
    if remain_min > th["yellow_min"]:
        return "🟡", basis, remain_min
    verdict = "已过期" if remain_min <= 0 else f"剩余不足{th['yellow_min']}min(长任务必中途失效)"
    return "🔴", f"{verdict} | {basis}", remain_min


JUDGES = {"faxin": judge_faxin, "rmfyalk": judge_rmfyalk}


def load_enabled_mcps():
    """读 profile enabled MCP 清单。profile 不存在返回 (None, 原因)。"""
    profile_path = SKILL_DIR / "data" / "user-profile.json"
    if not profile_path.exists():
        return None, "profile 未建"
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        inv = data.get("mcp_inventory") or {}
        return [k for k, v in inv.items()
                if isinstance(v, dict) and v.get("enabled") and not k.startswith("_")], None
    except Exception as e:
        return None, f"profile 解析失败: {e}"


def query_yuandian_balance():
    """元典余额查询（best-effort，需环境变量；缺任一则跳过）。"""
    key = os.environ.get("YUANDIAN_API_KEY")
    base = os.environ.get("YUANDIAN_API_BASE")
    if not (key and base):
        return "⚪", "未配置 YUANDIAN_API_KEY/YUANDIAN_API_BASE 环境变量，跳过（可改用 MCP 工具 yuandian_get_user_balance）"
    try:
        from urllib.request import Request, urlopen
        req = Request(f"{base.rstrip('/')}/open/user/balance", headers={"Authorization": f"Bearer {key}"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        pts = json.dumps(data, ensure_ascii=False)[:120]
        return "🟢", f"余额接口响应: {pts}"
    except Exception as e:
        return "⚪", f"余额查询失败: {e}"


def run(with_yuandian=False):
    enabled, enabled_err = load_enabled_mcps()

    # 已探段: enabled ∩ 可探能力（profile 不可用 → 探全部可探库并标注）
    probed, skipped_unprobable = [], []
    if enabled is None:
        target_keys = list(PROBABLE.keys())
        scope_note = enabled_err or "profile 未建"
    else:
        target_keys = [k for k in enabled if k in PROBABLE]
        scope_note = f"profile enabled {len(enabled)} 项"
        skipped_unprobable = [k for k in enabled if k not in PROBABLE]

    for key in target_keys:
        name, rel_path, judge_key = PROBABLE[key]
        path = REPO_DIR / rel_path
        if not path.exists():
            probed.append({"key": key, "name": name, "verdict": "⚪",
                           "basis": f"凭证文件不存在: {rel_path}"})
            continue
        try:
            tokens = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            probed.append({"key": key, "name": name, "verdict": "⚪",
                           "basis": f"tokens.json 解析失败: {e}"})
            continue
        verdict, basis, _ = JUDGES[judge_key](tokens)
        probed.append({"key": key, "name": name, "verdict": verdict, "basis": basis})

    # 元典余额（可选）
    yuandian_row = None
    if with_yuandian:
        v, b = query_yuandian_balance()
        yuandian_row = {"key": "yuandian", "name": "元典余额", "verdict": v, "basis": b}
        if v == "⚪" and "yuandian" in (skipped_unprobable or []):
            skipped_unprobable.remove("yuandian")

    # 退出码: 已探项存在 🟡/🔴 → 1
    has_warn = any(r["verdict"] in ("🟡", "🔴") for r in probed)
    return {
        "scope_note": scope_note,
        "probed": probed,
        "unprobable": skipped_unprobable,
        "yuandian": yuandian_row,
        "has_warn": has_warn,
        "refresh_hint": {
            "faxin": "faxin_wenshu_auto_login / faxin_laws_auto_login（共享 tokens.json，任一即可）",
            "rmfyalk": "rmfyalk_auto_login",
        },
    }


def render_md(r):
    lines = ["## 法律MCP 凭证预检报告", "",
             f"> 范围: {r['scope_note']} | 结论均为**本地推算值**，权威判定以检索报错为准 | {time.strftime('%Y-%m-%d %H:%M:%S')}", "",
             "### 已探", "",
             "| MCP | 判定 | 依据 |", "|---|---|---|"]
    for row in r["probed"]:
        lines.append(f"| {row['name']} | {row['verdict']} | {row['basis']} |")
    if r["yuandian"]:
        lines.append(f"| {r['yuandian']['name']} | {r['yuandian']['verdict']} | {r['yuandian']['basis']} |")
    lines += ["", "### 未探（不参与本次判定）", ""]
    if r["unprobable"]:
        lines.append(f"- {', '.join(r['unprobable'])}: {UNPROBABLE_NOTE}")
    else:
        lines.append("- （无）")
    lines += ["", "### 处置指引", ""]
    warn_rows = [row for row in r["probed"] if row["verdict"] == "🔴"]
    warn_rows_y = [row for row in r["probed"] if row["verdict"] == "🟡"]
    if warn_rows:
        for row in warn_rows:
            hint = r["refresh_hint"].get(row["key"], "")
            lines.append(f"- 🔴 **{row['name']}**: 直接调用 `{hint}` 刷新（约30s 有头浏览器弹窗），刷新后复跑本脚本确认转 🟢")
    if warn_rows_y:
        for row in warn_rows_y:
            hint = r["refresh_hint"].get(row["key"], "")
            lines.append(f"- 🟡 **{row['name']}**: 长任务（预计超剩余有效期）建议先 `{hint}` 刷新；快答可豁免")
    if not warn_rows and not warn_rows_y:
        lines.append("- 已探项均可用，直接开工")
    lines.append("- ⚪ 未探项失效时按运行时降级规则处理（预检不覆盖）")
    return "\n".join(lines)


def main():
    _reconfigure_stdio()
    with_yuandian = "--yuanndian" in sys.argv
    r = run(with_yuandian)
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(render_md(r))
    sys.exit(1 if r["has_warn"] else 0)


if __name__ == "__main__":
    main()
