#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
badi-wait — 芭迪协作同 turn 阻塞等待（v2.0 单信号版, 2026-11-23）

v1.8 终版架构（R8/R9 定稿）：
  唯一唤醒信号 = 芭迪群新消息（卡片+纯文本，同一 ListMessage API，30s 轮询）
  - 卡片 = 框架回合边界（完成/权限/进度），零内容，sender 白名单过滤
  - 纯文本 = 异常/权限的机器可读叙事（[完成] task-x / [权限] ... 前缀可 --task 过滤）
  - audit/conv 源已删除（A2A 砍除 + 卡片为权威信号）

STALL 梯子（R5 修正1 状态文件续计时）：
  exit 前按 start_ts 起算的墙钟输出梯子建议（10min 催办 / 30min 升卡）

退出码：
  0 = 检测到信号（stdout: SIGNAL: <type> + 原材料）
  1 = 总超时（stdout: WAIT_TIMEOUT + STALL 梯子判定）
  2 = 参数/环境错误

用法：
  badi-wait.py --task <task_id> [--total 1800] [--stall-1 600] [--stall-2 1800]
"""
import argparse, json, os, sys, time, urllib.request

HOME = os.path.expanduser("~")
STATE_DIR = os.path.join(HOME, ".hermes")

GROUP_CHAT = "<collab-group-chat-id>"
BADI_APP_ID = "<app-id>"
GROUP_POLL_INTERVAL = 30   # 用户裁定 30s（2026-11-23）


def log(msg):
    print(msg, flush=True)


def load_env():
    env = {}
    p = os.path.join(HOME, ".hermes/.env")
    for line in open(p):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def board_task_state(task_id):
    """查板快路径：任务已闭环 → 立即返回"""
    try:
        d = json.load(open(os.path.join(HOME, ".hermes/collab_board.json")))
        return d.get("tasks", {}).get(task_id, {}).get("state", "")
    except Exception:
        return ""


def group_new_messages(since_ms):
    """拉取芭迪群 since_ms 之后的新消息（卡片+文本，sender 白名单）"""
    env = load_env()
    try:
        def post(url, data):
            req = urllib.request.Request(
                url, json.dumps(data).encode(),
                headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=10).read())

        tok = post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                   {"app_id": env["FEISHU_APP_ID"],
                    "app_secret": env["FEISHU_APP_SECRET"]})["tenant_access_token"]
        url = (f"https://open.feishu.cn/open-apis/im/v1/messages"
               f"?container_id_type=chat&container_id={GROUP_CHAT}"
               f"&page_size=20&sort_type=ByCreateTimeDesc")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if resp.get("code") != 0:
            return []   # API 失败非致命降级（R5 原则）
        msgs = []
        for it in resp["data"].get("items", []):
            if int(it.get("create_time", 0)) <= since_ms:
                continue
            sender = it.get("sender", {})
            if sender.get("id") != BADI_APP_ID:
                continue
            mt = it.get("msg_type", "")
            entry = {"type": mt, "message_id": it.get("message_id", ""),
                     "create_time": it.get("create_time", "")}
            if mt == "text":
                # 纯文本可读（卡不可读）——带原文供 --task 过滤与分型
                try:
                    body = json.loads(it.get("body", {}).get("content", "{}"))
                    entry["text"] = body.get("text", "")[:300]
                except Exception:
                    entry["text"] = ""
            msgs.append(entry)
        return msgs
    except Exception as e:
        log(f"[badi-wait] group poll 非致命失败: {e}")
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--total", type=int, default=1800)
    ap.add_argument("--stall-1", type=int, default=600)
    ap.add_argument("--stall-2", type=int, default=1800)
    args = ap.parse_args()

    # STALL 梯子状态文件（跨调用续计时）
    state_path = os.path.join(STATE_DIR, f".badi_wait_{args.task}.state")
    if os.path.exists(state_path):
        start_ts = json.load(open(state_path))["start_ts"]
        log(f"[badi-wait] 重入：start_ts={start_ts}")
    else:
        start_ts = time.time()
        json.dump({"start_ts": start_ts, "task": args.task}, open(state_path, "w"))
        log(f"[badi-wait] 首次：start_ts={start_ts}")

    # 群消息游标持久化（重入不重复报旧消息）
    cursor_path = os.path.join(STATE_DIR, f".badi_wait_{args.task}.cursor")
    if os.path.exists(cursor_path):
        since_ms = json.load(open(cursor_path))["last_ms"]
    else:
        since_ms = int(time.time() * 1000)

    # 查板快路径
    st = board_task_state(args.task)
    if st in ("closed", "cancelled"):
        log(f"SIGNAL: board_already_{st}")
        return 0

    elapsed0 = time.time() - start_ts
    if elapsed0 > args.total:
        log("WAIT_TIMEOUT_TOTAL_EXCEEDED")
        return 1

    deadline = time.time() + args.total
    log(f"[badi-wait] task={args.task} 单信号等待（群消息30s），上限 {args.total}s")

    while time.time() < deadline:
        msgs = group_new_messages(since_ms)
        if msgs:
            since_ms = int(msgs[-1]["create_time"])
            json.dump({"last_ms": since_ms}, open(cursor_path, "w"))
            for m in msgs:
                if m["type"] == "text":
                    # 纯文本：带 [前缀] 的可 --task 匹配；不带前缀的也报告（可能是异常叙事）
                    if args.task in m.get("text", "") or "[" in m.get("text", ""):
                        log(f"SIGNAL: group_text\nRAW: {m['text']}")
                        return 0
                elif m["type"] == "interactive":
                    # 卡片零内容（R6 实锤）——只报告元信息，分型留给醒后
                    log(f"SIGNAL: group_card\nMETA: {json.dumps(m, ensure_ascii=False)}\n"
                        f"NOTE: 卡片=回合边界。醒后请查 conv/板分型（完成/权限/进度）")
                    return 0
        time.sleep(min(5, GROUP_POLL_INTERVAL))

    # 超时 → STALL 梯子判定（墙钟从 start_ts 起算）
    elapsed = time.time() - start_ts
    json.dump({"last_ms": since_ms}, open(cursor_path, "w"))
    if elapsed >= args.stall_2:
        log(f"WAIT_TIMEOUT STALL_LEVEL=2 elapsed={int(elapsed)}s → 建议发卡升用户")
    elif elapsed >= args.stall_1:
        log(f"WAIT_TIMEOUT STALL_LEVEL=1 elapsed={int(elapsed)}s → 建议催办芭迪")
    else:
        log(f"WAIT_TIMEOUT elapsed={int(elapsed)}s → 转全量对账")
    return 1


if __name__ == "__main__":
    sys.exit(main())
