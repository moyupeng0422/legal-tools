#!/usr/bin/env python3
"""
Workbuddy回复轮询脚本（v3.0 备用通道）

注意：v3.0 架构中，长任务监控改用 scripts/badi_monitor.py（SSH 轮询）。
本脚本降级为：
1. 初始任务确认：发消息后确认Workbuddy已收到
2. SSH 不可用时的备用通道
3. 检测Workbuddy的卡片通知

用法：
  python3 badi_poll.py <last_check_timestamp>

功能：
  - 每30秒轮询一次飞书群消息（ListMessage API）
  - 检测到Workbuddy新回复后，下载文件并打印完整内容
  - 找到回复 exit 0，20 分钟超时 exit 1

输出格式：
  FOUND:<时间戳>:<消息类型>:<内容预览>
  FILE: <文件名>
  CONTENT: <文件完整内容>
"""
import json, subprocess, sys, os, time

HOME = os.path.expanduser("~")
env = open(f"{HOME}/.hermes/.env").read()
secret = ""
for line in env.split("\n"):
    if line.startswith("FEISHU_APP_SECRET="):
        secret = line.split("=", 1)[1].strip()
        break

last_check = int(sys.argv[1]) if len(sys.argv) > 1 else 0
start_time = time.time()
MAX_WAIT = 1200  # 20 minutes

def get_token():
    r = subprocess.run([
        "curl", "-s", "-X", "POST", "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"app_id":"cli_aa9325017e78dbc2","app_secret":secret})
    ], capture_output=True, text=True)
    return json.loads(r.stdout).get("tenant_access_token", "")

while time.time() - start_time < MAX_WAIT:
    token = get_token()
    if not token:
        time.sleep(10)
        continue
    
    r2 = subprocess.run([
        "curl", "-s", "https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id=oc_11ad7cd4f6b7e8e44626b226331dd5bd&page_size=30&sort_type=ByCreateTimeDesc",
        "-H", f"Authorization: Bearer {token}"
    ], capture_output=True, text=True)
    data = json.loads(r2.stdout)
    items = data.get("data", {}).get("items", [])
    
    new_msgs = []
    for item in items:
        sender = item.get("sender", {}).get("id", "")
        ct = int(item.get("create_time", "0"))
        if sender == "cli_aa940825f0781cfa" and ct > last_check:
            new_msgs.append(item)
    
    if new_msgs:
        new_msgs.sort(key=lambda x: int(x.get("create_time", "0")))
        for m in new_msgs:
            ct = int(m.get("create_time", "0"))
            mtype = m.get("msg_type", "?")
            body = m.get("body", {}).get("content", "")
            from datetime import datetime
            ts = datetime.fromtimestamp(ct/1000).strftime("%H:%M:%S")
            print(f"FOUND:{ct}:{mtype}:Workbuddy 回复于{ts}")
            print(f"  content: {body[:500]}")
            
            if mtype == "file":
                try:
                    fk_data = json.loads(body)
                    fk = fk_data.get("file_key", "")
                    fn = fk_data.get("file_name", "")
                    outpath = f"/tmp/badi_replies_latest/{fn}"
                    subprocess.run(["mkdir", "-p", "/tmp/badi_replies_latest"])
                    r3 = subprocess.run([
                        "curl", "-s", "-o", outpath, "-w", "%{http_code}",
                        f"https://open.feishu.cn/open-apis/im/v1/messages/{m['message_id']}/resources/{fk}?type=file",
                        "-H", f"Authorization: Bearer {token}"
                    ], capture_output=True, text=True)
                    print(f"  FILE: {fn} (HTTP {r3.stdout.strip()})")
                    with open(outpath, encoding="utf-8", errors="replace") as f:
                        preview = f.read(2000)
                    print(f"  CONTENT:\n{preview}")
                except Exception as e:
                    print(f"  FILE_ERROR: {e}")
            print("---")
        sys.exit(0)
    
    elapsed_min = int((time.time() - start_time) / 60)
    sys.stderr.write(f"[{elapsed_min}m] Checking... no new reply\n")
    sys.stderr.flush()
    time.sleep(30)

sys.stderr.write(f"[TIMEOUT] Workbuddy未在{MAX_WAIT//60}分钟内回复\n")
sys.exit(1)
