# Reference: 错误恢复

CC 执行过程中的各类异常场景及恢复流程。

## 1. CC 崩溃

**检测：** `capture-pane` 连续 3 次输出相同，且显示 shell 提示符（非 `❯`）。

```bash
tmux list-panes -t claude-session -F '#{pane_alive}'
# false = pane 已死
```

**恢复：**

```
pane 存活但 CC 无响应
    ├── Ctrl+C 中断 → 观察 5 秒
    │    ├── 恢复正常 → 继续
    │    └── 仍无响应 → /exit → 重新启动 CC → --continue 恢复
    │
└── pane 已死
    ├── session 可恢复
    │    → 重建 CC 进程 → 处理弹窗 → --continue → 补发任务摘要
    └── session 不可恢复
         → 新建 session → 新建对话 → 重发任务（注明"此前尝试失败"）
```

## 2. 权限弹窗误拒

**场景：** 弹窗中误按 `n`，CC 报告操作未执行。

```bash
# 检测：capture-pane 看到 "Permission denied" 或操作未执行

# CC 通常会在被拒后再次提示，直接接受即可
tmux send-keys -t claude-session 'y' Enter

# 如果弹窗已消失，让 CC 重试
tmux load-buffer - <<'EOF'
上一步操作被拒绝了，请重新尝试。
EOF
tmux paste-buffer -t claude-session -d

# 如果是频繁出现的操作，加入 settings.local.json 预授权
```

## 3. API 限流 / 计费错误

**检测：** 输出含 `rate_limit`、`overloaded`、`billing_error`。

```
限流/过载
    ├── 第 1 次重试：等待 60 秒后重发命令
    ├── 第 2 次重试：等待 120 秒
    ├── 第 3 次重试：等待 300 秒
    └── 3 次仍失败
         ├── 有 fallback-model → 降级重试
         └── 无降级方案 → 汇报用户："CC API 限流，已重试 3 次"

计费错误 → 直接汇报用户，不自动重试
```

## 4. 工具执行失败

**检测：** 输出含 `Error:`、`Command failed`、非零退出码。

```
工具失败
    ├── 读取失败（文件不存在/权限不足）
    │    → 补全路径或修正权限后重试
    ├── 编辑失败（文件被锁定/已修改）
    │    → 重新读取文件确认状态后重试
    ├── 命令执行失败
    │    ├── 环境问题（依赖缺失/路径错误）→ 修复环境后重试
    │    ├── 方案问题（命令本身有误）→ 进入辩论协议，质疑 CC 方案
    │    └── 数据问题（输入格式错误）→ 补正输入后重试
    └── 无法判断类型 → 将完整错误信息提交 Hermes 裁决
```

## 5. SSH 连接断开

> **首次诊断或连接不通：先走 [ssh-diagnostics](references/ssh-diagnostics.md) 决策树定位根因。**

```
SSH 断开
    ├── 重试连接（最多 3 次，间隔 10 秒）
    │
    ├── 恢复后检查 tmux session
    │    ├── session 在
    │    │    ├── CC 仍在执行 → 继续监控
    │    │    ├── CC 等待输入 → 从断点继续
    │    │    └── CC 已退出 → 按崩溃恢复处理
    │    └── session 已亡
    │         → 重建 session → --continue 恢复对话
    │
    └── 无法恢复 → 汇报用户
```

## 6. 上下文窗口耗尽

**检测信号：** CC 重复已完成操作、"忘记"已处理文件、输出变短或出现幻觉。

**恢复流程（三步）：**

```bash
# Step 1：持久化已完成进度（防止 /compact 后丢失中间状态）
tmux load-buffer - <<'EOF'
请将已完成的文件修复记录写入 .claude/progress.md，
格式：- 文件名：修复内容摘要
EOF
tmux paste-buffer -t claude-session -d
sleep 10 && tmux capture-pane -t claude-session -p -S -5

# Step 2：执行 /compact
tmux send-keys -t claude-session '/compact focus on remaining tasks' Enter
sleep 5 && tmux capture-pane -t claude-session -p -S -5

# Step 3：补发进度摘要
tmux load-buffer - <<'EOF'
进度恢复：已完成 fetch_bidding.py、clean_data.py 的修复。
剩余：format_output.py、export_excel.py。
修复规范：统一 UTF-8、添加异常处理。
请继续处理剩余文件。进度记录见 .claude/progress.md
EOF
tmux paste-buffer -t claude-session -d
```

compact 后 CLAUDE.md 完整保留，进度文件作为 CC 的参考。

## 7. 事实校验未通过

CC 的结论与 Hermes 的观察不一致（详见 monitoring-debate.md 事实校验节）。

处理方式：
- 向 CC 发追问（附带具体证据）
- CC 修正后重新校验
- CC 坚持原报告 → 标记「置信度低」回传用户，附 Hermes 独立观察

## 端到端示例：处理 API 限流

```bash
# 1. 监控中发现限流
sleep 10 && tmux capture-pane -t claude-session -p -S -20
# → 输出含 "rate_limit"

# 2. 等待 60 秒后重发
sleep 60
tmux capture-pane -t claude-session -p -S -5
# → CC 可能自动重试了，检查状态
# → 如果 ❯ 空闲，CC 放弃了 → 重发任务
tmux load-buffer - <<'EOF'
请继续上一步操作。
EOF
tmux paste-buffer -t claude-session -d

# 3. 继续监控
sleep 10 && tmux capture-pane -t claude-session -p -S -20
```
