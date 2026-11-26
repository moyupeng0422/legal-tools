#!/bin/bash
# cc-send.sh — 向 tmux 中的 CC 发送消息的强制通道（硬性约束）
# 用法: cc-send.sh [-t session] "消息内容"
#       cc-send.sh -t claude-session -f /path/to/msg.txt   # 从文件读长消息
# 机制: 发文本 → sleep → 发 Enter → 校验输入框清空 → 残留自动补 Enter(最多3次) → 输出 SEND_OK / SEND_FAIL
# 背景: 2026-11-21 确认文本+Enter 同帧发送会被 CC Ink 界面吞 Enter，消息卡框需用户手动回车。
#       本脚本将"发送+补键+验证+重试"固化，杜绝该故障。

SESSION="claude-session"
MSG=""
FROM_FILE=0

while getopts "t:f:h" opt; do
  case $opt in
    t) SESSION="$OPTARG" ;;
    f) MSG="$(cat "$OPTARG")"; FROM_FILE=1 ;;
    h) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "用法: $0 [-t session] \"消息\" 或 -f 文件"; exit 1 ;;
  esac
done
shift $((OPTIND-1))
[ -z "$MSG" ] && MSG="$1"
if [ -z "$MSG" ]; then
  echo "SEND_FAIL: 消息为空"
  exit 1
fi

# 0. 维护已发消息记录（供 cc-wait.sh -d 排除输入回显假阳性）
echo "$MSG" > /tmp/cc_last_sent.txt

# 检查 tmux session 存活
tmux has-session -t "$SESSION" 2>/dev/null || { echo "SEND_FAIL: tmux session $SESSION 不存在"; exit 1; }

# 1. 发送文本（不带 Enter）
tmux send-keys -t "$SESSION" "$MSG"
sleep 1.5

# 2. 发送 Enter
tmux send-keys -t "$SESSION" Enter
sleep 2

# 3. 校验输入框是否清空（输入框 = 当前屏（非滚动区）中含提示符的最后区域）
#    capture-pane 不带 -S 只取当前屏；输入框行是 "> " 或 "> 内容"，位于状态栏上方
check_inputbox() {
  # 取当前屏最后 8 行，找以可选空格+> 开头的输入框行（排除状态栏/装饰行）
  # 提示符后可能是普通空格或 UTF-8 不换行空格(U+00A0 = \xc2\xa0)，一并清除
  tmux capture-pane -t "$SESSION" -p | tail -8 \
    | grep -E '^\s*>' | tail -1 \
    | LC_ALL=C sed 's/^[[:space:]]*>//' | LC_ALL=C sed 's/^\xc2\xa0//' | tr -d ' \t\xc2\xa0' | sed 's/^[[:space:]]*//'
}

RETRY=0
MAX_RETRY=3
while [ $RETRY -lt $MAX_RETRY ]; do
  CONTENT=$(check_inputbox)
  # 输入框内容为空 = 发送成功
  if [ -z "$CONTENT" ]; then
    echo "SEND_OK: 消息已提交（重试 $RETRY 次）"
    # ── 看板登记+哨兵自动拉起（v2.1 三方评审：谁派发谁登记）──
    TASK_ID_HOOK=$(echo "$MSG" | grep -oE 'TASK:[a-z0-9-]+' | head -1 | cut -d: -f2)
    if [ -n "$TASK_ID_HOOK" ]; then
      python3 - "$TASK_ID_HOOK" << 'PYEOF' 2>/dev/null
import sys, subprocess
subprocess.run(["python3", "/home/ubuntu/.hermes/scripts/collab_board.py",
                "add", sys.argv[1], "cc", "--note", "auto-registered by cc-send"],
               capture_output=True)
PYEOF
      if ! pgrep -f "board_sentinel.sh\|board_watch.sh" > /dev/null 2>&1; then
        nohup bash "$HOME/.hermes/scripts/board_sentinel.sh" 30 1800 >> /tmp/board_watch.log 2>&1 &
        disown
      fi
      echo "BOARD_REGISTERED: $TASK_ID_HOOK (cc-send hook)"
    fi
    exit 0
  fi
  # 注意：消息发出后 CC 若开始回显历史（消息出现在输出区），输入框行应为空
  # 若输入框仍有内容 → 补发 Enter
  RETRY=$((RETRY+1))
  tmux send-keys -t "$SESSION" Enter
  sleep 2
done

# 4. 重试耗尽仍失败 → 明确报错
CONTENT=$(check_inputbox)
echo "SEND_FAIL: 补键 $MAX_RETRY 次后输入框仍有残留: [$CONTENT]"
echo "请人工检查 tmux $SESSION"
exit 1
