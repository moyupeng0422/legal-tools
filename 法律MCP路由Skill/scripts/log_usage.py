#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
log_usage.py — 调用成本日志写入脚本（CLI 手动记账 + hook 自动记账共用写入通道）

按 credit-model.md 2.1 的 18 字段 schema，向 data/mcp_usage_log.jsonl 追加一行。
每次 MCP 调用后立即执行（含失败调用——失败也消耗额度）。
2026-08-28 hook 自动记账轮：写入逻辑抽为 write_entry()（hooks/auto_log_hook.py 与
backfill_from_transcript.py import 复用，单一写入通道）；CLI 行为完全不变。

用法（CLI）：
  python scripts/log_usage.py --task-id task-001 --scene A2 --function f5 \
      --mcp pkulaw --tool get_case_list --params "title=租赁合同 caseGrade=[指导性案例]" \
      --cost 25 --quota-type recurring --result ok --has-content true \
      --return-count 10 --total-count 237 --agent sub

  # 失败调用：--result error --error-type 400
  python scripts/log_usage.py --task-id task-001 --scene A2 --function f5 \
      --mcp pkulaw --tool get_article --cost 125 --quota-type recurring \
      --result error --error-type 400 --retry-count 1 --agent sub

  # 未知成本（知识库外MCP，profile cost_known:false）：--cost-unknown 记 cost=null
  python scripts/log_usage.py --task-id task-001 --scene X1 --function f2 \
      --mcp some-local-mcp --tool search --cost-unknown --quota-type recurring \
      --result ok --has-content true --return-count 5 --agent sub

注意事项：
  - seq 自动从日志文件最后一行 +1（每任务从1递增，task_id 改变时从1重新计数）
  - params_summary 只记关键参数摘要（脱敏），禁止记录完整入参/API Key/Cookie/Token
  - 不记录完整返回内容，只记 result_has_content/return_count/total_count 元数据
  - 日志路径可用环境变量 LOG_USAGE_PATH 覆盖默认路径（2026-08-28 Codex 宿主适配）；
    主本 PermissionError/OSError 时自动降级写系统临时目录（note 加 fallback-log 标记），
    输出显式警示——此时管控报告须标注"对账未完成（主本不可写）"
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime

# Windows GBK 终端 emoji 编码修复（P0，CC审核2026-08-13）
# 不加此块：print("✅ ...") 在 GBK 终端崩 UnicodeEncodeError → exit code=1
# → 写入实际成功但调用方（子agent）误判"记录失败"而重试/上报
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 日志路径（脚本位于 scripts/ 下，日志在 ../data/）
# 环境变量 LOG_USAGE_PATH 可覆盖（2026-08-28 Codex 宿主适配：宿主沙箱对 skill 主本
# 目录无写权限时，把日志引到宿主可写位置，对账通道不断）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.environ.get("LOG_USAGE_PATH") or os.path.join(SCRIPT_DIR, "..", "data", "mcp_usage_log.jsonl")
# 降级日志（主本不可写时的兜底落点：系统临时目录，稳定路径便于事后迁移/对账）
FALLBACK_LOG_PATH = os.path.join(tempfile.gettempdir(), "legal-mcp-router-usage-log.jsonl")
# 档位字典（test-run-20260821 审查修正：qwal/ptal 曾按 10 分记，实为 5 分——
# cost 由调用方自由传值无校验是根因，故加档位白名单校验）
CREDIT_DICT_PATH = os.path.join(SCRIPT_DIR, "..", "references", "credit-dictionary.json")


def load_tier_table():
    """从 credit-dictionary 加载 档位白名单 {tool_name: cost} 与 {mcp_key: default_cost}。
    字典缺失/损坏时返回 None（降级为不校验，不阻塞记账——校验失败比漏记更危险的方向是漏记）。"""
    try:
        with open(CREDIT_DICT_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        tiers = {}
        defaults = {}
        for key, mcp in d.get("mcp", {}).items():
            defaults[key] = mcp.get("default_cost", 0)
            for tool, cost in (mcp.get("tools") or {}).items():
                tiers[tool] = cost
        return tiers, defaults
    except Exception:
        return None, None


def resolve_tool_tier(tiers: dict, mcp: str, tool: str):
    """按三形态解析工具档位（2026-08-27 N5 修复：裸名掉 default 漏洞）：
    ① 原名精确 → ② mcp前缀补全（rh_ft_detail→yuandian_rh_ft_detail）→ ③ 去前缀（yuandian_rh_ft_detail→rh_ft_detail）。
    三形态均未命中返回 None（才允许回退 default_cost）。"""
    for cand in (tool, f"{mcp}_{tool}", tool.split(f"{mcp}_", 1)[-1] if f"{mcp}_" in tool else None):
        if cand and cand in tiers:
            return tiers[cand]
    return None


def check_cost_tier(mcp: str, tool: str, cost):
    """档位白名单校验：cost 必须等于 credit-dictionary 中该工具的档位
    （三形态均未列出时才用所属 MCP 的 default_cost——N5 教训：裸名查不到静默回退 default，
    会放行错档位，如 rh_ft_detail 记 5 分过校验）。
    cost 为 None（cost_known=false 未知成本标记，2026-08-28 立）→ 直接放行不参与档位比较。
    返回 (ok: bool, expected: int|None, matched_tier: bool)。"""
    if cost is None:
        return True, None, False
    tiers, defaults = load_tier_table()
    if tiers is None:
        return True, None, False  # 字典不可用 → 降级放行（校验失败不应阻塞记账）
    expected = resolve_tool_tier(tiers, mcp, tool)
    if expected is None:
        expected = defaults.get(mcp)
    if expected is None:
        # 字典未收录（知识库外 MCP/工具，走通用模式）→ 放行
        return True, None, False
    return cost == expected, expected, True

# 18 字段 schema（与 credit-model.md 2.1 对齐，顺序固定便于比对）
FIELDS = [
    "timestamp", "task_id", "seq", "scene_id", "function_id",
    "mcp", "tool", "params_summary", "cost", "quota_type",
    "result", "result_has_content", "return_count", "total_count",
    "error_type", "retry_count", "agent", "note",
]


def now_iso():
    """当前时间 ISO 8601 + 时区"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def next_seq(task_id: str, log_path: str = LOG_PATH) -> int:
    """同一 task_id 的调用序号：从日志末尾找到该任务的最后 seq，+1；
    新任务从 1 开始。
    同时扫描降级日志（2026-08-28）：主本不可写期间条目落在 FALLBACK_LOG_PATH，
    只扫主本会 seq 恒为 1，故取双路径最大值。"""
    max_seq = 0
    for path in (log_path, FALLBACK_LOG_PATH):
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("task_id") == task_id and isinstance(rec.get("seq"), int):
                    max_seq = max(max_seq, rec["seq"])
    return max_seq + 1


def write_entry(entry: dict, log_path: str = LOG_PATH, params_required: bool = True):
    """写入一条 18 字段记录（CLI 与 hook 共用单一写入通道，2026-08-28 hook 自动记账轮抽出）。

    entry 为 dict，必填：task_id/mcp/tool/quota_type/result/agent；cost 必填但可为 None
    （cost_known:false 未知成本标记，跳过档位校验，由调用方在 note 自标 cost-unknown/cost-unknown 类标记）；
    可缺省自动补全：timestamp（now）、seq（按 task_id 递增）、其余字段填 None。
    params_required：CLI=True（空 params 拒绝，沿用占位守卫）；hook 形态传 False
    （真实调用可能无参数，如 check_token input={}），占位标记（TEST_PROBE 等）两种形态都拒绝。

    返回 (ok: bool, msg: str)——不抛异常、不 sys.exit（调用方自行决定退出码）。"""
    try:
        # 1. error 必填 error_type
        if entry.get("result") == "error" and not entry.get("error_type"):
            return False, "result=error 时必须提供 error_type"

        # 2. params 守卫（占位标记两形态都拒；空 params 仅 CLI 形态拒）
        params = entry.get("params_summary") or ""
        if any(m in params for m in _PLACEHOLDER_MARKERS):
            return False, "params_summary 含占位标记（TEST_PROBE 等），拒绝写入"
        if params_required and not params.strip():
            return False, "params_summary 为空，拒绝写入"

        # 3. 档位白名单校验（命中档位表且不匹配 → 拒绝；未收录/字典不可用 → 放行）
        cost = entry.get("cost")
        cost_ok, expected, matched = check_cost_tier(entry["mcp"], entry["tool"], cost)
        if matched and not cost_ok:
            return False, (f"档位校验失败：{entry['mcp']}.{entry['tool']} 字典档位={expected} 分，"
                           f"传入 cost={cost} 分——请核对 credit-dictionary 后重记（禁止凭记忆估档）")

        # 4. seq/timestamp 补全 + 18 字段定序
        task_id = entry.get("task_id")
        entry.setdefault("timestamp", now_iso())
        entry["seq"] = next_seq(task_id, log_path)
        record = {f: entry.get(f) for f in FIELDS}
        record["result_has_content"] = bool(record.get("result_has_content"))

        # 5. 追加写入（2026-08-28 Codex 宿主适配：主本 PermissionError/OSError →
        #    降级写系统临时目录，防整条记录丢失；note 加 fallback-log 标记自识别）
        target = log_path
        fallback_used = False
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except (PermissionError, NotADirectoryError, OSError):
            target = FALLBACK_LOG_PATH
            fallback_used = True
            os.makedirs(os.path.dirname(target), exist_ok=True)
            record["note"] = f"{record.get('note') or ''} fallback-log".strip()
            with open(target, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        msg = (f"已记录 [{task_id} #{entry['seq']}] {entry['mcp']}.{entry['tool']} "
               f"cost={cost} {entry.get('quota_type')} result={entry.get('result')}"
               + ("（档位校验✓）" if matched else ""))
        if fallback_used:
            msg += (f"\n⚠️ 主本日志不可写（权限受限），已降级写入 {target}"
                    f"——管控报告须标注「对账未完成（主本不可写）」，事后可用 backfill 迁回主本")
        return True, msg
    except Exception as e:  # hook 旁路调用时任何异常都不应向上传播为崩溃
        return False, f"write_entry 异常: {e}"


# 占位标记守卫（防 TEST_PROBE 类调试残留污染正式日志，CC P1-3）
_PLACEHOLDER_MARKERS = ("TEST_PROBE", "PROBE", "test probe", "占位")


def main():
    parser = argparse.ArgumentParser(description="写入一条MCP调用成本日志")
    parser.add_argument("--task-id", required=True, help="本次检索任务唯一ID（如 task-001）")
    parser.add_argument("--scene", required=True, help="L2场景ID（如 A2）；hook 场景可传空串")
    parser.add_argument("--function", required=True, help="功能编号（f1-f9）；hook 场景可传空串")
    parser.add_argument("--mcp", required=True, help="MCP标识（credit-dictionary的key）")
    parser.add_argument("--tool", required=True, help="工具名（MCP实际调用名）")
    parser.add_argument("--params", default="", help="参数摘要（脱敏，关键参数名+值）")
    parser.add_argument("--cost", type=int, default=None,
                        help="本次消耗（积分/次/0；威科按次；整数）；未知成本MCP改用 --cost-unknown")
    parser.add_argument("--cost-unknown", action="store_true",
                        help="未知成本标记（profile cost_known:false 的知识库外MCP）：记 cost=null+note，不参与积分对账；与 --cost 互斥")
    parser.add_argument("--quota-type", required=True,
                        choices=["infinite", "recurring", "free_trial", "one_time"],
                        help="额度池类型")
    parser.add_argument("--result", required=True, choices=["ok", "empty", "error"],
                        help="调用结果")
    parser.add_argument("--has-content", type=str, default="false",
                        help="返回是否有内容（true/false，默认false）")
    parser.add_argument("--return-count", type=int, default=0, help="本次返回条数")
    parser.add_argument("--total-count", type=int, default=None, help="总命中数（无则省略）")
    parser.add_argument("--error-type", default=None,
                        help="错误分类：401/400/timeout/其他（result=error时必填）")
    parser.add_argument("--retry-count", type=int, default=0,
                        help="该工具本次任务内已重试次数（≤2）")
    parser.add_argument("--agent", default="sub", choices=["main", "sub", "auto-hook", "backfill"],
                        help="调用主体（auto-hook=PostToolUse hook 自动记账；backfill=transcript 离线补记）")
    parser.add_argument("--note", default=None, help="备注（升级来源/坑位命中等）")
    args = parser.parse_args()

    # cost 互斥校验：--cost 与 --cost-unknown 二选一（都传或都不传均拒，防漏传静默 None）
    if args.cost is not None and args.cost_unknown:
        print("⛔ --cost 与 --cost-unknown 互斥，二选一", file=sys.stderr)
        sys.exit(1)
    if args.cost is None and not args.cost_unknown:
        print("⛔ 缺少成本：已知档位传 --cost N；未知成本（profile cost_known:false）传 --cost-unknown", file=sys.stderr)
        sys.exit(1)

    note = args.note
    if args.cost_unknown:
        note = f"{note} cost-unknown".strip() if note else "cost-unknown"

    entry = {
        "task_id": args.task_id,
        "scene_id": args.scene,
        "function_id": args.function,
        "mcp": args.mcp,
        "tool": args.tool,
        "params_summary": args.params,
        "cost": args.cost,
        "quota_type": args.quota_type,
        "result": args.result,
        "result_has_content": str(args.has_content).lower() in ("true", "1", "yes"),
        "return_count": args.return_count,
        "total_count": args.total_count,
        "error_type": args.error_type,
        "retry_count": args.retry_count,
        "agent": args.agent,
        "note": note,
    }
    ok, msg = write_entry(entry)
    if ok:
        print(f"✅ {msg}")
    else:
        print(f"⛔ {msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
