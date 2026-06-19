#!/usr/bin/env python3
"""
Workbuddy长任务 SSH 监控脚本（v3.0）

用法：
  python3 badi_monitor.py <task_id> <timeout_minutes>

功能：
  - 每 30 秒 SSH cat status.json，检测 current_task.status 变化
  - completed → 打印 conv 内容 → exit 0
  - waiting → 打印 conv 内容 → exit 1（审阅模式）
  - writing 持续超过 30 分钟无进展 → exit 2（超时告警）
  - failed → 打印 conv 内容 → exit 3

退出码：
  0 = completed（正常完成）
  1 = waiting（需审阅）
  2 = timeout（writing 超 30 分钟无进展）
  3 = failed（WorkBuddy标记失败）
  4 = 未找到匹配的 current_task.id
  5 = SSH 连接失败

依赖：~/.ssh/config 已配置 local-win alias
"""

import subprocess, sys, time, json, os, re

SSH_CMD = ["ssh", "local-win", "powershell", "-Command"]
COLLAB_DIR = "D:\\workbuddy\\Claw\\hermes_collab\\"
STATUS_FILE = os.path.join(COLLAB_DIR, "status.json")
POLL_INTERVAL = 30
WRITING_TIMEOUT = 30  # minutes before declaring writing stalled

def ssh_cat(filepath):
    """SSH cat a file from Workbuddy's machine. Returns (content, error)."""
    cmd = SSH_CMD + [f"Get-Content '{filepath}' -Encoding UTF8 -Raw"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return None, r.stderr.strip()
    return r.stdout, None

def main():
    if len(sys.argv) < 2:
        print("Usage: badi_monitor.py <task_id> [timeout_minutes]")
        sys.exit(5)
    
    task_id = sys.argv[1]
    timeout_min = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    start_time = time.time()
    writing_start = None

    while True:
        elapsed = (time.time() - start_time) / 60
        
        # SSH read status.json
        content, err = ssh_cat(STATUS_FILE)
        if err:
            print(f"[{int(elapsed)}m] SSH error: {err}")
            time.sleep(POLL_INTERVAL)
            continue

        try:
            status = json.loads(content)
        except json.JSONDecodeError:
            print(f"[{int(elapsed)}m] status.json parse error, retrying...")
            time.sleep(POLL_INTERVAL)
            continue

        task = status.get("current_task", {})
        task_status = task.get("status", "")
        task_id_found = task.get("id", "")

        # Detect task ID mismatch
        if task_id_found and task_id not in task_id_found:
            # Task might have changed — check conv_files for completion
            conv_files = status.get("conv_files", {})
            matching = [k for k in conv_files if task_id in k]
            if matching and all(conv_files[k] == "completed" for k in matching):
                print(f"[{int(elapsed)}m] Task '{task_id}' already completed (found in conv_files).")
                sys.exit(0)
            print(f"[{int(elapsed)}m] current_task.id='{task_id_found}', waiting for '{task_id}'...")
            time.sleep(POLL_INTERVAL)
            continue

        # Check time elapsed
        if elapsed > timeout_min:
            print(f"[TIMEOUT] Task '{task_id}' did not complete within {timeout_min} minutes. Last status: {task_status}")
            sys.exit(2)

        # Dispatch by status
        if task_status == "completed":
            print(f"[{int(elapsed)}m] ✅ Status=completed. Reading conv...")
            conv_file = task.get("conv_file", "")
            conv_path = os.path.join(COLLAB_DIR, conv_file) if conv_file else ""
            if conv_path:
                conv, _ = ssh_cat(conv_path)
                if conv:
                    print(f"=== {conv_file} ===\n{conv[:3000]}")
            sys.exit(0)

        elif task_status == "waiting":
            print(f"[{int(elapsed)}m] ⏸ Status=waiting (needs review). Reading conv...")
            conv_file = task.get("conv_file", "")
            conv_path = os.path.join(COLLAB_DIR, conv_file) if conv_file else ""
            if conv_path:
                conv, _ = ssh_cat(conv_path)
                if conv:
                    print(f"=== {conv_file} ===\n{conv[:3000]}")
            sys.exit(1)

        elif task_status == "failed":
            print(f"[{int(elapsed)}m] ❌ Status=failed. Reading conv for error details...")
            conv_file = task.get("conv_file", "")
            conv_path = os.path.join(COLLAB_DIR, conv_file) if conv_file else ""
            if conv_path:
                conv, _ = ssh_cat(conv_path)
                if conv:
                    print(f"=== {conv_file} ===\n{conv[:3000]}")
            sys.exit(3)

        elif task_status == "writing":
            if writing_start is None:
                writing_start = time.time()
            writing_elapsed = (time.time() - writing_start) / 60
            phase_info = f"phase {task.get('phase_n', '?')}/{task.get('phase_of', '?')}"
            print(f"[{int(elapsed)}m] writing... {phase_info}, writing phase: {int(writing_elapsed)}m")
            
            if writing_elapsed > WRITING_TIMEOUT:
                print(f"[STALLED] Writing phase > {WRITING_TIMEOUT} minutes without status change.")
                sys.exit(2)
            
            time.sleep(POLL_INTERVAL)

        else:
            # Unknown status or no task
            print(f"[{int(elapsed)}m] No task or unknown status. status.json says: {task_status}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
