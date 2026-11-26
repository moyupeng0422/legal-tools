#!/usr/bin/env bash
# agent-send.sh — 飞书多 agent 发送引擎 v1.0 (2026-11-22)
# 契约：protocol-multiagent.md §2/§3/§4
# 用法: agent-send.sh <target> <task_id> [--step N] --text "..." | --msg-file <path>
#       [--override-serial "原因"] [--quiet]
# 输出: SEND_OK <message_id> (exit 0)
#       SEND_UNKNOWN_TARGET / SEND_UNCLOSED / SEND_TOO_LONG / SEND_SPLIT_ALARM / SEND_API_FAIL (exit 2)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$SCRIPT_DIR/agents.conf"
STATE="$SCRIPT_DIR/.agent_send_state.json"
ENV_FILE="/home/ubuntu/.hermes/.env"
HERMES_HOME="/home/ubuntu/.hermes"

usage() { grep '^#' "$0" | head -8; exit 1; }
die() { echo "$1"; exit 2; }

TARGET=""; TASK_ID=""; STEP="1"; TEXT=""; MSG_FILE=""; OVERRIDE=""; QUIET=0; NOTIFY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --step) STEP="$2"; shift 2;;
    --text) TEXT="$2"; shift 2;;
    --msg-file) MSG_FILE="$2"; shift 2;;
    --override-serial) OVERRIDE="$2"; shift 2;;
    --quiet) QUIET=1; shift;;
    --notify) NOTIFY=1; shift;;
    -h|--help) usage;;
    *) if [[ -z "$TARGET" ]]; then TARGET="$1"; shift;
       elif [[ -z "$TASK_ID" ]]; then TASK_ID="$1"; shift;
       else die "SEND_UNKNOWN_ARG: $1"; fi;;
  esac
done
[[ -z "$TARGET" || -z "$TASK_ID" ]] && usage
[[ -z "$TEXT" && -z "$MSG_FILE" ]] && die "SEND_NO_CONTENT: 需要 --text 或 --msg-file"
[[ -n "$MSG_FILE" ]] && TEXT="$(cat "$MSG_FILE")"

# ── 校验① target 白名单 + 配置加载（v1.7：合并原两遍 YAML 解析为一遍）──
# 原#38行第一遍仅做存在性校验后丢弃结果，与#47行第二遍完全重复（审计 P0-5）
T_RAW="$(python3 - "$CONF" "$TARGET" << 'PYEOF'
import sys, yaml
conf, target = sys.argv[1], sys.argv[2]
with open(conf) as f: c = yaml.safe_load(f)
t = (c.get("targets") or {}).get(target)
if not t or not t.get("enabled"): sys.exit(3)  # 3=UNKNOWN_TARGET
for k in ("channel_chat_id","at_open_id","at_handle","len_hard_kb","len_warn_kb","ack_timeout"):
    print(t.get(k, ""))
PYEOF
)"
RC_T=$?
[[ $RC_T -eq 3 ]] && die "SEND_UNKNOWN_TARGET: $TARGET 不在 agents.conf"
mapfile -t T <<< "$T_RAW"
CHAT_ID="${T[0]}"; AT_OID="${T[1]}"; AT_NAME="${T[2]}"; LEN_HARD=$(( ${T[3]:-100} * 1024 )); LEN_WARN=$(( ${T[4]:-20} * 1024 )); ACK_TIMEOUT="${T[5]:-600}"

# ── 校验② 串行铁律 ──
# v1.7.2：--notify 通知卡跳过串行检查（纯告知性质，随时可发，不占任务队列）
if [[ "$NOTIFY" -eq 0 && -f "$STATE" ]]; then
  OPEN="$(python3 -c "
import json
try:
    s = json.load(open('$STATE'))
    print(s.get('ack_state','closed'), s.get('task_id',''), s.get('sent_at',''))
except Exception: print('closed','','')
")"
  read -r ACK_STATE LAST_TASK SENT_AT <<< "$OPEN"
  if [[ "$ACK_STATE" == "open" ]]; then  # v1.7.2: notify 态不进此分支，通知卡不占串行闸门
    ELAPSED=$(( $(date +%s) - $(date -d "$SENT_AT" +%s 2>/dev/null || echo 0) ))
    if [[ "$ELAPSED" -lt "$ACK_TIMEOUT" && -z "$OVERRIDE" ]]; then
      die "SEND_UNCLOSED: 上次发送 [$LAST_TASK] 已 ${ELAPSED}s 未闭环(<${ACK_TIMEOUT})。等 wait 闭环或 --override-serial \"原因\""
    fi
    [[ -n "$OVERRIDE" ]] && echo "$(date -Is) OVERRIDE_SERIAL target=$TARGET task=$TASK_ID reason=$OVERRIDE" >> "$SCRIPT_DIR/.send_audit.log"
  fi
fi

# ── 校验②b 在途回执硬闸门（v1.6d P0）：同 target 有未回执卡片 → 拒发新卡 ──
# 芭迪依次处理卡片队列：上一张未回执就发下一张=堆积。仅 override 可越过（留痕）
# v1.7 修复（P0 键失配）：记账格式是 TASK_ID|STEP|MSG_ID|TS（见文件尾部 RECORD_PENDING），
#   旧代码按 '$TARGET|' 过滤 → 生产口径下永不命中，闸门从未生效（2026-11-23 审计确认）。
#   修正：按首字段=TASK_ID 过滤；本 target 的全部 TASK_ID 从 .agent_send_state.json+看板取，
#   简化为主键=本次 TASK_ID 之外，还需覆盖历史未核销——用 agents.conf 反查该 target 的 task 前缀不可靠，
#   故直接对账：扫描全账本，凡是「同一 target 历史发送过」的 task_id 需要映射。
#   实现口径：accountability 记账行追加 target 字段（新格式 target|task|step|msg|ts），
#   同时兼容读旧格式（task|step|msg|ts，按 state.json 的 task_id+target 映射兜底）。
# 读取所有历史 state 中 target→task 映射
TARGET_TASKS="$(python3 -c "
import json, os
st = os.path.expanduser('~/.hermes/scripts/.agent_send_state.json')
try:
    s = json.load(open(st))
    if s.get('target') == '$TARGET': print(s.get('task_id',''))
except Exception: pass
" 2>/dev/null)"
PENDING_HITS="$(python3 - "$TARGET" "$TASK_ID" << 'PYEOF'
import os, sys
target, cur_task = sys.argv[1], sys.argv[2]
pr = os.path.expanduser('~/.hermes/pending_receipts.jsonl')
if not os.path.exists(pr): raise SystemExit
hits = []
for line in open(pr, encoding='utf-8'):
    line = line.strip()
    if not line: continue
    parts = line.split('|')
    # 新格式 target|task|step|msg|ts ；旧格式 task|step|msg|ts
    if len(parts) >= 5:
        tgt, task = parts[0], parts[1]
    elif len(parts) == 4:
        tgt, task = None, parts[0]
    else:
        continue
    # 命中条件：task 属于本 target（新格式直接比 target；旧格式与本次 task 或历史映射比对）
    if tgt is not None:
        if tgt == target: hits.append(line)
    else:
        if task == cur_task: hits.append(line)
print('\n'.join(hits))
PYEOF
)"
if [[ -n "$PENDING_HITS" && -z "$OVERRIDE" && "$NOTIFY" -eq 0 ]]; then
  die "SEND_PENDING_RECEIPT: target=$TARGET 有未回执卡片在途：
$PENDING_HITS
对方依次处理队列中——等回执后再发，或 --override-serial \"理由\"（如芭迪意外卡住需插队）"
fi
[[ -n "$PENDING_HITS" && -n "$OVERRIDE" ]] && echo "$(date -Is) OVERRIDE_PENDING target=$TARGET task=$TASK_ID reason=$OVERRIDE pending=[$PENDING_HITS]" >> "$SCRIPT_DIR/.send_audit.log"

# ── 校验③ @ 模板强制注入（消息头）──
if [[ "$TEXT" != *"<at user_id=\"$AT_OID\""* ]]; then
  TEXT="<at user_id=\"$AT_OID\">$AT_NAME</at> $TEXT"
fi

# ── 校验④ 长度守卫（UTF-8 字节数，与飞书平台口径一致）──
BODY_LEN=$(python3 -c "import sys; print(len(sys.argv[1].encode('utf-8')))" "$TEXT")
[[ $BODY_LEN -gt $LEN_HARD ]] && die "SEND_TOO_LONG: ${BODY_LEN}B > 硬上限 ${LEN_HARD}B。长内容走 conv 文件+短指针"
[[ $BODY_LEN -gt $LEN_WARN && $QUIET -eq 0 ]] && echo "WARN: 内容 ${BODY_LEN}B 超过警告阈值 ${LEN_WARN}B（不阻断）"

# ── 凭证 ──
APP_ID="$(grep '^FEISHU_APP_ID=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d ' ')"
APP_SECRET="$(grep '^FEISHU_APP_SECRET=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d ' ')"
[[ -z "$APP_ID" || -z "$APP_SECRET" ]] && die "SEND_NO_CRED: .env 缺 FEISHU_APP_ID/SECRET"

TOKEN=$(python3 -c "
import json, urllib.request
req = urllib.request.Request('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    data=json.dumps({'app_id':'$APP_ID','app_secret':'$APP_SECRET'}).encode(),
    headers={'Content-Type':'application/json'})
r = json.loads(urllib.request.urlopen(req, timeout=15).read())
assert r.get('code')==0, r
print(r['tenant_access_token'])
") || die "SEND_TOKEN_FAIL"

# ── 校验⑤ 发送（直调 REST，绕过 gateway adapter 拆分）+ 拆分哨兵 ──
# @ 标签需经 text 内容的 <at> 语法？飞书 text 消息的 @ 是纯文本不触发唤醒——
# 必须用 text 内容中 @_user_占位 或 post/interactive。实测：text 消息内 <at> 标签不渲染。
# 方案：text 类型 + content.text 内嵌 @文本 作为可见标记；真正唤醒依赖群内 @ 渲染，
# 需 msg_type=text 且 text 含 at 标签——飞书 text 不支持；故用 post 富文本不支持…
# 结论：唤醒级 @ 必须走 text content 的特殊格式或 interactive。
# 飞书官方：text 消息里 <at user_id=\"ou_xxx\"></at> 是支持的（content JSON 内）。
RESP=$(python3 - "$CHAT_ID" "$TEXT" "$TOKEN" << 'PYEOF'
import json, sys, urllib.request
chat_id, text, token = sys.argv[1], sys.argv[2], sys.argv[3]
body = {"receive_id": chat_id, "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False)}
req = urllib.request.Request(
    "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
    data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
r = json.loads(urllib.request.urlopen(req, timeout=20).read())
if r.get("code") != 0:
    print(f"API_ERR|{r.get('code')}|{r.get('msg')}"); sys.exit(0)
mid = r["data"]["message_id"]
print(f"OK|{mid}")
PYEOF
) || die "SEND_API_FAIL: REST 调用异常"
CMD_TYPE="${RESP%%|*}"; RESP_BODY="${RESP#*|}"
[[ "$CMD_TYPE" == "API_ERR" ]] && die "SEND_API_FAIL: $RESP_BODY"
MESSAGE_ID="$RESP_BODY"

# ── 校验⑤b 送达回读（v1.7 P0-7，v1.7.1 三态修正——CC 终审采纳）──
# 背景：2026-11-23 00:24 gateway 静默吞消息事故。发送≠送达，需 GET 回读确认。
# v1.7.1 关键定性修正（CC 抓出）：die 时 send API 已返回 message_id——卡片已在对方队列。
# 回读失败=「无法确认送达」≠「确认未送达」。原版 die 不记账会让真实在途的卡在账本上不存在
# → 闸门放行下一张 → 串行纪律静默破坏。修正为三态分类：
#   404 → 真未落库 → die 不记账（唯一合法的"确认未送达"路径）
#   429/5xx/超时 → 退避重试 0.5/1/2s 三次；401 → 刷 token 重试一次
#   三次全败 → 正常记账 + verified:false 标记 + 告警（记录事实，校验结果作字段）
VERIFY=$(python3 - "$MESSAGE_ID" "$TOKEN" << 'PYEOF'
import json, sys, time, urllib.request
message_id, token = sys.argv[1], sys.argv[2]

def read_msg(tok):
    req = urllib.request.Request(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}",
        headers={"Authorization": f"Bearer {tok}"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        return {"code": -1, "msg": f"EXC|{e}"}

delays = [0.5, 1, 2]
for i, d in enumerate(delays):
    time.sleep(d)
    r = read_msg(token)
    c = r.get("code")
    if c == 0:
        print("VERIFIED"); raise SystemExit
    if c == 99991663 or c == 401 or (isinstance(c, int) and c == -1 and "401" in str(r.get("msg",""))):
        # token 失效：刷新一次再继续
        print("TOKEN_EXPIRED", flush=True); raise SystemExit(3)
    # 429/5xx/其他：继续退避重试
# 三次全败，区分最终错误码
r_last = read_msg(token)
c_last = r_last.get("code")
if c_last == 99991661 or c_last == 404 or (isinstance(c_last, int) and 23000 <= c_last <= 23999):
    print(f"NOT_FOUND|{c_last}|{r_last.get('msg')}")   # 真未落库
else:
    print(f"UNCONFIRMED|{c_last}|{r_last.get('msg')}") # 无法确认（卡可能已在途）
PYEOF
) || true
VERIFY_RC=$?
if [[ "$VERIFY" == "VERIFIED" ]]; then
  DELIVERY_VERIFIED=true
  echo "DELIVERY_VERIFIED: $MESSAGE_ID 回读确认已落库"
elif [[ "$VERIFY" == TOKEN_EXPIRED ]]; then
  # token 刷新后重读一次（沿用主 token 获取逻辑）
  TOKEN=$(python3 -c "
import json, urllib.request
req = urllib.request.Request('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    data=json.dumps({'app_id':'$APP_ID','app_secret':'$APP_SECRET'}).encode(),
    headers={'Content-Type':'application/json'})
r = json.loads(urllib.request.urlopen(req, timeout=15).read())
assert r.get('code')==0, r
print(r['tenant_access_token'])
") || TOKEN=""
  VERIFY=$(python3 - "$MESSAGE_ID" "$TOKEN" << 'PYEOF'
import json, sys, urllib.request
message_id, token = sys.argv[1], sys.argv[2]
req = urllib.request.Request(
    f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}",
    headers={"Authorization": f"Bearer {token}"})
try:
    r = json.loads(urllib.request.urlopen(req, timeout=15).read())
    print("VERIFIED" if r.get("code")==0 else f"UNCONFIRMED|{r.get('code')}")
except Exception as e:
    print(f"UNCONFIRMED|EXC|{e}")
PYEOF
) || true
  [[ "$VERIFY" == "VERIFIED" ]] && { DELIVERY_VERIFIED=true; echo "DELIVERY_VERIFIED: $MESSAGE_ID (token refreshed)"; }
fi
if [[ "${DELIVERY_VERIFIED:-false}" != "true" ]]; then
  CMD_V="${VERIFY%%|*}"
  if [[ "$CMD_V" == "NOT_FOUND" ]]; then
    # 唯一合法的「确认未送达」：不记账，硬失败（防幽灵卡假象——API 成功但实际未落库属异常，人工排查）
    echo "$(date -Is) SEND_DELIVERY_NOT_FOUND msg=$MESSAGE_ID result=$VERIFY" >> "$SCRIPT_DIR/.send_audit.log"
    die "SEND_DELIVERY_NOT_FOUND: message_id=$MESSAGE_ID 回读404——API 声称成功但消息未落库，属平台异常，未记账。请人工核查"
  fi
  # 无法确认（429/5xx/超时三次全败）：卡片大概率已在途 → 正常记账 + verified:false 标记 + 告警
  echo "$(date -Is) SEND_DELIVERY_UNCONFIRMED msg=$MESSAGE_ID result=$VERIFY task=$TASK_ID step=$STEP" >> "$SCRIPT_DIR/.send_audit.log"
  echo "WARN: SEND_DELIVERY_UNCONFIRMED（$VERIFY）——卡可能已在途，已记账并标记 verified:false，请留意对方回执"
  DELIVERY_VERIFIED=false
fi

# 拆分哨兵：直调 API 一次调用只返回一个 message_id；此断言防御未来接口行为变化
MSG_COUNT=$(echo "$MESSAGE_ID" | grep -c "," || true)
[[ ${MSG_COUNT:-0} -gt 0 ]] && die "SEND_SPLIT_ALARM: 返回多个 message_id=$MESSAGE_ID（异常拆分）"

# ── 校验⑥ 状态登记 ──
FP=$(python3 -c "import hashlib; print(hashlib.sha256(f'$TASK_ID|$STEP'.encode()).hexdigest()[:12])")
python3 - "$STATE" "$TARGET" "$TASK_ID" "$STEP" "$MESSAGE_ID" "$FP" "$NOTIFY" << 'PYEOF'
import json, sys
from datetime import datetime
path = sys.argv[1]
# v1.7.2：通知卡 ack_state=notify（不占串行闸门——无交付物语义，无需 wait 闭环）
ack = "notify" if sys.argv[7] == "1" else "open"
state = {
    "target": sys.argv[2], "task_id": sys.argv[3], "step": sys.argv[4],
    "message_id": sys.argv[5], "sent_at": datetime.now().isoformat(timespec="seconds"),
    "ack_state": ack, "fingerprint": sys.argv[6],
}
json.dump(state, open(path, "w"), ensure_ascii=False, indent=2)
PYEOF

echo "SEND_OK: $MESSAGE_ID | fingerprint=$FP | task=$TASK_ID step=$STEP target=$TARGET"

# ── 哨兵自动拉起（任务生命周期绑定，2026-11-22 用户拍板）──
# 语义：派任务 → 哨兵自动启动（短间隔盯守）；全任务收口 → 哨兵自检退出。
# Hermes 不需要手动挂监控。已有哨兵在跑则不重复拉起。
# v1.7.2：通知卡跳过看板登记（纯告知无任务语义，登记反而制造假 dispatched）
if [ "$NOTIFY" -eq 0 ]; then
python3 - "$TASK_ID" "$TARGET" "$STEP" << 'PYEOF' || echo "BOARD_ADD_WARN: 看板登记失败（非阻断）"
import sys, subprocess
sys.path.insert(0, "/home/ubuntu/.hermes/scripts")
r = subprocess.run(["python3", "/home/ubuntu/.hermes/scripts/collab_board.py",
                    "add", sys.argv[1], sys.argv[2], "--step", sys.argv[3],
                    "--note", "auto-registered by agent-send"],
                   capture_output=True, text=True)
print(r.stdout.strip()); sys.exit(0)
PYEOF
fi
# ── 回执记账（v1.6d 硬闸门 P0）：SEND_OK 后登记 pending receipt ──
# v1.7：新格式 target|task|step|msg|ts（闸门按 target 过滤需要此字段；兼容读旧格式）
# v1.7.2（2026-11-23 用户驱动）：--notify 通知卡不记账——通知无交付物语义，不占回执闭环；
#   送达保障靠 DELIVERY_VERIFIED 回读（已内建）。避免"通知卡回执永挂账本→闸门误拦后续派发"
if [ "$NOTIFY" -eq 1 ]; then
  echo "NOTIFY_MODE: 通知卡不记账（无回执闭环要求；送达已由回读校验确认）"
else
  echo "$TARGET|$TASK_ID|$STEP|$MESSAGE_ID|$(date -Iseconds)" >> ~/.hermes/pending_receipts.jsonl
  echo "RECORD_PENDING: task=$TASK_ID step=$STEP 已登记回执账本（收口前须核销）"
fi
if ! pgrep -f "board_sentinel.sh\|board_watch.sh" > /dev/null 2>&1; then
  echo "WATCH_NOT_RUNNING: 主会话请立即 terminal(background=true) 拉起 board_watch.sh（exit-on-change 才能唤醒主会话）——派发必拉 watch 铁律（协议 v1.5）"
  echo "（v1.7：nohup 保险哨兵钩子已删——无唤醒通道纯日志，审计裁定冗余；提醒保留）"
else
  echo "SENTINEL_RUNNING: 看板哨兵已在运行（terminal bg 主通道有效）"
fi
