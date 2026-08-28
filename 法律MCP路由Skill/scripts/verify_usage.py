#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_usage.py — 调用对账脚本（主agent任务结束时执行）

对账逻辑（credit-model.md 第三节）：
  日志条数（data/mcp_usage_log.jsonl，本次task_id） vs traces 中 mcp_tools 事件数
  差异 = 异常（子agent擅自重试/漏记/跨任务干扰）→ 主agent先与子agent核实再上报

⚠️ traces 的 mcp_tools span 只有时间/耗时/状态（无工具名/参数）——只能"计数对账"，
   且是全局事件（可能含其他任务），所以差异需要主agent人工核实。
⚠️ trace 结构假设 {"spans":[{"name":"mcp_tools"}]}——2026-08-27 起对账前自动探测（abtest-F1-20260827 P6）：
   traces 目录缺失 / 无 trace 文件 / 结构不符 → 输出"降级跳过"结论（exit code=2），
   usage_log 为权威记录，不再报"差异 N"误导人工归因（abtest 实测：WorkBuddy 宿主
   traces 事件数与日志条数口径不匹配，3 次对账差异全靠人工归因"宿主口径不适用"）。

用法：
  # 对账指定任务
  python scripts/verify_usage.py --task-id task-001

  # 查看某任务日志明细
  python scripts/verify_usage.py --task-id task-001 --show-log

  # 按 usage_log 的 task_id 时间窗过滤 traces（推荐——把跨任务干扰从人工归因变为自动过滤，
  # test-run-20260821 审查改进：A2 轮 traces 62 条 vs 日志 3 条全靠人工核对）
  python scripts/verify_usage.py --task-id task-001 --by-log-window

  # 兼容旧用法：时间窗口过滤
  python scripts/verify_usage.py --task-id task-001 --since-minutes 30

  # 指定traces根目录（WorkBuddy 宿主对账用；也可用环境变量 TRACES_DIR；不提供则跳过 traces 对账）
  python scripts/verify_usage.py --task-id task-001 --traces-dir /path/to/traces

输出：
  ✅ 一致 / ⚠️ 差异（给出差异数与可能原因）
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

# Windows GBK 终端 emoji 编码修复（P0，CC审核2026-08-13）
# 不加此块：print("✅/⚠️ ...") 在 GBK 终端崩 UnicodeEncodeError → exit code=1
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 与 log_usage.py 同源：LOG_USAGE_PATH 环境变量覆盖（2026-08-28 Codex 宿主适配）
LOG_PATH = os.environ.get("LOG_USAGE_PATH") or os.path.join(SCRIPT_DIR, "..", "data", "mcp_usage_log.jsonl")
# traces 根目录：环境变量 TRACES_DIR 或运行时 --traces-dir 传入；都未提供则跳过 traces 对账
DEFAULT_TRACES = os.environ.get("TRACES_DIR")


def load_usage_log(task_id: str):
    """读取指定 task_id 的所有日志记录"""
    records = []
    if not os.path.exists(LOG_PATH):
        return records
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("task_id") == task_id:
                records.append(rec)
    return records


def count_mcp_events_in_trace(trace_path: str) -> int:
    """统计单个trace文件中的 mcp_tools 事件数"""
    count = 0
    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for span in data.get("spans", []):
            if span.get("name") == "mcp_tools":
                count += 1
    except (json.JSONDecodeError, OSError):
        pass
    return count


def probe_traces_structure(traces_dir: str, t_start: datetime) -> tuple[bool, int]:
    """探测 traces 目录结构是否符合对账假设（2026-08-27 立，abtest-F1-20260827 P6）。

    返回 (structure_ok, scanned_files)：
    - structure_ok=True：扫描到的 trace_*.json 中至少一个含 {"spans":[{"name":"mcp_tools"}]} 结构
      → 计数对账有效，正常出"一致/差异"结论
    - structure_ok=False：目录不存在 / 窗口内无 trace_*.json / 所有文件均无该结构
      → 宿主 traces 计数口径不适用（abtest 实测：WorkBuddy 宿主 traces 16 事件 vs 日志 7 条，
        差异全靠人工归因"宿主口径"），直接输出降级结论，不报"差异 N"误导人工归因

    探测窗口与对账窗口对齐：mtime ≥ (t_start - 24h)（与 count_traces_mcp_events_window 的
    粗排除口径一致——trace 会话结束才落盘，mtime 晚于调用时刻，故用窗口前 24h 下界）。"""
    if not traces_dir or not os.path.isdir(traces_dir):
        return False, 0
    mtime_floor = t_start - timedelta(hours=24)
    scanned = 0
    for root, _, files in os.walk(traces_dir):
        for fn in files:
            if not fn.startswith("trace_") or not fn.endswith(".json"):
                continue
            path = os.path.join(root, fn)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
            except OSError:
                continue
            if mtime < mtime_floor:
                continue
            scanned += 1
            if count_mcp_events_in_trace(path) > 0:
                return True, scanned
            # 含 spans 数组但无 mcp_tools 命名的 span 也算结构符合（事件数为 0 是真实值）
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data.get("spans"), list):
                    return True, scanned
            except (json.JSONDecodeError, OSError):
                continue
    return False, scanned


def count_traces_mcp_events(traces_dir: str, since: datetime) -> int:
    """统计 traces 目录下（since 时间之后）所有 mcp_tools 事件数"""
    total = 0
    if not traces_dir or not os.path.isdir(traces_dir):
        return 0
    for root, _, files in os.walk(traces_dir):
        for fn in files:
            if not fn.startswith("trace_") or not fn.endswith(".json"):
                continue
            path = os.path.join(root, fn)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
            except OSError:
                continue
            if mtime < since:
                continue
            total += count_mcp_events_in_trace(path)
    return total


def count_traces_mcp_events_window(traces_dir: str, t_start: datetime, t_end: datetime) -> int:
    """统计 traces 中 span.startedAt ∈ [t_start, t_end] 的 mcp_tools 事件数。
    --by-log-window 模式用：窗口取自 usage_log 该 task_id 首条/末条记录时间。

    ⚠️ 不用文件 mtime 过滤（test-run 复测实证）：trace 文件在会话结束时一次性落盘，
    mtime 与调用发生时间脱节（A2 任务 22:49 调用，文件 00:10+ 才写），mtime 粗筛会把
    窗口内调用的文件整批排除。改读 span 内部 startedAt（ISO UTC）精确过滤；
    文件仅按 mtime 上界粗排除明显过旧的（性能优化，不影响正确性）。"""
    total = 0
    if not traces_dir or not os.path.isdir(traces_dir):
        return 0
    for root, _, files in os.walk(traces_dir):
        for fn in files:
            if not fn.startswith("trace_") or not fn.endswith(".json"):
                continue
            path = os.path.join(root, fn)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
            except OSError:
                continue
            if mtime < t_start - timedelta(hours=24):
                continue  # 落盘早于窗口前24h，span 不可能在窗口内（粗排除）
            total += count_mcp_events_in_trace_window(path, t_start, t_end)
    return total


def count_mcp_events_in_trace_window(trace_path: str, t_start: datetime, t_end: datetime) -> int:
    """统计单个 trace 文件中 span.startedAt 落在 [t_start, t_end] 的 mcp_tools 事件数"""
    count = 0
    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for span in data.get("spans", []):
            if span.get("name") != "mcp_tools":
                continue
            sa = span.get("startedAt")
            if not sa:
                continue
            try:
                # startedAt 为 ISO UTC（如 2026-08-22T08:04:28.681Z）→ 转 naive 本地时间
                t = datetime.fromisoformat(sa.replace("Z", "+00:00"))
                t = t.astimezone().replace(tzinfo=None)
            except ValueError:
                continue
            if t_start <= t <= t_end:
                count += 1
    except (json.JSONDecodeError, OSError):
        pass
    return count


def load_server_alias():
    """credit-dictionary 顶层 server_alias 段（--from-transcript 模式判断映射范围）。"""
    try:
        with open(os.path.join(SCRIPT_DIR, "..", "references", "credit-dictionary.json"),
                  "r", encoding="utf-8") as f:
            return json.load(f).get("server_alias", {})
    except Exception:
        return {}


def extract_transcript_mcp_calls(transcript_path: str):
    """从会话留痕提取全部 MCP 调用（--from-transcript 模式）。
    格式自动探测（2026-08-28 Codex 宿主适配）：CC transcript / Codex rollout，
    解析逻辑统一在 scripts/transcript_parsers.py。
    返回 (calls, unmapped)：calls=[{ts, tool, server}]（仅 server_alias 映射内），
    unmapped=[server.tool 原始名]（未映射，不入账但列出供人工裁决）。"""
    alias = load_server_alias()
    import transcript_parsers as tp
    _, calls, _ = tp.parse_auto(transcript_path)
    out, unmapped = [], []
    for c in calls:
        if c.get("server") in alias:
            out.append({"ts": c.get("ts", ""), "server": c["server"], "tool": c["tool"]})
        else:
            unmapped.append(f"{c.get('server')}.{c.get('tool')}")
    return out, unmapped


def parse_ts(s: str):
    """ISO 时间 → naive 本地 datetime（比对用）；失败返回 None。"""
    try:
        t = datetime.fromisoformat(s)
        if t.tzinfo is not None:
            t = t.astimezone().replace(tzinfo=None)
        return t
    except (ValueError, TypeError):
        return None


def check_double_logging(records: list):
    """双记检测（--dedup-hook，默认开）：同 task 内 auto-hook 条目与手动条目（main/sub）
    工具相同且时间差 ≤10s → 疑似双记对。返回疑似对列表 [(hook_seq, manual_seq, tool)]。"""
    auto = [r for r in records if r.get("agent") == "auto-hook"]
    manual = [r for r in records if r.get("agent") in ("main", "sub")]
    pairs = []
    for a in auto:
        ta = parse_ts(a.get("timestamp", ""))
        if ta is None:
            continue
        for m in manual:
            if m.get("tool") != a.get("tool"):
                continue
            tm = parse_ts(m.get("timestamp", ""))
            if tm is not None and abs((ta - tm).total_seconds()) <= 10:
                pairs.append((a.get("seq"), m.get("seq"), a.get("tool")))
                break
    return pairs


def entry_time_candidates(r: dict):
    """一条 usage_log 记录的候选时刻列表：timestamp（记账时刻）+ note 中的 call_ts
    （backfill 条目记录的调用时刻，完整 ISO 含 Z；2026-08-28 补——补记场景两时刻可差很远，
    只比 timestamp 会把补记条目误判为"多记"、调用误判为"漏记"）。"""
    cands = [parse_ts(r.get("timestamp", ""))]
    note = r.get("note") or ""
    if "call_ts=" in note:
        cands.append(parse_ts(note.split("call_ts=")[1].split()[0]))
    return [t for t in cands if t is not None]


def reconcile_with_transcript(task_id: str, transcript_paths, records: list):
    """--from-transcript 模式：transcript MCP 调用清单 vs usage_log 逐条比对（工具名级）。
    transcript_paths 支持多文件（主会话 + subagents/agent-*.jsonl——子agent 调用记录在
    独立文件，hook 记账的 session_id 归主会话，2026-08-28 T2 实测）。
    匹配规则：工具相同且任一候选时刻（timestamp/call_ts）与调用时刻差 ≤10s。"""
    calls, unmapped = [], []
    for tp in transcript_paths:
        c, u = extract_transcript_mcp_calls(tp)
        calls.extend(c)
        unmapped.extend(u)
    used = set()
    matched, missed = [], []
    for c in calls:
        tc = parse_ts(c["ts"])
        hit = None
        for i, r in enumerate(records):
            if i in used or r.get("tool") != c["tool"]:
                continue
            # 单向时序窗口（2026-08-28 T2 实测修正）：transcript 时间戳=调用发起时刻，
            # hook 记账=返回后（长调用如 auto_login 差 50s+），故记账时刻 ∈ [发起-5s, 发起+600s]
            if tc is not None and any(-5 <= (tr - tc).total_seconds() <= 600
                                      for tr in entry_time_candidates(r)):
                hit = i
                break
        if hit is not None:
            used.add(hit)
            matched.append(c)
        else:
            missed.append(c)
    # transcript 有、log 无 = 漏记；log 有、transcript 无 = 多记/跨会话污染
    extra = [r for i, r in enumerate(records) if i not in used]

    print(f"=== 逐调用对账 [--from-transcript] [{task_id}] ===")
    print(f"transcript 映射内调用: {len(calls)} ｜ usage_log 条目: {len(records)} ｜ 匹配: {len(matched)}")
    if unmapped:
        uniq = sorted(set(unmapped))
        print(f"未映射 server 调用: {len(unmapped)}（{len(uniq)} 种，不入账属预期）：{', '.join(uniq[:6])}"
              f"{' ...' if len(uniq) > 6 else ''}")
    if missed:
        print(f"\n⚠️ transcript 有、log 无（疑似漏记 {len(missed)} 条）：")
        for c in missed:
            print(f"  {c['ts'][:19]} {c['server']}.{c['tool']}")
        print("  → 可用 scripts/hooks/backfill_from_transcript.py 补记")
    if extra:
        print(f"\n⚠️ log 有、transcript 无（{len(extra)} 条，可能是跨会话 task_id 复用或手动多记）：")
        for r in extra:
            print(f"  #{r.get('seq')} {r.get('mcp')}.{r.get('tool')} agent={r.get('agent')}")
    if args_dedup_enabled():
        pairs = check_double_logging(records)
        if pairs:
            print(f"\n⚠️ 疑似手动/自动双记 {len(pairs)} 对（同工具±10s）：{pairs}")

    ok = not missed and not extra
    print(f"\n{'✅ 逐调用一致' if ok else '⚠️ 存在差异（见上）'}")
    return 0 if ok else 1


def args_dedup_enabled():
    """--dedup-hook 当前值（main 的 args 全局暂存，避免长参数传递）。"""
    return _ARGS.get("dedup_hook", True)


_ARGS = {}


def main():
    parser = argparse.ArgumentParser(description="usage_log vs traces/transcript 对账")
    parser.add_argument("--task-id", default=None,
                        help="要对账的任务ID；--from-transcript 模式缺省取 transcript 文件名（session_id）")
    parser.add_argument("--from-transcript", nargs="+", default=None, metavar="PATH",
                        help="会话留痕 jsonl 路径（可多个）：逐调用对账（工具名级，2026-08-28 hook 轮新增；"
                             "格式自动探测——CC transcript 与 Codex rollout 均支持，2026-08-28 Codex 适配）。"
                             "含子agent 任务时传主留痕 + 子agent 留痕文件"
                             "（CC：主 transcript + <session>/subagents/agent-*.jsonl；"
                             "Codex：主 rollout + 同日期目录下子 agent rollout 文件）")
    parser.add_argument("--dedup-hook", action=argparse.BooleanOptionalAction, default=True,
                        help="检测手动/自动记账双记（同工具±10s，默认开）")
    parser.add_argument("--show-log", action="store_true", help="同时打印日志明细")
    parser.add_argument("--traces-dir", default=DEFAULT_TRACES, help="traces根目录")
    parser.add_argument("--since-minutes", type=int, default=60,
                        help="只统计最近N分钟的traces（默认60，避免旧任务干扰）")
    parser.add_argument("--by-log-window", action="store_true",
                        help="按 usage_log 该 task_id 首/末条记录时间窗过滤 traces（推荐，自动排除跨任务干扰）")
    parser.add_argument("--margin-minutes", type=int, default=3,
                        help="--by-log-window 模式下窗口外扩分钟数（默认3）")
    args = parser.parse_args()
    _ARGS["dedup_hook"] = args.dedup_hook

    # --from-transcript 模式：逐调用对账（工具名级），不走 traces 计数链路
    if args.from_transcript:
        for p in args.from_transcript:
            if not os.path.isfile(p):
                print(f"⛔ transcript 不存在: {p}", file=sys.stderr)
                return 1
        task_id = args.task_id or os.path.splitext(os.path.basename(args.from_transcript[0]))[0]
        return reconcile_with_transcript(task_id, args.from_transcript, load_usage_log(task_id))
    if not args.task_id:
        parser.error("--task-id 必填（--from-transcript 模式可省略）")

    # 1. 日志条数（cost=null = cost_known:false 未知成本条目，2026-08-28 立不计入积分汇总）
    records = load_usage_log(args.task_id)
    log_count = len(records)
    log_cost = sum((r.get("cost") or 0) for r in records)
    unknown_cost_cnt = sum(1 for r in records if r.get("cost") is None)
    log_errors = sum(1 for r in records if r.get("result") == "error")

    # 2. traces 事件数
    window_desc = f"近{args.since_minutes}分钟"
    probe_start = datetime.now() - timedelta(minutes=args.since_minutes)  # 探测窗口起点（与对账窗口对齐后覆盖）
    if args.by_log_window:
        if not records:
            print(f"usage_log 无 [{args.task_id}] 记录，无法按日志窗口过滤——改用时间窗口模式")
            since = datetime.now() - timedelta(minutes=args.since_minutes)
            trace_count = count_traces_mcp_events(args.traces_dir, since)
        else:
            ts = []
            for r in records:
                try:
                    t = datetime.fromisoformat(r["timestamp"])
                except (KeyError, ValueError):
                    continue
                # 统一转 naive 本地时间（os.path.getmtime 返回 naive，混比会 TypeError）
                if t.tzinfo is not None:
                    t = t.astimezone().replace(tzinfo=None)
                ts.append(t)
            if not ts:
                print("⚠️ 日志记录无有效 timestamp，退回时间窗口模式")
                since = datetime.now() - timedelta(minutes=args.since_minutes)
                trace_count = count_traces_mcp_events(args.traces_dir, since)
            else:
                margin = timedelta(minutes=args.margin_minutes)
                t_start = min(ts) - margin
                t_end = max(ts) + margin
                # mtime 早于 start 说明文件未被本任务触碰，排除；晚于 end+少量余量同理
                trace_count = count_traces_mcp_events_window(args.traces_dir, t_start, t_end + margin)
                window_desc = f"日志窗口 {t_start.strftime('%H:%M')}~{t_end.strftime('%H:%M')}（±{args.margin_minutes}min）"
                probe_start = t_start  # 探测窗口与对账窗口对齐（trace 落盘晚于调用，探测内部再放宽 24h）
    else:
        since = datetime.now() - timedelta(minutes=args.since_minutes)
        trace_count = count_traces_mcp_events(args.traces_dir, since)

    # 3. 汇总
    print(f"=== 对账 [{args.task_id}] ===")
    print(f"usage_log 记录数 : {log_count}（成功{log_count - log_errors} 失败{log_errors}）")
    print(f"usage_log 累计成本: {log_cost}")
    if unknown_cost_cnt:
        print(f"未知成本记录 : {unknown_cost_cnt} 条（cost_known=false，不参与积分对账）")
    if args.dedup_hook:
        pairs = check_double_logging(records)
        if pairs:
            print(f"⚠️ 疑似手动/自动双记 {len(pairs)} 对（同工具±10s）：{pairs}——装 hook 宿主应免手动记账")

    # 3.5 traces 结构探测降级（2026-08-27 立，abtest-F1-20260827 P6）：
    # 宿主 traces 计数口径不适用时（目录缺失/无 trace 文件/结构不符），不报"差异 N"
    # 误导人工归因——直接输出降级结论，usage_log 为权威记录（exit code=2 区别于一致/差异）
    since_probe = probe_start
    structure_ok, scanned = probe_traces_structure(args.traces_dir, since_probe)
    if not structure_ok:
        print(f"traces 对账降级 : 宿主 traces 计数口径不适用（扫描 {scanned} 个 trace 文件，"
              f"无 {{\"spans\":[{{\"name\":\"mcp_tools\"}}]}} 结构）")
        print("→ 跳过计数对账，usage_log 为权威记录；如需余额级核对请查服务商后台")
        if args.show_log:
            print("\n--- usage_log 明细 ---")
            for r in records:
                cost_disp = "?" if r.get("cost") is None else r["cost"]
                print(f"  #{r['seq']} {r['mcp']}.{r['tool']} cost={cost_disp} "
                      f"result={r['result']} has_content={r.get('result_has_content')} "
                      f"return={r.get('return_count')} total={r.get('total_count')}")
        print("\n⏭️ 降级跳过（非差异，非一致）")
        return 2

    print(f"traces mcp_tools事件数: {trace_count}（{window_desc}）")
    print(f"差异: {abs(log_count - trace_count)}")

    if args.show_log:
        print("\n--- usage_log 明细 ---")
        for r in records:
            cost_disp = "?" if r.get("cost") is None else r["cost"]
            print(f"  #{r['seq']} {r['mcp']}.{r['tool']} cost={cost_disp} "
                  f"result={r['result']} has_content={r.get('result_has_content')} "
                  f"return={r.get('return_count')} total={r.get('total_count')}")

    if log_count == trace_count:
        print("\n✅ 一致")
        return 0
    else:
        print("\n⚠️ 差异——可能原因：")
        print("  1. traces含其他任务事件（跨任务干扰）→ 用 --by-log-window 按任务时间窗过滤，或缩小 --since-minutes")
        print("  2. 子agent漏记日志（traces>日志）→ 与子agent核实补记")
        print("  3. 子agent擅自重试但未记日志 → 与子agent核实后上报用户")
        print("  4. 日志记账档位与余额实扣不符 → 先核对 cost 是否等于 credit-dictionary 档位（test-run-20260821 教训）")
        # 漏记定位辅助（2026-08-27 立，retest-C2 教训：13 次调用漏记 1 条靠人工数 jsonl 才发现）：
        # traces 只有计数无工具名，无法精确指认漏记条目；按"子agent 汇报次数 vs 记账条数"提示人工比对锚点
        if trace_count > log_count:
            print(f"\n  🔍 漏记定位辅助（traces>{log_count}，疑似漏记 {trace_count - log_count} 条）：")
            print("     traces 无工具名无法精确指认——请主agent 对照子agent 各步骤汇报中的调用次数，")
            print("     与上方 usage_log 明细逐环节比对，差集环节即漏记处（retest-C2：seq 4-6 少 1 条 ft_detail）。")
            print("     建议：要求子agent 步骤汇报末尾附'本阶段调用次数=记账条数'自查行（F1 骨架③已内置）。")
        print("\n  ℹ️ 口径固定（2026-08-27 立）：CC 宿主的子agent/主agent 直调不入 WorkBuddy traces，"
              "此类差异属预期局限，勿当漏记追查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
