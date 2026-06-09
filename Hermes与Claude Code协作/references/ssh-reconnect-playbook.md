# Reference: SSH 断连恢复实战手册

> 来源：2026-06-02 health-plan-v2 协作中 SSH 断开后的恢复实录

## 症状识别

SSH 断开后，tmux `claude-session` 不会消失，但内部进程已回退到本地 bash。**关键陷阱**：`capture-pane` 会返回 scrollback 中的 CC 旧内容（表格、方案、提示符），看起来 CC 仍在运行。

### 判断 SSH 是否断开

```bash
# 方法1：看最后一行提示符
tmux capture-pane -t claude-session -p | tail -1
# 如果看到 $ 或 ~$ → bash（SSH已断）
# 如果看到 ❯ 或 ⏸ → CC（正常运行）

# 方法2：直接测SSH
ssh -o ConnectTimeout=10 -o BatchMode=yes <host-alias> "echo SSH_OK"
```

### 常见误判

```
capture-pane 输出:
  ┌─────────────┬────────┐
  │   指标      │   v1   │    ← 这是 CC 1小时前的输出！
  ├─────────────┼────────┤
  ...
  >             ← 看起来像 CC 提示符，实际是 bash 残留

真实状态：bash 在 ubuntu@VM:~$，只是 scrollback 里有旧内容
```

## 恢复流程

### Step 1：确认 SSH 可用
```bash
ssh -o ConnectTimeout=10 <host-alias> "echo SSH_OK"
# 输出 SSH_OK → 继续
# 超时/refused → 走 ssh-diagnostics.md 诊断
```

### Step 2：在 tmux 内重连 SSH
```bash
tmux send-keys -t claude-session C-c C-c   # 清理残留
sleep 1
tmux send-keys -t claude-session 'ssh <host-alias>' Enter
sleep 5
# 验证是否进入 Windows
tmux capture-pane -t claude-session -p | tail -1
# 应看到: <用户>@<主机名> ...>
```

### Step 3：恢复 CC
```bash
tmux send-keys -t claude-session 'd:' Enter
sleep 1
tmux send-keys -t claude-session 'cd "D:\claude vscode"' Enter
sleep 1
tmux send-keys -t claude-session 'claude --continue' Enter
# 验证 CC 启动
sleep 8
tmux capture-pane -t claude-session -p | tail -3
# 应看到: ⏸ plan mode on 或 ❯ 提示符
```

### Step 4：激活协作协议
```bash
# CC 启动后，先切换出 accept-edits 模式（如果卡住）
tmux send-keys -t claude-session BTab   # Shift+Tab
sleep 2
# 再发送激活标记（注意：在 CC 提示符下，不是 bash）
tmux send-keys -t claude-session "<!-- HERMES-ACTIVATE -->" Enter
```

## ⚠️ 常见错误

1. **在 bash 下发送 `<!-- HERMES-ACTIVATE -->`**：bash 会把 `!` 解释为历史扩展，报 `event not found`。必须确认 CC 已启动再发。

2. **发送 `'<!-- ... -->'` 带单引号**：CC 会原样显示单引号，可能影响解析。直接发送不带引号的内容。

3. **断连后不重连直接发指令**：`capture-pane` 显示 CC 内容 ≠ CC 还在运行。先走本手册的 Step 1-3 恢复连接。
