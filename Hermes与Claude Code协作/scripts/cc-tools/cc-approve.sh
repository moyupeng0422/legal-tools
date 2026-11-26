#!/bin/bash
# cc-approve.sh — CC 权限弹窗处理脚本（2026-11-22，Hermes×CC R1→R2 辩论定稿）
# 用法: cc-approve.sh dump              # 只读弹窗全文+分类，不按键
#       cc-approve.sh <N>               # 批准选项 N（1-based，脚本承载全部机械操作）
#       cc-approve.sh cancel            # 按 Esc 关闭弹窗（前置确认有弹窗才执行）
#       cc-approve.sh --allow-persist <N>  # 允许"不再询问"类持久化选项（显式授权）
#
# 设计（辩论定稿）:
#   - Hermes 只做决策输入（读 dump→选号），机械操作全由脚本承载
#   - 黑名单在 dump 环节分类（CLASSIFICATION 标记），按键入口二次校验硬拒
#   - don't-ask-again 选项拒绝持久化，除非 --allow-persist
#   - 排队弹窗: 批准后自动 dump 下一帧，有新弹窗输出 APPROVE_OK_NEXT
#   - NEED_REVIEW dump 输出弹窗全文不截断（关键词可能被截断导致误分类）
#   - cancel 前置确认: 无弹窗时按 Esc = 中断运行中 turn，必须拒绝
# 返回: 0=成功 | 1=失败 | 2=HUMAN_REQUIRED/NEED_REVIEW

SESSION="claude-session"

while getopts "t:h" opt; do
  case $opt in
    t) SESSION="$OPTARG" ;;
    h) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
  esac
done
shift $((OPTIND-1))

snap() { tmux capture-pane -t "$SESSION" -p -S -60 2>/dev/null; }

stable_snap() {
  local f1 f2 n=0
  while [ $n -lt 5 ]; do
    f1=$(snap); sleep 0.35; f2=$(snap)
    if [ "$f1" = "$f2" ]; then echo "$f2"; return; fi
    n=$((n+1))
  done
  echo "$f2"  # 5 轮仍抖动则返回最后一帧（调用方验证逻辑兜底）
}

# 弹窗检测：返回 0=有弹窗，输出弹窗文本块
detect_dialog() {
  local frame
  frame=$(stable_snap)
  # 弹窗特征：选项列表 + 确认标题在同一帧（且是底部 UI，非正文引用——锚定末尾区域）
  local tail_block
  tail_block=$(echo "$frame" | tail -15)
  if echo "$tail_block" | grep -qE "Do you want to proceed|Would you like to proceed|requires approval|Do you want to make this edit|Do you want to allow"; then
    echo "$frame"
    return 0
  fi
  return 1
}

# 分类：AUTO_OK / NEED_REVIEW / HUMAN_REQUIRED
classify() {
  local dialog="$1"
  # 只分析弹窗区块（最后一个分隔线之后的底部 UI 区），不读正文——正文引用黑名单词会误分类
  local dlg_block
  dlg_block=$(echo "$dialog" | sed -n "/^╌+/,\$p" | tail -20)
  # HUMAN_REQUIRED 黑名单（宁误报不放行）
  if echo "$dlg_block" | grep -qiE "bypass permissions|dangerously-skip|settings\.local\.json|\.claude\.json|settings\.json|hooks|mcp server|trust|删除|delete|rm -|del "; then
    echo "HUMAN_REQUIRED"
    return
  fi
  # NEED_REVIEW：写配置区路径/凭证字样/多行复杂内容
  if echo "$dlg_block" | grep -qiE "token|key|credential|secret|password|scp |ssh |curl |wget "; then
    echo "NEED_REVIEW"
    return
  fi
  echo "AUTO_OK"
}

# 选项行提取（> 1. Yes 格式）
list_options() {
  echo "$1" | grep -E "^\s*[>↓]?\s*[0-9]+\.|^\s*[>↓]\s+[0-9]+\." | sed 's/^[>↓ ]*//'
}

tmux has-session -t "$SESSION" 2>/dev/null || { echo "APPROVE_FAIL: session 不存在"; exit 1; }

CMD="$1"
case "$CMD" in
  dump)
    FRAME=$(detect_dialog)
    if [ $? -ne 0 ]; then
      echo "NO_DIALOG: 当前无权限弹窗"
      exit 0
    fi
    CLASS=$(classify "$FRAME")
    echo "CLASSIFICATION: $CLASS"
    echo "OPTIONS:"
    list_options "$FRAME"
    echo "--- DIALOG_FULLTEXT（不截断） ---"
    echo "$FRAME"
    exit 0
    ;;
  cancel)
    FRAME=$(detect_dialog)
    if [ $? -ne 0 ]; then
      echo "CANCEL_NO_DIALOG: 无弹窗，拒绝按 Esc（无弹窗时 Esc=中断运行中 turn）"
      exit 2
    fi
    tmux send-keys -t "$SESSION" Escape
    sleep 1
    if detect_dialog >/dev/null 2>&1; then
      echo "APPROVE_FAIL: Esc 后弹窗仍在，现场:"
      stable_snap | tail -5
      exit 1
    fi
    echo "CANCEL_OK: 弹窗已关闭"
    exit 0
    ;;
  --allow-persist)
    PERSIST=1
    N="$2"
    ;;
  [1-9])
    PERSIST=0
    N="$CMD"
    ;;
  *)
    echo "用法: cc-approve.sh dump | <N> | cancel | --allow-persist <N>"
    exit 1
    ;;
esac

# ── 批准流程 ──
FRAME=$(detect_dialog)
if [ $? -ne 0 ]; then
  echo "NO_DIALOG: 当前无权限弹窗，无需批准"
  exit 0
fi

# 闸门一：黑名单硬拒（即使 Hermes 已决策传号）——R2 定稿：无旁路，人工标志文件才放行
CLASS=$(classify "$FRAME")
if [ "$CLASS" = "HUMAN_REQUIRED" ]; then
  # 唯一放行通道：用户亲手创建的标志文件（决策权回到人手上，且创建动作本身是人的行为）
  if [ ! -f ~/.hermes/HUMAN_OK ]; then
    echo "APPROVE_HUMAN_REQUIRED: 弹窗命中黑名单（$CLASS），脚本拒绝按键。"
    echo "唯一放行方式：用户亲手执行 touch ~/.hermes/HUMAN_OK 创建标志文件后重试（审计日志自动记录）。"
    echo "--- DIALOG_FULLTEXT ---"
    echo "$FRAME"
    exit 2
  fi
  echo "ℹ HUMAN_AUDIT: $(date '+%F %T') HUMAN_OK 标志放行黑名单弹窗 → 追加审计" >> /tmp/cc_approve_audit.log
  rm -f ~/.hermes/HUMAN_OK  # 一次性使用，用后即焚
fi
if [ "$CLASS" = "NEED_REVIEW" ] && [ -z "$ALLOW_REVIEW" ]; then
  echo "APPROVE_NEED_REVIEW_GATE: 弹窗为 NEED_REVIEW 类，未经 ALLOW_REVIEW=1 确认不可按键。"
  echo "如 Hermes 已读全文确认安全: ALLOW_REVIEW=1 cc-approve.sh $N"
  echo "--- DIALOG_FULLTEXT ---"
  echo "$FRAME"
  exit 2
fi

# 闸门二：don't-ask-again 持久化防护（fail-closed：无法确认目标选项时视为命中）
TARGET_LINE=$(echo "$FRAME" | grep -E "^\s*[>↓ ]*\s*$N\." | head -1)
if [ -z "$TARGET_LINE" ]; then
  # gate-zero：目标选项不存在（dump 与 approve 之间状态失步）——绝不按键
  echo "APPROVE_FAIL: 选项 $N 在当前弹窗中不存在（状态可能已失步），拒绝按键。当前选项:"
  list_options "$FRAME"
  exit 1
fi
if echo "$TARGET_LINE" | grep -qiE "don.t ask again|不再询问|don't ask"; then
  if [ "$PERSIST" != "1" ]; then
    echo "APPROVE_PERSIST_BLOCKED: 选项 $N 为持久化授权（don't ask again），需 --allow-persist 显式批准:"
    echo "  $TARGET_LINE"
    exit 2
  fi
  echo "ℹ PERSIST_AUDIT: $(date '+%F %T') 用户授权持久化选项 $N → 追加至 cc-approve 审计" >> /tmp/cc_approve_audit.log
fi

# ── 机械操作（全脚本承载）──
# 1. 检查 > 是否已在目标选项上（ExitPlanMode 类弹窗不响应数字键，只认 Enter/Tab）
FRAME_NOW=$FRAME
if echo "$FRAME_NOW" | grep -qE "^\s*>\s*$N\."; then
  # > 已在目标选项 → 直接 Enter（数字键会被这类弹窗当文本吃进输入框）
  tmux send-keys -t "$SESSION" Enter
  sleep 1.2
  F2=$(stable_snap)
  if echo "$F2" | grep -qE "Do you want to proceed|Would you like to proceed|requires approval|Do you want to make this edit|Do you want to allow"; then
    NEXT_CLASS=$(classify "$F2")
    echo "APPROVE_OK_NEXT: 已确认（Enter 直通），队列中还有新弹窗（分类: $NEXT_CLASS）"
    exit 0
  fi
  echo "APPROVE_OK: 已确认（Enter 直通，> 原在目标选项）"
  exit 0
fi
# 2. > 不在目标选项 → 数字键选择路径（常规权限弹窗）
tmux send-keys -t "$SESSION" "$N"
sleep 1.0
# 2. 探测结果：弹窗消失（数字键直接确认类）= 成功；> 移动 = 需 Enter；无变化 = 重试
F1=$(stable_snap)
if ! echo "$F1" | grep -qE "Do you want to proceed|Would you like to proceed|requires approval|Do you want to make this edit|Do you want to allow"; then
  # 弹窗已消失（直接确认类弹窗，如 ExitPlanMode）→ 跳过 Enter
  if ! echo "$F1" | grep -qE "^\s*>\s*$N\."; then
    echo "APPROVE_OK: 选项 $N 已确认（直接确认类弹窗），弹窗已消失"
    exit 0
  fi
fi
if ! echo "$F1" | grep -qE "^\s*>\s*$N\."; then
  # 重试一次
  tmux send-keys -t "$SESSION" "$N"
  sleep 0.6
  F1=$(stable_snap)
  if ! echo "$F1" | grep -qE "^\s*>\s*$N\."; then
    echo "APPROVE_FAIL: 按 $N 后 > 未移动到目标选项。现场:"
    echo "$F1" | tail -8
    exit 1
  fi
fi
# 3. Enter 确认
tmux send-keys -t "$SESSION" Enter
sleep 1.2
# 4. 验证弹窗消失 or 排队下一弹窗
F2=$(stable_snap)
if echo "$F2" | grep -qE "Do you want to proceed|Would you like to proceed|requires approval|Do you want to make this edit|Do you want to allow"; then
  NEXT_CLASS=$(classify "$F2")
  echo "APPROVE_OK_NEXT: 选项 $N 已批，队列中还有新弹窗（分类: $NEXT_CLASS）"
  echo "OPTIONS:"
  list_options "$F2"
  exit 0
fi
echo "APPROVE_OK: 选项 $N 已批准，弹窗已消失"
exit 0
