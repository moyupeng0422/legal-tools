#!/bin/bash
# cc-wait.sh — 智能等待 CC 状态变化（替代固定 sleep）
# 用法: cc-wait.sh [-t session] [-T 秒] [-d 关键词] [-p] [-i 轮询间隔秒] [-m 已发消息文件]
#   默认: 等待 CC 从 busy（emoji+省略号状态行）变为空闲（无 busy 行 + 输入框空）
#   -d 关键词: 等待 CC 输出区出现标记（如 DONE/ACK），出现即返回 done
#   -m 文件:   排除模式——把已发消息内容写入临时文件传入，-d 匹配时排除"输入回显"造成的假阳性
#              （不传 -m 时自动读取最近发送记录 /tmp/cc_last_sent.txt，由 cc-send.sh 自动维护）
#   -p: 检测权限弹窗，出现立即返回 popup (exit 2)
#   -q: 队列自愈——检测到 "Press up to edit queued messages" 且 CC 无响应时自动补 Enter 消化队列
# 返回: exit 0 = idle/done | exit 2 = popup | exit 3 = timeout
#
# v2 (2026-11-21): 修复 -d 假阳性（匹配到输入回显而非 CC 回复）；新增 -q 队列自愈、-m 排除文件

SESSION="claude-session"
TIMEOUT=300
DONE_KW=""
SENT_FILE="/tmp/cc_last_sent.txt"
POPUP=0
QUEUE_FIX=0
POLL=3

TASK_MAP=0
while getopts "t:T:d:m:pqi:M" opt; do
  case $opt in
    t) SESSION="$OPTARG" ;;
    T) TIMEOUT="$OPTARG" ;;
    d) DONE_KW="$OPTARG" ;;
    m) SENT_FILE="$OPTARG" ;;
    p) POPUP=1 ;;
    q) QUEUE_FIX=1 ;;
    i) POLL="$OPTARG" ;;
    M) TASK_MAP=1 ;;
    *) echo "用法: $0 [-t session] [-T 秒] [-d 关键词] [-m 已发消息文件] [-p] [-q] [-i 秒] [-M 落库TASK_MAP]"; exit 1 ;;
  esac
done

# busy 判定（skill 47d）：活跃状态行带省略号；完成态 "✻ Baked for 5s" 无省略号不算 busy
BUSY_PAT='(✶|✽|✻|✢|✦|·) .*…'
POPUP_PAT='(Do you want to proceed|requires approval|^> 1\. (Yes|No))'
QUEUE_PAT='Press up to edit queued messages'

START=$(date +%s)
STABLE=0
QUEUE_STABLE=0

# 判断一行是否为"输入回显"：消息发出后 CC 会把用户输入原样显示在输出区（> 前缀行及其折行）
# -d 匹配必须排除这些回显行，只认 CC 自己的回复输出
is_echo_line() {
  # 输入回显特征：行首 "> " 或行首为折行缩进且与已发消息重叠
  echo "$1" | grep -qE '^\s*>\s'
}

while true; do
  NOW=$(date +%s)
  ELAPSED=$((NOW-START))
  [ $ELAPSED -ge $TIMEOUT ] && { echo "WAIT_TIMEOUT: ${TIMEOUT}s 内未达到目标状态"; exit 3; }

  SNAP=$(tmux capture-pane -t "$SESSION" -p -S -60 2>/dev/null)

  # 1. 弹窗检测（优先级最高）
  if [ $POPUP -eq 1 ] && echo "$SNAP" | grep -qE "$POPUP_PAT"; then
    echo "WAIT_POPUP: 检测到权限弹窗，需要处理"
    echo "$SNAP" | grep -E "$POPUP_PAT" | head -2
    exit 2
  fi

  # 2. 队列自愈：排队信号持续出现且 CC 无忙碌 → 补 Enter 消化（skill #156）
  if [ $QUEUE_FIX -eq 1 ]; then
    if echo "$SNAP" | grep -q "$QUEUE_PAT"; then
      HAS_EMOJI_Q=$(echo "$SNAP" | grep -cE "$BUSY_PAT")
      if [ $HAS_EMOJI_Q -eq 0 ]; then
        QUEUE_STABLE=$((QUEUE_STABLE+1))
        if [ $QUEUE_STABLE -ge 2 ]; then   # 连续2次采样确认排队且空闲 → 补键
          tmux send-keys -t "$SESSION" Enter
          sleep 2
          QUEUE_STABLE=0
          echo "QUEUE_FIX: 检测到滞留队列，已补 Enter 消化"
        fi
      fi
    else
      QUEUE_STABLE=0
    fi
  fi

  # 3. done 关键词检测（v2：排除输入回显行，只匹配 CC 输出）
  if [ -n "$DONE_KW" ]; then
    # 取 CC 输出行（排除 "> " 开头的用户输入回显行），检查关键词
    HIT=$(echo "$SNAP" | grep -vE '^\s*>\s' | grep -F "$DONE_KW" | head -1)
    if [ -n "$HIT" ]; then
      echo "WAIT_DONE: 关键词 [$DONE_KW] 已出现于 CC 输出（耗时 ${ELAPSED}s）"
      # v3 --task-map: DONE 触发时自动提取 [TASK_MAP] 块落库（#18 task_map 漏记根治）
      if [ "$TASK_MAP" = "1" ]; then
        tmux capture-pane -t "$SESSION" -p -S -200 2>/dev/null | python3 -c "
import sys, json, re, datetime
frame = sys.stdin.read()
m = re.search(r'\[TASK_MAP\](.*?)\[/TASK_MAP\]', frame, re.S)
if not m:
    print('  TASK_MAP: 本轮 DONE 无 [TASK_MAP] 块，跳过落库')
    sys.exit(0)
block = m.group(1)
def pick(k):
    mm = re.search(rf'{k}:\s*(.+)', block)
    return mm.group(1).strip() if mm else ''
name = pick('session') or pick('task_id')
if not name:
    print('  TASK_MAP: 块内无 session/task_id，跳过')
    sys.exit(0)
entry = {'task_id': pick('task_id'), 'step': pick('step'), 'done': pick('done'),
         'session': name, 'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
         'status': 'updated'}
p = '/home/ubuntu/.hermes/claude_task_map.json'
try:
    d = json.load(open(p, encoding='utf-8'))
except Exception:
    d = {}
d[name] = entry
json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'  TASK_MAP_OK: {name} → done={entry[\"done\"]} 已落库')
"
      fi
      # v3: output_type 辩论提醒（协议字段，CC 自声明）
      if echo "$SNAP" | grep -q "output_type: *analysis"; then
        echo "⚠ DEBATE_REQUIRED: CC 本轮为方案类输出（output_type: analysis）。回复用户前：发 [辩论]R2 或声明豁免（豁免原因: xxx）"
      fi
      exit 0
    fi
  fi

  # 4. 空闲检测
  HAS_EMOJI=$(echo "$SNAP" | grep -cE "$BUSY_PAT")
  if [ $HAS_EMOJI -eq 0 ]; then
    STABLE=$((STABLE+1))
    if [ $STABLE -ge 2 ]; then
      echo "WAIT_IDLE: CC 空闲（耗时 ${ELAPSED}s）"
      exit 0
    fi
  else
    STABLE=0
  fi

  sleep $POLL
done
