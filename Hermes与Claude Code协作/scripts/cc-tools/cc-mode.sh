#!/bin/bash
# cc-mode.sh — CC tmux 会话模式切换脚本（2026-11-22，Hermes×CC R1→R2 辩论定稿）
# 用法: cc-mode.sh [plan|auto|normal|status] [-t session]
# 机制: 前置空闲检查 → 循环 BTab + 读状态栏到位即停 → 帧稳定验证
# 规则（辩论定稿）:
#   - 弹窗悬着时 BTab 语义变成挪弹窗光标 → 必须前置空闲检查，非空闲报 MODE_BUSY
#   - 不硬编码循环顺序（版本行为可能变），循环+读状态栏+到位即停
#   - 连续 2 次 BTab 状态栏无变化 → 上报 MODE_STUCK（有东西挡着，继续按是掷骰子）
#   - 按键后帧稳定检查：连读两帧一致才算数（防 capture 帧滞后）
# 返回: 0=成功 | 1=失败 | 2=MODE_BUSY/MODE_STUCK

SESSION="claude-session"
TARGET=""
MAX_TRIES=8

while getopts "t:h" opt; do
  case $opt in
    t) SESSION="$OPTARG" ;;
    h) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
  esac
done
shift $((OPTIND-1))
TARGET="$1"

snap() { tmux capture-pane -t "$SESSION" -p -S -4 2>/dev/null; }

# 帧稳定读取：连读两帧一致才返回
stable_snap() {
  local f1 f2
  f1=$(snap); sleep 0.35; f2=$(snap)
  if [ "$f1" = "$f2" ]; then echo "$f2"; else stable_snap; fi
}

# 前置空闲检查：无弹窗、无运行中旋转指示
check_idle() {
  local frame
  frame=$(stable_snap)
  if echo "$frame" | grep -qE "Do you want to proceed|requires approval|esc to interrupt|Press up to edit queued"; then
    echo "MODE_BUSY: 会话非空闲（弹窗/运行中/队列挂起），拒绝切换。现场:"
    echo "$frame" | tail -3
    exit 2
  fi
}

# 读当前模式
current_mode() {
  local frame
  frame=$(stable_snap)
  if echo "$frame" | grep -q "⏸ plan mode on"; then echo "plan"
  elif echo "$frame" | grep -q "⏵⏵ accept edits on"; then echo "auto"
  elif echo "$frame" | grep -q "⏵⏵ auto mode on"; then echo "auto"
  else echo "normal"; fi
}

tmux has-session -t "$SESSION" 2>/dev/null || { echo "MODE_FAIL: session $SESSION 不存在"; exit 1; }

if [ "$TARGET" = "status" ] || [ -z "$TARGET" ]; then
  echo "MODE_OK:$(current_mode)"
  exit 0
fi

case "$TARGET" in
  plan|auto|normal) ;;
  *) echo "MODE_FAIL: 未知目标 '$TARGET'（plan|auto|normal|status）"; exit 1 ;;
esac

check_idle

CUR=$(current_mode)
if [ "$CUR" = "$TARGET" ]; then
  echo "MODE_OK:$TARGET (已是目标模式)"
  exit 0
fi

STUCK=0
TRY=0
while [ $TRY -lt $MAX_TRIES ]; do
  tmux send-keys -t "$SESSION" BTab
  sleep 0.5
  NEW=$(current_mode)
  if [ "$NEW" = "$TARGET" ]; then
    echo "MODE_OK:$TARGET (尝试 $((TRY+1)) 次 BTab)"
    exit 0
  fi
  if [ "$NEW" = "$CUR" ]; then
    STUCK=$((STUCK+1))
    if [ $STUCK -ge 2 ]; then
      echo "MODE_STUCK: 连续 $STUCK 次 BTab 状态栏无变化（可能被吞/有遮挡），现场:"
      snap | tail -3
      exit 2
    fi
  else
    STUCK=0
    CUR="$NEW"
  fi
  TRY=$((TRY+1))
  sleep 0.3
done

echo "MODE_FAIL: $MAX_TRIES 次 BTab 未到达 '$TARGET'，末帧:"
snap | tail -3
exit 1
