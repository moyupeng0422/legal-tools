#!/usr/bin/env bash
# hermes-post-task.sh — 醒后任务收尾两段式脚本（v1.0, 2026-11-23）
#
# R9 裁决：聚合机械操作、保留判断闸门。
#   verify 段：SSH 拉产出 + 机械校验 + conv 就位确认 → 输出结构化材料后停（LLM 读材料做验收判断）
#   close  段：LLM 判断后调用。pass → closed+归档确认；fail → exception 转异常流程
#              SSH 断场景用 close --unverified（completed-unverified 入队，不闭环）
#
# 用法：
#   hermes-post-task.sh verify  -TaskId <id> -RemotePath <产出路径> [-ExpectFiles "a,b,c"]
#   hermes-post-task.sh close   -TaskId <id> -Verdict pass|fail [-Notes "..."]
#   hermes-post-task.sh close   -TaskId <id> --unverified -Notes "SSH断"
#   hermes-post-task.sh brief                          # 全板结构化快照
set -uo pipefail

BOARD="$HOME/.hermes/collab_board.json"
WIN_CONV_DIR='D:\<projects-root>\collab\hermes-badi\conv'
CLOUD_CONV_DIR="$HOME/hermes_collab/conv_inbox"
LOCK="$BOARD.lock"

die() { echo "ERROR: $*" >&2; exit 2; }

board_update() {
    # $1=task_id  $2=python更新代码（对 t 变量操作）
    flock "$LOCK" python3 - "$1" "$2" <<'PYEOF'
import json, sys, os, tempfile
task_id, code = sys.argv[1], sys.argv[2]
p = os.path.expanduser("~/.hermes/collab_board.json")
d = json.load(open(p))
t = d["tasks"].get(task_id)
if not t:
    print(f"ERROR: task {task_id} 不在看板"); sys.exit(1)
exec(code)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p))
with os.fdopen(fd, "w") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
os.replace(tmp, p)
print("BOARD_UPDATED")
PYEOF
}

cmd="${1:-}"; shift || true
case "$cmd" in
verify)
    TASK_ID="" ; REMOTE="" ; EXPECT=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -TaskId) TASK_ID="$2"; shift 2;;
            -RemotePath) REMOTE="$2"; shift 2;;
            -ExpectFiles) EXPECT="$2"; shift 2;;
            *) die "verify 未知参数 $1";;
        esac
    done
    [[ -z "$TASK_ID" || -z "$REMOTE" ]] && die "verify 需要 -TaskId -RemotePath"

    echo "=== POST-TASK VERIFY: $TASK_ID ==="
    # 1. conv 就位确认（云端 conv_inbox 应有该任务的推送）
    CONV_HITS=$(ls "$CLOUD_CONV_DIR" 2>/dev/null | grep -i "$TASK_ID" | head -3)
    if [[ -n "$CONV_HITS" ]]; then
        echo "CONV: ✅ $CONV_HITS"
    else
        echo "CONV: ❌ 云端 conv_inbox 无该任务文件（推送缺席，可能需催芭迪重推）"
    fi

    # 2. 产出存在性校验（SSH）
    SSH_OUT=$(ssh -o ConnectTimeout=10 -p 2222 local-win \
        "if exist \"$REMOTE\" (echo REMOTE_OK) else (echo REMOTE_MISSING)" 2>&1 | tail -1)
    echo "PRODUCt: $SSH_OUT ($REMOTE)"

    # 3. 预期文件清单校验（可选）
    if [[ -n "$EXPECT" ]]; then
        IFS=',' read -ra FILES <<< "$EXPECT"
        for f in "${FILES[@]}"; do
            f=$(echo "$f" | xargs)
            R=$(ssh -o ConnectTimeout=10 -p 2222 local-win \
                "if exist \"$REMOTE\\$f\" (echo OK) else (echo MISSING)" 2>&1 | tail -1)
            echo "FILE: $f → $R"
        done
    fi

    echo "=== 机械校验完成。以上材料供 LLM 验收判断；判断后调 close 段 ==="
    ;;

close)
    TASK_ID="" ; VERDICT="" ; NOTES="" ; UNVERIFIED=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -TaskId) TASK_ID="$2"; shift 2;;
            -Verdict) VERDICT="$2"; shift 2;;
            -Notes) NOTES="$2"; shift 2;;
            --unverified) UNVERIFIED=1; shift;;
            *) die "close 未知参数 $1";;
        esac
    done
    [[ -z "$TASK_ID" ]] && die "close 需要 -TaskId"

    if [[ $UNVERIFIED -eq 1 ]]; then
        board_update "$TASK_ID" "
t['state'] = 'completed-unverified'
t['note'] = (t.get('note','') + ' | SSH断，入验收队列').strip('| ')
"
        echo "CLOSED_AS: completed-unverified（下次唤醒补验收）"
        exit 0
    fi

    [[ -z "$VERDICT" ]] && die "close 需要 -Verdict pass|fail（或 --unverified）"

    if [[ "$VERDICT" == "pass" ]]; then
        board_update "$TASK_ID" "
t['state'] = 'closed'
t['conclusion'] = 'result_pass'
t['confirmed_at'] = __import__('datetime').datetime.now().isoformat(timespec='seconds')
if '''$NOTES''': t['note'] = '''$NOTES'''
"
        echo "CLOSED_AS: closed (pass)"
    else
        board_update "$TASK_ID" "
t['state'] = 'exception'
t['conclusion'] = 'result_fail'
if '''$NOTES''': t['note'] = '''$NOTES'''
"
        echo "CLOSED_AS: exception (fail) → 转异常流程（重派/升级）"
    fi
    ;;

brief)
    python3 - "$BOARD" <<'PYEOF'
import json, sys, os, time
d = json.load(open(sys.argv[1]))
tasks = d.get("tasks", {})
open_tasks = {k: v for k, v in tasks.items() if v.get("state") not in ("closed", "cancelled")}
print(f"=== BOARD BRIEF ({time.strftime('%H:%M:%S')}) ===")
print(f"在飞任务: {len(open_tasks)} / 总任务: {len(tasks)}")
for k, v in sorted(open_tasks.items(), key=lambda x: x[1].get("prio", "P9")):
    print(f"  [{v.get('state')}] {k} → {v.get('target')} step={v.get('step')} | {v.get('note','')[:60]}")
unv = {k: v for k, v in tasks.items() if v.get("state") == "completed-unverified"}
if unv:
    print(f"⚠ 验收入队: {list(unv.keys())}")
# 心跳检查
# v1.8: board-listener 已退役（砍A2A后audit源消失），心跳项移除
PYEOF
    ;;

*)
    echo "用法: $0 verify|-TaskId... | close -TaskId... | brief" >&2
    exit 2
    ;;
esac
