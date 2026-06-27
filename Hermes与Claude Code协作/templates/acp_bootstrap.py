#!/usr/bin/env python3
"""ACP 快速引导脚本 — 验证 Hermes → Windows claude-agent-acp 连通性

用法:
    设置环境变量 ANTHROPIC_API_KEY 后直接运行。
    或通过命令行传参: python3 acp_bootstrap.py <api_key>

验证内容:
    1. SSH pipe 连接 Windows
    2. ACP initialize 握手
    3. session/new 创建会话
    4. session/prompt 发送并接收回复
"""

import subprocess, json, threading, time, sys, os

# ============ 配置 ============
SSH_TARGET = "local-win"
API_KEY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ANTHROPIC_API_KEY", "")
BASE_URL = "https://<API_服务商域名>/api/anthropic"
MODEL = "glm-5-turbo"
TIMEOUT = {"init": 15, "session": 20, "prompt": 90, "cleanup": 5}

if not API_KEY:
    print("ERROR: 请设置 ANTHROPIC_API_KEY 或传参: python3 acp_bootstrap.py <key>")
    sys.exit(1)


def read_line(pipe, timeout=10):
    r = [None]; d = threading.Event()
    threading.Thread(target=lambda: (setattr(r, '__setitem__', None), r.__setitem__(0, pipe.readline()) or d.set()) if not d.set() else None, daemon=True).start()
    # 上面的 lambda 太复杂，用更标准的方式:
    result = [None]; done = threading.Event()
    def _reader():
        try: result[0] = pipe.readline()
        except: result[0] = ""
        done.set()
    threading.Thread(target=_reader, daemon=True).start()
    return result[0] if done.wait(timeout) else None


# 构造 SSH 远程命令（cmd.exe 语法，注入所有必要环境变量）
REMOTE_CMD = (
    f"set ANTHROPIC_BASE_URL={BASE_URL} && "
    f"set ANTHROPIC_AUTH_TOKEN={API_KEY} && "
    f"set ANTHROPIC_MODEL={MODEL} && "
    f"set ANTHROPIC_DEFAULT_SONNET_MODEL={MODEL} && "
    f"claude-agent-acp"
)


def main():
    print("=" * 50)
    print("  ACP Bootstrap Test")
    print(f"  SSH: {SSH_TARGET} → claude-agent-acp")
    print("=" * 50)

    # Step 1: 启动 ACP
    print("\n[1/4] Starting ACP process...")
    proc = subprocess.Popen(
        ["ssh", "-o", "ConnectTimeout=10", SSH_TARGET, REMOTE_CMD],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    time.sleep(1.5)
    if proc.poll() is not None:
        print(f"  FAIL: process exited early (code {proc.returncode})")
        print(f"  stderr: {proc.stderr.read()[:500]}")
        return 1
    print("  OK")

    # Step 2: initialize
    print("\n[2/4] ACP initialize...")
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": 1, "clientInfo": {"name": "hermes-bootstrap"}, "capabilities": {}}
    }) + "\n")
    proc.stdin.flush()

    # 跳过无 id 的推送行
    resp = None
    deadline = time.time() + TIMEOUT["init"]
    while time.time() < deadline:
        line = read_line(proc.stdout, max(1, deadline - time.time()))
        if not line or not line.strip():
            continue
        try:
            obj = json.loads(line.strip())
            if "id" in obj:
                resp = obj; break
        except json.JSONDecodeError:
            continue

    if not resp or "error" in resp:
        print(f"  FAIL: {resp}")
        proc.stdin.close(); proc.wait(5); return 1
    print(f"  OK — server capabilities: {list(resp['result'].get('capabilities', {}).keys())}")

    # Step 3: session/new
    print("\n[3/4] Creating session...")
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "session/new",
        "params": {"cwd": "C:\\", "mcpServers": []}
    }) + "\n")
    proc.stdin.flush()

    resp = None
    deadline = time.time() + TIMEOUT["session"]
    while time.time() < deadline:
        line = read_line(proc.stdout, max(1, deadline - time.time()))
        if not line or not line.strip():
            continue
        try:
            obj = json.loads(line.strip())
            if "id" in obj:
                resp = obj; break
        except json.JSONDecodeError:
            continue

    if not resp or "error" in resp:
        print(f"  FAIL: {resp}")
        proc.stdin.close(); proc.wait(5); return 1
    sid = resp["result"]["sessionId"]
    model = resp["result"].get("models", {}).get("currentModelId", "?")
    print(f"  OK — session={sid[:12]}... model={model}")

    # Step 4: session/prompt
    print("\n[4/4] Sending prompt...")
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": 3, "method": "session/prompt",
        "params": {"sessionId": sid, "prompt": [{"type": "text", "text": "回复OK即可"}]}
    }) + "\n")
    proc.stdin.flush()

    text_chunks = []
    resp = None
    deadline = time.time() + TIMEOUT["prompt"]
    while time.time() < deadline:
        line = read_line(proc.stdout, max(1, deadline - time.time()))
        if not line or not line.strip():
            continue
        try:
            obj = json.loads(line.strip())
            if "id" in obj:
                resp = obj; break
            # 流式事件: method="session/update"
            update = obj.get("params", {}).get("update", {})
            su = update.get("sessionUpdate", "")
            if su == "agent_message_chunk":
                text_chunks.append(update.get("content", {}).get("text", ""))
        except json.JSONDecodeError:
            continue

    if not resp or "error" in resp:
        print(f"  FAIL: {resp}")
        proc.stdin.close(); proc.wait(5); return 1

    reply = "".join(text_chunks).strip()
    usage = resp["result"].get("usage", {})
    print(f"  OK — reply: '{reply}'")
    print(f"  tokens: {usage.get('inputTokens', '?')}+{usage.get('outputTokens', '?')}")

    # Cleanup
    proc.stdin.close()
    proc.wait(TIMEOUT["cleanup"])

    print(f"\n{'=' * 50}")
    print(f"  ALL TESTS PASSED")
    print(f"{'=' * 50}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
