#!/bin/bash
# cc-start.sh — CC 会话启动六步法脚本化（2026-11-22，hooks 全否决后的统一脚本架构）
# 用法: cc-start.sh <任务名> [项目目录]
#   cc-start.sh "Hermes:新任务名"
#   cc-start.sh "Hermes:新任务名" "D:\其他项目目录"
# 六步: ①SSH连通 ②cd项目目录 ③启动claude ④HERMES-ACTIVATE ⑤/rename ⑥task_map落库
# 每步逐项验证，任一步失败即停并输出现场（消除 #48/#89/#90 高频违规源）

SESSION="claude-session"
PROJECT_DIR="${CC_PROJECT_DIR:-}"  # 必填：Windows 端项目根目录（建议 export CC_PROJECT_DIR 或直接改此行）
TASK_NAME="$1"
[ -z "$TASK_NAME" ] && { echo "START_FAIL: 缺任务名。用法: cc-start.sh <任务名> [项目目录]"; exit 1; }
[ -n "$2" ] && PROJECT_DIR="$2"

echo "═══ cc-start: 启动 CC 会话 [$TASK_NAME] ═══"

# 0. 前置：清理旧 session（幂等——已有 session 则复用判断留给调用者，默认拒绝重建）
if tmux has-session -t "$SESSION" 2>/dev/null; then
  CUR=$(bash "$(dirname "$0")/cc-mode.sh" status 2>/dev/null | head -1)
  # 判断 pane 是否在跑 CC（最后一行提示符特征）
  LAST=$(tmux capture-pane -t "$SESSION" -p -S -3 2>/dev/null | tail -1)
  if echo "$LAST" | grep -qE "accept edits on|plan mode on|auto mode on|^\\$|^>"; then
    echo "START_FAIL: session 已存在且疑似 CC 活跃（$CUR）。重建请先 kill: tmux kill-session -t $SESSION"
    exit 1
  fi
  echo "ℹ session 存在但非 CC（bash shell），复用 session"
fi

# Step1: SSH 连通
echo "[1/6] SSH 连通性..."
ssh -o ConnectTimeout=10 local-win "echo OK" >/dev/null 2>&1 \
  || { echo "START_FAIL: SSH 不通。诊断: ssh-diagnostics.md"; exit 1; }
echo "      OK"

# Step2: cd 项目目录（在 tmux session 内；无 session 则创建）
echo "[2/6] cd $PROJECT_DIR ..."
tmux has-session -t "$SESSION" 2>/dev/null || tmux new-session -d -s "$SESSION" -x 220 -y 50
tmux send-keys -t "$SESSION" "cd /d \"$PROJECT_DIR\"" Enter
sleep 2
PANE=$(tmux capture-pane -t "$SESSION" -p -S -3 | tail -1)
if ! echo "$PANE" | grep -qi "work-management\|$(basename "$PROJECT_DIR" | sed 's/.*\\\\//')"; then
  echo "      ⚠ 提示符未确认切换（当前: $PANE）——继续但请人工留意"
else
  echo "      OK"
fi

# Step3: 启动 claude（正常模式，不带模型参数不带--resume）
echo "[3/6] 启动 claude ..."
tmux send-keys -t "$SESSION" "claude" Enter
sleep 12
PANE=$(tmux capture-pane -t "$SESSION" -p -S -8)
if echo "$PANE" | grep -q "Bypass Permissions"; then
  echo "      ⚠ 检测到 Bypass 弹窗 → 按 2 接受"
  tmux send-keys -t "$SESSION" "2"; sleep 0.5
  tmux send-keys -t "$SESSION" Enter; sleep 3
fi
if ! tmux capture-pane -t "$SESSION" -p -S -5 | grep -qE "^>|shift\+tab"; then
  echo "START_FAIL: claude 未正常启动，现场:"
  tmux capture-pane -t "$SESSION" -p -S -8 | tail -5
  exit 1
fi
echo "      OK"

# Step4: HERMES-ACTIVATE（走 cc-send 保证送达）
echo "[4/6] 激活协作模式 ..."
bash "$(dirname "$0")/cc-send.sh" "<!-- HERMES-ACTIVATE -->" | grep -q SEND_OK \
  || { echo "START_FAIL: 激活标记发送失败"; exit 1; }
sleep 4
echo "      OK"

# Step5: /rename 任务名（走 cc-send；带 Hermes: 前缀检查）
echo "[5/6] /rename ..."
case "$TASK_NAME" in
  Hermes:*) REN="$TASK_NAME" ;;
  *) REN="Hermes:$TASK_NAME" ;;
esac
bash "$(dirname "$0")/cc-send.sh" "/rename $REN" >/dev/null
sleep 4
if ! tmux capture-pane -t "$SESSION" -p -S -5 | grep -q "$REN"; then
  echo "START_FAIL: rename 未生效，现场:"
  tmux capture-pane -t "$SESSION" -p -S -5 | tail -3
  exit 1
fi
echo "      OK → $REN"

# Step6: task_map 落库（立即写，不等任务完成——#18 教训）
echo "[6/6] task_map 落库 ..."
python3 - "$REN" <<'EOF'
import json, sys, datetime
name = sys.argv[1]
for p in ["/home/ubuntu/.hermes/claude_task_map.json"]:
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        d = {}
    d[name] = {"task_id": "", "step": 0, "done": 0, "session": name,
               "created": datetime.date.today().isoformat(), "status": "started"}
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"      OK → {p}")
EOF

# 终态验证：模式状态 + 输入框干净
MODE=$(bash "$(dirname "$0")/cc-mode.sh" status)
INPUT=$(tmux capture-pane -t "$SESSION" -p -S -3 | tail -1)
if echo "$INPUT" | grep -qE "^> *$|^> $"; then
  CLEAN="输入框干净"
else
  CLEAN="⚠ 输入框有残留: $INPUT"
fi
echo "═══ START_OK: $REN | $MODE | $CLEAN ═══"
exit 0
