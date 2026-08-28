#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_from_transcript.py — 从会话留痕离线补记 MCP 调用账目（CC transcript / Codex rollout）

定位：hook 未装/漏装/记账故障时的降级恢复通道；也是"先试用 skill 后装 hook"用户的过渡工具。
原理：会话留痕完整记录每次 MCP 调用（工具名+入参+响应），事后离线提取补账。
格式自动探测（scripts/transcript_parsers.py，2026-08-28 Codex 宿主适配）：
  cc     Claude Code transcript（~/.claude/projects/<munged-cwd>/<session_id>.jsonl）
  codex  Codex rollout（~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl；子 agent 是独立文件）

用法：
  python scripts/hooks/backfill_from_transcript.py --session <留痕.jsonl 路径>
  python scripts/hooks/backfill_from_transcript.py --session <主文件> <子agent文件...> --dry-run  # 只预览
  python scripts/hooks/backfill_from_transcript.py --session <path> --task-id xxx # 覆盖 task_id（默认=第一个文件名）

行为：
  - 自动探测格式 → 提取全部 MCP 调用 → server_alias 映射（未映射列入 skipped 报告，不写入）
  - 档位三形态查 credit-dictionary（同 log_usage）→ 走 write_entry 单一通道
  - 幂等：同 task_id 下已存在同工具且调用时刻匹配的条目 → 跳过（防重复补记）
  - agent=backfill，note="source=backfill call_ts=..."（调用发起时刻，对账窗口语义）；参数脱敏
"""
import argparse
import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(HOOKS_DIR)
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
CREDIT_DICT = os.path.join(SKILL_DIR, "references", "credit-dictionary.json")
USER_PROFILE = os.path.join(SKILL_DIR, "data", "user-profile.json")
sys.path.insert(0, SCRIPTS_DIR)

TIER2QUOTA = {"free": "infinite", "free_trial": "free_trial",
              "quota_recurring": "recurring", "one_time": "one_time"}


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def summarize_params(tool_input):
    """同 auto_log_hook：前4个 key=value，值截60字符，敏感字段只记名。"""
    if not isinstance(tool_input, dict) or not tool_input:
        return ""
    parts = []
    for i, (k, v) in enumerate(tool_input.items()):
        if i >= 4:
            parts.append("...")
            break
        s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
        if any(w in k.lower() for w in ("key", "token", "cookie", "password", "secret")):
            parts.append(f"{k}=<redacted>")
        else:
            parts.append(f"{k}={s[:60]}")
    return " ".join(parts)


def parse_transcript(path):
    """提取 (calls, results)：格式自动探测（cc transcript / codex rollout，见 transcript_parsers）。
    codex 条目自包含（result/is_error 在 call dict 内，results 恒空）；cc 靠 tool_use_id 配对。"""
    import transcript_parsers as tp
    fmt, calls, results = tp.parse_auto(path)
    for c in calls:
        c.setdefault("fmt", fmt)
    return calls, results


def resp_result(content):
    """tool_result 内容 → (result, has_content, total_count)——尽力而为。"""
    result, has_content, total = "ok", False, None
    try:
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
        elif content is not None:
            text = json.dumps(content, ensure_ascii=False)
        t = text.strip()
        has_content = bool(t) and t not in ('""', "null", "[]", "{}")
        low = text.lower()
        if '"iserror": true' in low or t.startswith('{"error"'):
            result = "error"
    except Exception:
        pass
    return result, has_content, total


def main():
    ap = argparse.ArgumentParser(description="从会话留痕离线补记 MCP 调用账目（CC transcript / Codex rollout 自动探测）")
    ap.add_argument("--session", required=True, nargs="+", metavar="PATH",
                    help="会话留痕 jsonl 路径（可多个：主会话 + 子 agent rollout；格式自动探测）")
    ap.add_argument("--task-id", default=None, help="覆盖 task_id（默认=第一个文件名去 .jsonl）")
    ap.add_argument("--dry-run", action="store_true", help="只预览待补记条目，不写入")
    args = ap.parse_args()

    for p in args.session:
        if not os.path.isfile(p):
            print(f"⛔ 留痕文件不存在: {p}", file=sys.stderr)
            return 1
    task_id = args.task_id or os.path.splitext(os.path.basename(args.session[0]))[0]

    alias = load_json(CREDIT_DICT, {}).get("server_alias", {})
    profile = load_json(USER_PROFILE, {})
    inv = profile.get("mcp_inventory", {})
    quota_map = {k: TIER2QUOTA.get(v.get("tier"), "recurring")
                 for k, v in inv.items() if isinstance(v, dict) and "tier" in v}
    # cost_known:false（知识库外 MCP）→ 记 null 不参与积分对账（与 auto_log_hook 同规则）
    cost_known_map = {k for k, v in inv.items()
                      if isinstance(v, dict) and v.get("cost_known") is False}

    import log_usage as lu
    tiers, defaults = lu.load_tier_table()

    # 幂等判定素材：该 task_id 已有条目（两类——①backfill 自写条目按 note call_ts 等值；
    # ②auto-hook 等他源条目按"同工具+timestamp±10s"时间匹配，2026-08-28 修复：
    # auto-hook 条目无 call_ts，初版只认 call_ts 导致对同一调用双记）
    existing = []
    if os.path.exists(lu.LOG_PATH):
        with open(lu.LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("task_id") != task_id:
                    continue
                note = r.get("note") or ""
                call_ts = note.split("call_ts=")[1].split()[0] if "call_ts=" in note else ""
                existing.append({"tool": r.get("tool"), "call_ts": call_ts,
                                 "ts": r.get("timestamp") or ""})

    def ts_to_dt(s):
        from datetime import datetime
        try:
            t = datetime.fromisoformat(s)
            return t.astimezone().replace(tzinfo=None) if t.tzinfo else None
        except (ValueError, TypeError):
            return None

    def already_logged(tool, call_ts_full):
        key = (tool, (call_ts_full or "")[:19])
        for e in existing:
            if e["call_ts"] and (e["tool"], e["call_ts"][:19]) == key:
                return True
        # auto-hook 等条目：记账时刻∈[调用发起-5s, 发起+600s]（长调用如 auto_login 差 50s+，
        # 2026-08-28 T2 实测修正——±10s 容差会漏判致同调用双记）
        t_call = ts_to_dt(call_ts_full)
        if t_call is not None:
            for e in existing:
                if e["tool"] != tool or e["call_ts"]:
                    continue
                t_e = ts_to_dt(e["ts"])
                if t_e is not None and -5 <= (t_e - t_call).total_seconds() <= 600:
                    return True
        return False

    calls, results = [], {}
    for p in args.session:
        c, r = parse_transcript(p)
        calls.extend(c)
        results.update(r)
    written, skipped_unmapped, skipped_dup = 0, [], 0
    print(f"=== backfill [{task_id}] ===\n留痕 MCP 调用总数: {len(calls)}")
    for c in calls:
        inv_key = alias.get(c["server"])
        if not inv_key:
            skipped_unmapped.append(f"{c['server']}.{c['tool']}")
            continue
        if already_logged(c["tool"], c["ts"]):
            skipped_dup += 1
            continue
        # call_ts 存完整 ISO（含 Z）——verify_usage --from-transcript 比对时需还原 UTC→本地；
        # 幂等键仍用前 19 位（纯等值比较，无时区语义）
        note = f"source=backfill call_ts={c['ts']}"
        if inv_key in cost_known_map:
            cost = None
            note += " backfill:cost-unknown"
        else:
            cost = lu.resolve_tool_tier(tiers or {}, inv_key, c["tool"])
            if cost is None:
                cost = (defaults or {}).get(inv_key, 0)
                note += " backfill:default-tier"
        # 响应判定：codex 条目自包含（result dict 在 call 内，复用 auto_log_hook 的
        # 失败文本特征判定，error_type 同步可得）；cc 走原有 resp_result 尽力判定（行为不变）
        if c.get("fmt") == "codex":
            import auto_log_hook as alh
            result, has_content, err_type, _ = alh.parse_response(c.get("result"))
        else:
            result, has_content, _ = resp_result(results.get(c["id"]))
            err_type = None
        entry = {
            "task_id": task_id, "scene_id": "", "function_id": "",
            "mcp": inv_key, "tool": c["tool"],
            "params_summary": summarize_params(c["input"]),
            "cost": cost, "quota_type": quota_map.get(inv_key, "recurring"),
            "result": result, "result_has_content": has_content,
            "return_count": 0, "total_count": None,
            "error_type": err_type if result == "error" else None, "retry_count": 0,
            "agent": "backfill", "note": note,
        }
        if args.dry_run:
            print(f"  [dry-run] {c['ts'][:19]} {inv_key}.{c['tool']} cost={cost} result={result}")
            written += 1
            continue
        ok, msg = lu.write_entry(entry, params_required=False)
        if ok:
            written += 1
            existing.append({"tool": c["tool"], "call_ts": (c["ts"] or "")[:19], "ts": ""})
            print(f"  ✅ {msg}")
        else:
            print(f"  ⛔ {msg}", file=sys.stderr)

    print(f"\n补记 {written} 条 ｜ 幂等跳过 {skipped_dup} 条")
    if skipped_unmapped:
        uniq = sorted(set(skipped_unmapped))
        print(f"未映射 server 跳过 {len(skipped_unmapped)} 条（{len(uniq)} 种）：{', '.join(uniq[:8])}"
              f"{' ...' if len(uniq) > 8 else ''}")
        print("→ 如需记账，请在 credit-dictionary.json server_alias 段添加映射后重跑")
    return 0


if __name__ == "__main__":
    sys.exit(main())
