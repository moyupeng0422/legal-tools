#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_log_hook.py — PostToolUse hook 自动记账（法律MCP路由 skill 宿主增强层）

定位：Claude Code / Codex 双宿主可选增强（WorkBuddy 无 hooks 机制，维持手动记账，功能无损失）。
原理：宿主每次 MCP 工具调用后经 stdin 注入 {tool_name, tool_input, tool_response, session_id,
transcript_path, cwd, ...}（两宿主 JSON 同构，2026-08-28 Codex 适配核验；Codex 另有
turn_id/tool_use_id）——脚本纯旁路解析并写入 usage_log，LLM 全程零参与、无感知。
任务边界 = session_id（一个会话天然一个 task_id），无任何 LLM 维护的状态文件。
宿主判定：stdin 含 tool_use_id → host=codex，否则 host=cc（仅入 note 供审计）。

设计约束（见 discussions/2026-08-27-hook自动记账实施方案.md v2）：
  ① 只记 server_alias 映射内的 7 个法律 MCP；未映射（qcc-*/tyc 等）静默跳过
  ② 档位由脚本查 credit-dictionary（三形态），LLM 不传 cost——错账从机制上消灭
  ③ quota_type 从 data/user-profile.json mcp_inventory 的 tier 映射
  ④ 永远 exit 0：记账失败不阻塞主流程（异常写 stderr 供排查）
  ⑤ 与手动记账互斥靠约定：装了本 hook 的宿主 LLM 免手动记账；verify_usage --dedup-hook 兜底去重

安装：见同目录 README.md（settings.json 配置模板 hooks-settings.example.json）。
"""
import io
import json
import os
import re
import sys
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# skill 内相对定位（<SKILL_DIR> 任意安装路径均成立）
HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(HOOKS_DIR)
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
CREDIT_DICT = os.path.join(SKILL_DIR, "references", "credit-dictionary.json")
USER_PROFILE = os.path.join(SKILL_DIR, "data", "user-profile.json")
sys.path.insert(0, SCRIPTS_DIR)

# tier → quota_type 映射（user-profile mcp_inventory.tier → log 18字段 quota_type）
TIER2QUOTA = {
    "free": "infinite",
    "free_trial": "free_trial",
    "quota_recurring": "recurring",
    "one_time": "one_time",
}


def load_server_alias():
    """credit-dictionary 顶层 server_alias 段 {server名: inventory key}。缺失返回 {}。"""
    try:
        with open(CREDIT_DICT, "r", encoding="utf-8") as f:
            return json.load(f).get("server_alias", {})
    except Exception:
        return {}


def load_quota_map():
    """user-profile mcp_inventory {key: tier} → {key: quota_type}。缺失返回 {}。"""
    try:
        with open(USER_PROFILE, "r", encoding="utf-8") as f:
            inv = json.load(f).get("mcp_inventory", {})
        return {k: TIER2QUOTA.get(v.get("tier"), "recurring")
                for k, v in inv.items() if isinstance(v, dict) and "tier" in v}
    except Exception:
        return {}


def load_cost_known_map():
    """user-profile mcp_inventory {key: cost_known}——仅收集显式 False 的 key
    （知识库外 MCP，2026-08-28 cost_known 轮）。缺失/缺省均视为已知档位，返回 {}。"""
    try:
        with open(USER_PROFILE, "r", encoding="utf-8") as f:
            inv = json.load(f).get("mcp_inventory", {})
        return {k: False for k, v in inv.items()
                if isinstance(v, dict) and v.get("cost_known") is False}
    except Exception:
        return {}


def parse_response(resp):
    """尽力解析 tool_response → (result, has_content, error_type, total_count)。
    解析失败不报错，按 ok/无内容处理（记账事实层以调用发生为准，响应细节尽力而为）。"""
    result, has_content, error_type, total_count = "ok", False, None, None
    try:
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
            except json.JSONDecodeError:
                has_content = bool(resp.strip())
                return result, has_content, error_type, total_count
        if isinstance(resp, dict):
            if resp.get("isError") is True:
                result = "error"
            text = ""
            content = resp.get("content")
            if isinstance(content, list):
                text = " ".join(str(b.get("text", "")) for b in content
                                if isinstance(b, dict))
            elif "result" in resp:
                text = str(resp["result"])
            elif "error" in resp:
                text = str(resp["error"])
                if result != "error" and len(resp) <= 2:
                    result = "error"
            else:
                text = json.dumps(resp, ensure_ascii=False)
            has_content = bool(text.strip()) and text.strip() not in ('""', "null", "[]", "{}")
            # 业务失败文本特征判定（2026-08-28 T2 实测补充）：部分 MCP（rmfyalk 实证）把
            # 失败包装在正常响应里（无 isError 字段）——Token 过期记成 ok 失真。
            # 尽力而为：特征匹配可能误判，记账为旁路审计，可接受。
            if result == "ok":
                low_t = text.lower()
                if any(k in low_t for k in ("token 已失效", "token已失效", "token 已过期", "token已过期",
                                            "cookie 已过期", "cookie已过期")):
                    result, error_type = "error", "401"
                elif any(k in low_t for k in ("connecterror", "connection error",
                                              "net::err", "err_connection", "err_timed_out")):
                    # flk "错误: ConnectError" 实证（2026-08-28 行为级复测）：网络层失败包在
                    # result 字符串里，无 isError——原表漏判记成 ok。net 类与 401/400 分列，
                    # 供止损统计（401 刷新/400 改参/net 等待重试）。
                    result, error_type = "error", "net"
                elif any(k in text for k in ("未查询到相关", "未获取到案例", "未获取到")):
                    result = "empty"
            if result == "error":
                t = text.lower()
                error_type = ("401" if "401" in t or "token" in t or "cookie" in t or "登录" in text
                              else "400" if "400" in t or "参数" in text
                              else "timeout" if "timeout" in t or "超时" in text
                              else "net" if any(k in t for k in ("connecterror", "connection error",
                                                                 "net::err", "err_connection",
                                                                 "err_timed_out"))
                              else "other")
            m = re.search(r'"total"\s*:\s*(\d+)', text)
            if m:
                total_count = int(m.group(1))
    except Exception:
        pass
    return result, has_content, error_type, total_count


def summarize_params(tool_input):
    """参数脱敏摘要：前4个 key=value，值截断60字符；疑似敏感字段（key/token/cookie）只记名不记值。"""
    try:
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
    except Exception:
        return ""


def main():
    try:
        # ⚠️ 必须走 buffer 二进制读 + utf-8 解码（2026-08-28 实测坑）：hook 进程 stdin
        # 默认编码为 GBK/cp936，sys.stdin.read() 遇 UTF-8 中文（工具响应必含中文）抛
        # UnicodeDecodeError → 静默 return，记账零条目且无痕迹（debug dump 0 字节实锤）
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        return  # stdin 非 JSON：静默退出（旁路永不阻塞）
    tool_name = event.get("tool_name", "")
    if not tool_name.startswith("mcp__"):
        return
    parts = tool_name.split("__")
    if len(parts) < 3:
        return
    server, tool = parts[1], "__".join(parts[2:])

    alias = load_server_alias()
    inv_key = alias.get(server)
    if not inv_key:
        return  # 非法律 MCP（qcc-*/tyc/其他）→ 静默跳过

    # 复用 log_usage 的查表与写入（单一通道）
    try:
        import log_usage as lu
    except Exception as e:
        print(f"[auto_log_hook] import log_usage 失败: {e}", file=sys.stderr)
        return

    tiers, defaults = lu.load_tier_table()
    notes = ["source=hook"]
    # 宿主标记（2026-08-28 Codex 适配）：Codex stdin 独有 tool_use_id/turn_id；
    # 有 tool_use_id 顺带记前 12 位（原生幂等审计键）。仅入 note，不影响任何判定。
    if event.get("tool_use_id"):
        notes.append(f"host=codex tuid={event['tool_use_id'][:12]}")
    else:
        notes.append("host=cc")
    if load_cost_known_map().get(inv_key) is False:
        # profile 显式标 cost_known:false（知识库外 MCP）→ 记 null 不参与积分对账，
        # 优先于查表/default-tier 兜底（防假 default 分污染账本，2026-08-28 立）
        cost = None
        notes.append("auto-hook:cost-unknown")
    elif tiers is not None:
        cost = lu.resolve_tool_tier(tiers, inv_key, tool)
        if cost is None:
            cost = (defaults or {}).get(inv_key, 0)
            notes.append("auto-hook:default-tier")
    else:
        cost = 0
        notes.append("auto-hook:dict-missing")

    quota = load_quota_map().get(inv_key, "recurring")
    result, has_content, error_type, total_count = parse_response(event.get("tool_response"))
    if error_type:
        notes.append(f"hook-err:{error_type}")

    entry = {
        "task_id": event.get("session_id") or "unknown-session",
        "scene_id": "",
        "function_id": "",
        "mcp": inv_key,
        "tool": tool,
        "params_summary": summarize_params(event.get("tool_input")),
        "cost": cost,
        "quota_type": quota,
        "result": result,
        "result_has_content": has_content,
        "return_count": 0,
        "total_count": total_count,
        "error_type": error_type if result == "error" else None,
        "retry_count": 0,
        "agent": "auto-hook",
        "note": " ".join(notes),
    }
    ok, msg = lu.write_entry(entry, params_required=False)
    if not ok:
        print(f"[auto_log_hook] {msg}", file=sys.stderr)
    # 成功时静默（stdout 会注入对话上下文，不污染）——永远 exit 0
    return


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[auto_log_hook] 未捕获异常: {e}", file=sys.stderr)
    sys.exit(0)
