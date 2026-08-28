#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transcript_parsers.py — CC transcript / Codex rollout 的 MCP 调用提取（共享解析模块）

服务对象：scripts/hooks/backfill_from_transcript.py（离线补记）+ scripts/verify_usage.py
（--from-transcript 逐调用对账）。两宿主的会话留痕格式不同，本模块自动探测并统一输出。

两种格式（2026-08-28 Codex 宿主适配轮实证）：
  cc     Claude Code transcript（~/.claude/projects/<munged>/<session_id>.jsonl）
         tool_use 块与 tool_result 块分离，靠 tool_use_id 配对
  codex  Codex rollout（~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl）
         MCP 调用为自包含条目：type=="event_msg" → payload.type=="item_completed"
         → item.type=="McpToolCall"，一行含 server/tool/arguments/result（无需配对）
         子 agent 为独立 rollout 文件（session_meta.session_id=根线程、parent_thread_id=直接父）

统一输出：parse_auto(path) → (fmt, calls, results)
  fmt     "cc" | "codex"
  calls   [{ts, id, server, tool, input, result, is_error}]（result/is_error 仅 codex 必有；
          cc 的响应在 results 里按 id 查）
  results {id: response}（仅 cc 非空）
"""
import json
import os
import re
from datetime import datetime, timezone


def detect_format(path):
    """读首行判断格式：含 "type":"session_meta" → codex；否则 cc。失败按 cc 处理。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            first = f.readline()
        rec = json.loads(first)
        return "codex" if rec.get("type") == "session_meta" else "cc"
    except Exception:
        return "cc"


def _ms_to_iso(ms):
    """epoch 毫秒 → ISO UTC 字符串（含 Z，毫秒精度）。与 verify_usage.parse_ts 兼容。"""
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"
    except (ValueError, TypeError, OSError, OverflowError):
        return ""


def parse_cc(path):
    """CC transcript：tool_use/tool_result 块配对。
    返回 (calls, results)：calls=[{ts,id,server,tool,input}]，results={tool_use_id: content}。"""
    calls, results = [], {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "mcp__" not in line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            ts = rec.get("timestamp", "")
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and str(b.get("name", "")).startswith("mcp__"):
                    parts = b["name"].split("__")
                    if len(parts) >= 3:
                        calls.append({"ts": ts, "id": b.get("id"), "server": parts[1],
                                      "tool": "__".join(parts[2:]), "input": b.get("input"),
                                      "result": None, "is_error": False})
                elif b.get("type") == "tool_result" and b.get("tool_use_id"):
                    results[b["tool_use_id"]] = b.get("content")
    return calls, results


_MCP_IN_EXEC_RE = re.compile(r"tools\.mcp__([A-Za-z0-9_-]+)__([A-Za-z0-9_]+)\s*\(")


def parse_codex(path):
    """Codex rollout：McpToolCall 自包含条目（主路径）。
    ts 取 payload.started_at_ms（=调用发起时刻，对齐对账窗口的"发起"语义；
    行级 timestamp 是完成时刻，不可用）。
    兜底：无 McpToolCall 条目时（如 code mode 包装形态），正则抽层2
    custom_tool_call(name=="exec") input 中的 tools.mcp__<server>__<tool>——
    尽力而为（无入参/响应细节），条目标 fallback=True。"""
    calls = []
    fallback = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if '"McpToolCall"' not in line and '"custom_tool_call"' not in line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rtype = rec.get("type")
            if rtype == "event_msg":
                payload = rec.get("payload") or {}
                if payload.get("type") != "item_completed":
                    continue
                item = payload.get("item") or {}
                if item.get("type") != "McpToolCall":
                    continue
                result = item.get("result")
                calls.append({
                    "ts": _ms_to_iso(payload.get("started_at_ms")) or rec.get("timestamp", ""),
                    "id": item.get("id", ""),
                    "server": item.get("server", ""),
                    "tool": item.get("tool", ""),
                    "input": item.get("arguments"),
                    "result": result if isinstance(result, dict) else None,
                    "is_error": bool(isinstance(result, dict) and result.get("isError")),
                    "fallback": False,
                })
            elif rtype == "response_item":
                payload = rec.get("payload") or {}
                if payload.get("type") != "custom_tool_call" or payload.get("name") != "exec":
                    continue
                m = _MCP_IN_EXEC_RE.search(str(payload.get("input", "")))
                if not m:
                    continue
                fallback.append({
                    "ts": _ms_to_iso((rec.get("internal_chat_message_metadata_passthrough") or {})
                                     .get("create_time", 0) * 1000) or rec.get("timestamp", ""),
                    "id": payload.get("call_id", ""),
                    "server": m.group(1), "tool": m.group(2),
                    "input": None, "result": None, "is_error": False,
                    "fallback": True,
                })
    if not calls and fallback:
        return fallback
    return calls


def parse_auto(path):
    """自动探测格式并解析。返回 (fmt, calls, results)。"""
    fmt = detect_format(path)
    if fmt == "codex":
        return fmt, parse_codex(path), {}
    calls, results = parse_cc(path)
    return fmt, calls, results
