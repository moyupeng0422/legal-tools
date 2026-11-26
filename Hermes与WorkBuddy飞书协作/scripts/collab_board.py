#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collab_board.py v2 — 协作任务看板（append-only jsonl 事件流 + 单写者派生）
架构（2026-11-22 三方评审第二批，用户拍板）：
  - 存储改 append-only jsonl 事件流（board_events.jsonl）：并发天然安全（追加原子性）、
    崩溃恢复=重放、完整审计链（migrate_manifest 同模式）
  - 状态视图 collab_board.json 由事件流重放派生（派生文件可随时重建，不信任其内容）
  - 单写者原则：本地 agent（芭迪）零双写——状态由 Hermes 哨兵从 conv_inbox 落盘/
    CC DONE 事件派生；本 CLI 仅 Hermes 使用
  - conclusion 字段：区分 outcome（result=成功/失败）与 process（stalled=运行停滞）

状态机（v2 九态）:
  dispatched → working → waiting_review → done → closed
                  ↘ need_approval → (approved→working / rejected→closed)
  paused / blocked（不计停滞）  failed（带 conclusion=result）

事件类型（jsonl 每行一事件）:
  task_registered / state_changed / heartbeat / note_added / gc_compacted

用法:
  collab_board.py add <task_id> <target> [--step N] [--prio P0-P3] [--note ...]
  collab_board.py update <task_id> <state> [--step N] [--conclusion stalled|result_pass|result_fail] [--note ...]
  collab_board.py heartbeat <task_id>                        # 心跳（不计停滞基线偏移，仅记录活跃）
  collab_board.py show [--state S]
  collab_board.py brief                                      # 待办摘要（含 STALLED/CONCLUSION）
  collab_board.py rebuild                                    # 从事件流重建派生视图
  collab_board.py gc [--days 7]                              # 事件流压实（closed 超期合并为快照行）
"""
import json, os, sys, argparse, datetime, tempfile

HERMES_DIR = os.path.expanduser("~/.hermes")
EVENTS = os.path.join(HERMES_DIR, "board_events.jsonl")
VIEW = os.path.join(HERMES_DIR, "collab_board.json")          # 派生视图（兼容旧读取方）
STATES = ["dispatched", "working", "need_approval", "waiting_review", "paused", "blocked", "done", "failed", "closed"]
CONCLUSIONS = ["stalled", "result_pass", "result_fail", ""]
# STALL 规则 v2（只提醒绝不改状态；心跳与状态转移分离）
STALL_RULES = {
    "dispatched": 300,        # visible-timeout：派发5min未ACK → 提醒检查唤醒链路
    "working": 900,           # 执行15min无事件 → 疑似卡住
    "need_approval": 1800,    # 待批30min → 提醒催办
}
NO_STALL_STATES = {"paused", "blocked", "waiting_review", "done", "failed", "closed"}

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")

def append_event(evt):
    """append-only：追加一行事件（原子性天然好于覆盖写）。并发安全靠 O_APPEND。"""
    evt["ts"] = now()
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")

def replay():
    """事件流重放 → 派生状态视图（崩溃恢复=重放）。"""
    tasks = {}
    if not os.path.exists(EVENTS):
        return {"tasks": tasks, "updated": None}
    with open(EVENTS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue  # 半行（断电尾部截断）跳过——append-only 的崩溃恢复优势
            tid = e.get("task_id")
            et = e.get("event")
            if et == "task_registered":
                tasks[tid] = {"target": e["target"], "step": e.get("step", 1),
                              "state": "dispatched", "prio": e.get("prio", "P2"),
                              "conclusion": "", "note": e.get("note", ""),
                              "issued_at": e["ts"], "updated_at": e["ts"],
                              "last_heartbeat": e["ts"], "last_activity": e["ts"]}
            elif et == "task_snapshot":
                tasks[tid] = {"target": e.get("target",""), "step": 0,
                              "state": e.get("state","closed"), "prio": "P2",
                              "conclusion": e.get("conclusion",""), "note": "(archived)",
                              "issued_at": e.get("issued_at",""), "updated_at": e.get("archived_at", now()),
                              "last_heartbeat": e.get("archived_at", now())}
            elif tid in tasks:
                if et == "state_changed":
                    t = tasks[tid]
                    t["state"] = e["state"]
                    if e.get("step") is not None: t["step"] = e["step"]
                    if e.get("conclusion"): t["conclusion"] = e["conclusion"]
                    if e.get("note"): t["note"] = e["note"]
                    t["updated_at"] = e["ts"]
                    t["last_activity"] = e["ts"]  # STALL 基线（心跳分离：只有状态转移刷新）
                elif et == "heartbeat":
                    tasks[tid]["last_heartbeat"] = e["ts"]
                    tasks[tid]["last_activity"] = e["ts"]
                elif et == "note_added":
                    tasks[tid]["note"] = e.get("note", tasks[tid]["note"])
                    tasks[tid]["updated_at"] = e["ts"]
    return {"tasks": tasks, "updated": now()}

def sync_view(b):
    """派生视图落盘（原子写，兼容旧读取方；内容可由 rebuild 随时重建）。"""
    b["updated"] = now()
    fd, tmp = tempfile.mkstemp(dir=HERMES_DIR, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=1)
    os.replace(tmp, VIEW)

def board():
    b = replay()
    sync_view(b)
    return b

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("task_id"); p.add_argument("target")
    p.add_argument("--step", type=int, default=1)
    p.add_argument("--prio", default="P2", choices=["P0", "P1", "P2", "P3"])
    p.add_argument("--note", default="")
    p = sub.add_parser("update")
    p.add_argument("task_id"); p.add_argument("state", choices=STATES)
    p.add_argument("--step", type=int, default=None)
    p.add_argument("--conclusion", default="", choices=CONCLUSIONS)
    p.add_argument("--note", default=None)
    p = sub.add_parser("heartbeat"); p.add_argument("task_id")
    p = sub.add_parser("show"); p.add_argument("--state", default=None)
    sub.add_parser("brief"); sub.add_parser("rebuild")
    p = sub.add_parser("gc"); p.add_argument("--days", type=int, default=7)
    a = ap.parse_args()

    if a.cmd == "add":
        b = replay()
        if a.task_id in b["tasks"]:
            print(f"UPDATE: {a.task_id} 已存在（幂等保留）"); return
        append_event({"event": "task_registered", "task_id": a.task_id,
                      "target": a.target, "step": a.step, "prio": a.prio, "note": a.note})
        print(f"ADD_OK: {a.task_id} → {a.target} dispatched (prio={a.prio})")
        return

    if a.cmd == "update":
        b = replay()
        if a.task_id not in b["tasks"]:
            print(f"FAIL: {a.task_id} 不存在"); sys.exit(1)
        # ── v1.6d 硬闸门 P0：closed 前检查在途回执（pending_receipts.jsonl）──
        if a.state == "closed":
            pr_path = os.path.join(HERMES_DIR, "pending_receipts.jsonl")
            pending = []
            if os.path.exists(pr_path):
                with open(pr_path, encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split("|")
                        # v1.7 五字段新格式 target|task|step|msg|ts；兼容旧四字段 task|step|msg|ts
                        if len(parts) >= 5:
                            row_task = parts[1]
                        else:
                            row_task = parts[0] if parts else ""
                        if row_task == a.task_id:
                            pending.append(parts[2] if len(parts) >= 5 else (parts[1] if len(parts) >= 2 else "?"))
            if pending:
                if not (a.note and "force-closed" in a.note):
                    print(f"BLOCKED: {a.task_id} 有 {len(pending)} 条在途回执未核销 "
                          f"(step: {','.join(sorted(set(pending)))})。"
                          f"对方 [state:] 回执核销前禁止收口；"
                          f"确要强制收口请 --note 'force-closed <理由>'（理由落事件流审计）")
                    sys.exit(2)
        evt = {"event": "state_changed", "task_id": a.task_id, "state": a.state,
               "conclusion": a.conclusion, "note": a.note or ""}
        if a.step is not None: evt["step"] = a.step
        append_event(evt)
        # closed 成功 → 清理该任务的 pending 回执记录
        if a.state == "closed":
            pr_path = os.path.join(HERMES_DIR, "pending_receipts.jsonl")
            if os.path.exists(pr_path):
                with open(pr_path, encoding="utf-8") as f:
                    def _row_task(l):
                        ps = l.strip().split("|")
                        return ps[1] if len(ps) >= 5 else (ps[0] if ps else "")
                    kept = [l for l in f if _row_task(l) != a.task_id]
                fd, tmp = tempfile.mkstemp(dir=HERMES_DIR, suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.writelines(kept)
                os.replace(tmp, pr_path)
        print(f"UPDATE_OK: {a.task_id} → {a.state}" + (f" [{a.conclusion}]" if a.conclusion else ""))
        return

    if a.cmd == "heartbeat":
        append_event({"event": "heartbeat", "task_id": a.task_id})
        print(f"HB_OK: {a.task_id}")
        return

    if a.cmd == "rebuild":
        b = replay(); sync_view(b)
        print(f"REBUILD_OK: {len(b['tasks'])} tasks 从事件流派生")

    if a.cmd == "show":
        b = board()
        for tid, t in sorted(b["tasks"].items(), key=lambda kv: (kv[1].get("prio","P2"), kv[0])):
            if a.state and t["state"] != a.state: continue
            c = f" [{t['conclusion']}]" if t.get("conclusion") else ""
            print(f"{tid:38s} {t['target']:6s} {t.get('prio','P2')} step{t['step']:<3} {t['state']:14s}{c} {t['updated_at'][:16]} {t['note'][:36]}")
        return

    if a.cmd == "brief":
        b = board()
        groups = {s: [] for s in STATES}
        for tid, t in b["tasks"].items():
            if t["state"] != "closed":
                groups[t["state"]].append((tid, t))
        stalled, out = [], []
        now_dt = datetime.datetime.now()
        for s in ["need_approval", "waiting_review", "failed", "dispatched", "working", "paused", "blocked", "done"]:
            for tid, t in sorted(groups[s], key=lambda kv: kv[1].get("prio", "P2")):
                c = f" [{t['conclusion']}]" if t.get("conclusion") else ""
                out.append(f"[{s}]{c} {tid} → {t['target']} step{t['step']} {t['note'][:30]}")
                threshold = STALL_RULES.get(s)
                if threshold:
                    # STALL 基线=last_activity（最后一次状态转移/心跳，不含 registered）
                    base = t.get("last_activity", t["updated_at"])
                    base_dt = datetime.datetime.fromisoformat(base)
                    mins = (now_dt - base_dt).total_seconds() / 60
                    if mins * 60 > threshold:
                        stalled.append(f"[STALL] {tid} ({s}) 已停滞 {int(mins)} 分钟 → 核查卡住/唤醒失败/需催办（只提醒不改状态）")
        if stalled:
            print("⚠ STALLED DETECTED [板催办·非新任务]:")
            print("\n".join(stalled)); print("---")
        if not out:
            print("BOARD_CLEAN: 无待办任务")
        else:
            print(f"BOARD: {len(out)} 项未收口")
            print("\n".join(out))
        return

    if a.cmd == "gc":
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=a.days)).isoformat()
        b = replay()
        # 压实 v2（修：直接删 closed 事件会使任务"复活"为旧状态——重放缺终态）。
        # 正确做法：超期 closed 任务的全部事件 → 替换为单行终态快照（保审计摘要+终态语义）
        kept, compacted, snapshots = [], 0, []
        seen = set()
        with open(EVENTS, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        for line in lines:
            try: e = json.loads(line)
            except: kept.append(line); continue
            tid = e.get("task_id")
            t = b["tasks"].get(tid)
            if (t and t["state"] == "closed" and t["updated_at"] < cutoff
                    and e.get("event") == "state_changed" and e["state"] == "closed"):
                compacted += 1
                if tid not in seen:
                    seen.add(tid)
                    kept.append(json.dumps({"event": "task_snapshot", "task_id": tid,
                        "state": "closed", "target": t["target"], "conclusion": t.get("conclusion",""),
                        "issued_at": t["issued_at"], "archived_at": now()}, ensure_ascii=False))
                continue
            kept.append(line)
        fd, tmp = tempfile.mkstemp(dir=HERMES_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n")
        os.replace(tmp, EVENTS)
        # 快照事件需要在 replay() 识别——刷新派生视图
        print(f"GC: 压实 {compacted} 条事件为 {len(seen)} 份终态快照")

if __name__ == "__main__":
    main()
