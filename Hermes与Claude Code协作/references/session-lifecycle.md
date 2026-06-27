# Reference: Session 生命周期

会话的创建、启动、弹窗处理、任务切换、消息发送与维护。

## Session 创建与启动

```bash
# 检查 session 是否已存在
tmux has-session -t claude-session 2>/dev/null

# 不存在 → 创建（140列×40行，适合 CC 输出）
tmux new-session -d -s claude-session -x 140 -y 40

# 启动 Claude Code（正常模式）
tmux send-keys -t claude-session 'cd /path/to/project && claude' Enter

# 等待启动完成
sleep 5 && tmux capture-pane -t claude-session -p -S -10
# 预期看到 ❯ 提示符
```

## 弹窗处理

### 弹窗 1：Workspace Trust（首次进入项目目录）

```
❯ 1. Yes, I trust this folder    ← 默认选项
  2. No, exit
```

盲按 Enter 即可。Trust 弹窗只出现一次。

```bash
sleep 4 && tmux send-keys -t claude-session Enter
```

### 弹窗 2：工具权限提示

```
Allow Claude to edit file src/config.py? (y/n/always)
Allow Claude to run bash command: npm install ...? (y/n/always)
```

**处理方式取决于操作安全性：**

```bash
# 安全操作（读取、编辑项目内文件）→ 直接接受
tmux send-keys -t claude-session 'y' Enter

# 需要审查的操作（网络请求、删除等）→ 先看详情再决定
tmux capture-pane -t claude-session -p -S -10
tmux send-keys -t claude-session 'y' Enter   # 审查后接受
tmux send-keys -t claude-session 'n' Enter   # 审查后拒绝
```

### 预授权配置

通过 `settings.local.json` 预授权常用安全操作，减少运行时弹窗。**v2.1 共识：仅预授权 git（有 reflog 兜底），其余全部保留弹窗。**

```json
{
  "permissions": {
    "allow": [
      "Bash(git *):allow"
    ]
  }
}
```

| 命令 | 决策 | 理由 |
|------|------|------|
| `Bash(git *):allow` | ✅ 预授权 | 协作最高频操作，git 有 reflog 兜底 |
| `Bash(cp *):allow` | ❌ 弹窗 | 可复制敏感文件到任意位置 |
| `Bash(mv *):allow` | ❌ 弹窗 | 可移动/覆盖系统文件 |
| `Bash(python *):allow` | ❌ 弹窗 | 任意代码执行，信任边界不同 |
| `Bash(node *):allow` | ❌ 弹窗 | 同上 |

## 任务命名与切换

新任务必须在 CC 内**先命名**，才能后续通过 `/resume` 找回：

```bash
# 1. CC 空闲时发送 /rename
tmux send-keys -t claude-session '/rename "任务名"' Enter
sleep 2

# 2. Hermes 记录到 task_map
# claude_task_map.json: {"任务名": {"session_name": "任务名", ...}}

# 3. 后续切换回来时
tmux send-keys -t claude-session 'claude --resume "任务名"' Enter
```

> **命名是 resume 的前置条件。** 不 `/rename` 的对话只能用 `--continue` 恢复最近一次，无法按名称精准切回。

单 `claude-session` 内通过 `--resume` 切换对话。`claude_task_map.json`（`~/.hermes/`）作为对话索引，记录任务名→CC 会话名的映射：

```json
{
  "Hermes Profile设计": {
    "session_name": "Hermes Profile设计",
    "description": "多Profile架构设计讨论",
    "created": "2026-05-29"
  },
  "Hermes-Claude协作Skill设计": {
    "session_name": "Hermes-Claude协作Skill设计",
    "description": "重构协作规范skill",
    "created": "2026-05-30"
  }
}
```

> 这是对话索引而非运行时状态追踪器。只需记录任务名和对应 CC 会话名，不维护 status 等运行时字段——任务进度由监控循环（monitoring-debate.md）实时跟踪。

### Resume Session 选择 TUI 界面

`claude --resume <会话名>` 可能触发 TUI 选择界面而非直接恢复：

```
Resume Session
╭─────────────────────────────────────────────────────────────────────────────────────╮
│ ⌕ 健康管理skill                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────╯

  Ctrl+A to show all projects · Ctrl+B to toggle branch · Ctrl+V to preview · Ctrl+R to rename · Type to search · Esc to cancel ·
```

**处理方式：**
- 直接按 `Enter` 选中高亮项（会话名前有 `⌕` 标记即为选中）
- 如果 Enter 无效，尝试 `Escape` 取消 → 回到 bash 提示符 → 再用 `claude --resume <会话ID>` 指定精确的 session UUID
- 也可以先用 `Escape` 取消 → `claude` 启动新会话 → CC 内部再用 `/resume <会话名>` 切换（内部命令更稳定）
- **已知问题：`claude --resume <uuid>` 无效（2026-06-11 确认）**：CC resume 不支持通过 session UUID 恢复，UUID 会被当作搜索词。只能通过名称搜索或方向键选择。此外，CC 退出时打印的 `Resume this session with: claude --resume <uuid>` 中的 UUID 并非直接可用参数。
- **搜索不可靠**：resume 搜索可能找不到已知存在的 session（session 实际名称是一长段消息预览，不含用户记忆的关键词）。超过 3 分钟搜索无果应放弃，改用新建 session + 从输出文件续接（见 SKILL.md pitfalls #111-#113）。

**切换流程：**

```bash
# 1. 当前任务未完成 → 记录到 task_map（任务名 + CC 会话名）
# 2. 如果 CC 正在执行 → Ctrl+C 中断
tmux send-keys -t claude-session C-c
sleep 2

# 3. 从 task_map 获取目标 session_name，发送 --resume
tmux send-keys -t claude-session 'claude --resume "Hermes Profile设计"' Enter

# 4. 轮询确认就绪
sleep 5 && tmux capture-pane -t claude-session -p -S -5
# 看到 ❯ 即就绪
```

## 发送长消息（paste-buffer）

**发送前必须检查 CC 状态：** `capture-pane` 确认 CC 在 `❯` 空闲态且无 `accept edits on` 提示。若 CC 卡在编辑模式，先 `Escape` 退出，否则 paste-buffer 内容会被吞掉。

超过 100 字符必须用 paste-buffer，避免 tmux 输入缓冲溢出。

```bash
# 写入消息到 buffer
tmux load-buffer - <<'EOF'
你的完整任务描述，可以包含多行、代码片段、文件路径列表等。
支持中文、特殊字符、长文本。
EOF

# 粘贴到 session
tmux paste-buffer -t claude-session -d
```

**通过 SSH 远程发送：**

```bash
ssh -p {port} {user}@{host} "tmux load-buffer -t claude-session /dev/stdin" <<'EOF'
长消息内容
EOF
ssh -p {port} {user}@{host} "tmux paste-buffer -t claude-session -d"
```

## 发送前检查 CC 状态

发送消息前务必确认 CC 处于可接收状态。**空闲判断铁律：只看输入框上方有无 emoji 标记（区域①），不看 UI 模式（区域③）。** 三区域模型详见 monitoring-debate.md §2。

常见阻塞状态：

| 区域 | 状态指示 | 含义 | 处理 |
|------|----------|------|------|
| ① | `✶`/`✽`/`✻`/`✢`/`·` + 文字 | CC 正在 thinking | 等待完成 |
| ① | 无 emoji | CC 空闲 | 可发指令（选择合适的发送方式） |
| ③ | `⏵⏵ accept edits on` | accept edits 模式 | 用短 send-keys 不用 paste-buffer；可 BTab 切 plan mode |
| ③ | `⏸ plan mode on` | plan mode | 用短 send-keys 不用 paste-buffer。收到 TASK 后 CC 必须先回 ACK 再出 plan |
| ③ | 无标记 | normal mode | 正常发送，可用 paste-buffer（≤500字符） |
| — | `Enter to select` | CC interview 表单 | 数字+Enter 两拍法选择 |
| — | `Would you like to proceed?` | CC 等待 plan 执行确认 | 审查方案后选择 1/2/3 |
| — | `<!-- PAUSE:... -->` | CC 需要决策 | 按 PAUSE 四种响应处理 |

### 发送后 ACK 验证（v2.1）

发送 TASK 后，30s 内检查 CC 是否回了 ACK（含 task_id + step 回显）：

```bash
# 发送指令后
sleep 5 && tmux capture-pane -t claude-session -p -S -10

# 预期看到 CC 回显：
# 复述: <任务摘要>
# 指纹: task_id=xxx | step=M/N | done=P
```

Hermes 比对 task_id + step 与发送时一致 → 确认送达。不一致或 30s 无 ACK → 重发。

**plan mode 特别注意**：CC 收到 TASK 后必须优先回 ACK（无论何种模式），再出 plan。

### accept edits 专项处理

accept edits 模式下 paste-buffer 长消息会被截断（只收到最后一行）。两种处理方式：

**方式 A：切换到 plan mode（推荐）**
```bash
# Shift+Tab 循环模式：accept edits → plan mode
tmux send-keys -t claude-session BTab
sleep 2 && tmux capture-pane -t claude-session -p -S -3
# 确认出现 "⏸ plan mode on"
# plan mode 下可用短 send-keys，但 paste-buffer 仍可能被截断
```

**方式 B：退出重启**
```bash
# 如果 BTab 无效，/exit 退出后重启 CC
tmux send-keys -t claude-session C-c ; sleep 1
tmux send-keys -t claude-session '/exit' Enter ; sleep 5
# CC 退出后重新启动
tmux send-keys -t claude-session 'claude' Enter
```

**方式 C：scp 兜底（方式 A/B 均失败时）**
```bash
# 将长消息写入文件，scp 到 Windows，让 CC 读取
cat > /tmp/cc_msg.txt << 'EOF'
...长消息内容...
EOF
scp /tmp/cc_msg.txt local-win:"/Users/HUAWEI/cc_msg.txt"
tmux send-keys -t claude-session '读取 C:\\Users\\HUAWEI\\cc_msg.txt，...' Enter
# 短 send-keys 不受 accept edits 影响，可用于触发读文件指令
```

**铁律：paste-buffer 在 accept edits 和 plan mode 下都不可靠。** 优先用 BTab 切 plan mode + 短 send-keys，其次 scp 兜底。

**⚠️ Accept edits 渐进式阻塞（2026-06-10 新增）：** 阻塞是渐进加重的——刚启动时 send-keys 正常，CC 执行多次工具调用后间歇吞输入，最终可能进入完全阻塞（所有按键被吞，C-c×3/Escape//exit 全无效）。详见 [error-recovery.md §10](references/error-recovery.md)。**预防：长任务减少工具调用频率，中途 C-c+重发比等 CC 自然结束更安全。**

### Plan Mode Interview 表单

CC 在 plan mode 中可能弹出 interview 表单收集需求：

```
←  [×] Card 范围  [ ] Header 颜色  √ Submit  →

消息类型的动态选颜色？

> 1. 需要，按类型配色
  2. 不需要，统一默认
  3. 不需要 header
─────────────────────────────────────
  5. Chat about this
  6. Skip interview and plan immediately

Enter to select · Tab/Arrow keys to navigate · Esc to cancel
```

**选择方式：数字和 Enter 分两拍发送**（间隔 ≥ 300ms），不可合并为单次 send-keys。两拍法：先 `send-keys 'N'` → sleep 0.5s → 再 `send-keys Enter`。单次 `send-keys '2' Enter` 可能被 CC 忽略不生效。选择后 capture-pane 验证是否生效；未生效则 Ctrl+C 取消 → 等 ❯ → 重发消息避开 interview 表单。

```bash
# 选择第 2 项（两拍法）
tmux send-keys -t claude-session '2' ; sleep 0.5 ; tmux send-keys -t claude-session Enter
# 跳过 interview 直接看 plan
tmux send-keys -t claude-session '6' ; sleep 0.5 ; tmux send-keys -t claude-session Enter
```

⚠️ 注意：表单中的 `[ ]` checkbox 和 `>` 选项是两套交互。Navigating with Tab cycles through checkboxes before reaching the options.

### Plan Mode Multi-Step Interview（多步骤表单）

CC 的 interview 可能是多步骤的——选择初始选项后，CC 会追问后续问题：

```
←  [×] 优先确认  [×] 端口情况  √ Submit  →

方案中有几个待确认点，巽饕先看哪个？

> 1. 先处理当前 legal 孤儿
  2. 先讨论方案设计
  3. 直接开始部署
─────────────────────────────────────────────────
  5. Chat about this
  6. Skip interview and plan immediately
```

选择后 CC 可能追问第二题：

```
←  [×] 优先确认  [×] 端口情况  √ Submit  →

各 profile 的 Dashboard 端口情况？

> → 共享 9119 端口
─────────────────────────────────────────────────
  5. Chat about this
  6. Skip interview and plan immediately
```

**Review & Submit 流程：** 回答完所有问题后，CC 显示复查页：

```
Review your answers

 ● 先看哪个？
   → 先讨论方案设计
 ● 端口情况？
   → 共享 9119 端口

Ready to submit your answers?

> 1. Submit answers
  2. Cancel
```

- **Submit（1）**：提交答案，CC 根据答案继续执行
- **Cancel（2）**：返回 "User declined to answer questions"，**直接退入自由聊天模式**——此时可以发送正常消息与 CC 对话，不再受 interview 约束

**退出路径：**
- 任何时候选 `6. Skip interview and plan immediately` → 跳过 interview，CC 直接出 plan
- 任何时候选 `5. Chat about this` → 进入自由聊天（但可能仍受 interview 状态影响）
- Review 页选 `2. Cancel` → 确认退出，回到 `❯` compose 区，可正常发消息对话

## 跨平台文件传输

当需要将 CC 本地（Windows）的整个 skill 目录传到云端时：

### 推荐：tar + SSH 管道（可靠处理含空格路径）

```bash
# 从 Windows 传到云端（在 tmux / CC 中执行）
cd "D:/claude vscode" && tar czf - health-management-skill | ssh -p 2222 ubuntu@100.90.24.4 "cd /home/ubuntu/.hermes/profiles/family/skills/family/health-management && tar xzf -"
```

**优势**：
- 自动创建所有子目录（SCP 对复杂嵌套目录常失败）
- 正确处理 Windows 路径中的空格
- 使用 SSH 端口可由 `~/.ssh/config` 指定

**注意**：tar 会创建一个与源目录同名的子目录（如 `health-management-skill/`）。传输后需将内容移上一级：
```bash
cd /dest/path && mv subdir/* . && rmdir subdir
```

### 避免：SCP 含空格路径

```bash
# 可能失败——空格导致路径解析问题
scp -P 2222 -r "HUAWEI@host:D:\\claude vscode\\project" .
```

SCP 在以下场景易出错：源路径含空格、嵌套目录层数深、目标目录不存在。`tar + SSH` 管道是更稳定的替代方案。\n\n

正常情况下 `claude-session` 持久运行。仅在 CC 崩溃无法恢复时重建：

```bash
tmux kill-session -t claude-session 2>/dev/null
tmux new-session -d -s claude-session -x 140 -y 40
tmux send-keys -t claude-session 'cd /path/to/project && claude' Enter
# 处理弹窗后，用 --continue 恢复未完成的对话
```

## 新任务 vs 进入现有对话（铁律）

**必须区分两个场景：**

| 场景 | 操作 | 原因 |
|------|------|------|
| 在现有 CC 对话中继续/恢复 | `--resume` 或直接发消息 | 上下文连续 |
| 开启**新讨论话题**（与本对话无关） | `/exit` → `claude` 新启动 → 四步法 | 新话题需要干净的上下文 |

**常见错误（2026-06-17 实战）**：Hermes 需要与 CC 讨论一个全新的设计话题，但直接在 CC 现有的法律WIKI对话中发送讨论内容——导致 CC 在已加载的文件上下文中处理不相关的任务。

**正确流程：**

```bash
# 1. /exit 退出当前 CC 对话
tmux send-keys -t claude-session '/exit' Enter
sleep 3

# 2. 确认 CC 已退出（看到 bash 提示符）
tmux capture-pane -t claude-session -p -S -3

# 3. cd 到项目目录 → claude 启动新对话 → HERMES-ACTIVATE → /rename
tmux send-keys -t claude-session 'cd /d "D:\claude vscode"' Enter
sleep 2
tmux send-keys -t claude-session 'claude --model glm-5-turbo' Enter
sleep 8
# 处理弹窗 → 确认空闲
tmux send-keys -t claude-session '<!-- HERMES-ACTIVATE -->' Enter
sleep 3
tmux send-keys -t claude-session '/rename Hermes:任务名' Enter
sleep 2

# 4. 更新 task_map → 开始新任务
```

**判别信号**：用户说"跟CC讨论XX"且 XX 与 CC 当前对话内容无关 → 必须新建对话。若用户说"让CC继续做XX"且 XX 是当前对话的延伸 → 直接发消息。

## 端到端示例：新任务启动

```bash
# 1. 检查 session
tmux has-session -t claude-session 2>/dev/null && echo ALIVE || echo DEAD

# 2. 不存在则创建并启动 CC
tmux new-session -d -s claude-session -x 140 -y 40
tmux send-keys -t claude-session 'cd /path/to/project && claude' Enter
sleep 5
# 处理 Trust 弹窗
tmux send-keys -t claude-session Enter

# 3. 等待 CC 就绪 + 激活协作模式
sleep 3 && tmux capture-pane -t claude-session -p -S -5
# 看到 ❯

# 3b. 发送协作激活标记
tmux send-keys -t claude-session '<!-- HERMES-ACTIVATE -->' Enter
sleep 1

# 4. 发送任务（paste-buffer）
tmux load-buffer - <<'EOF'
任务：修复 scripts/fetch_bidding.py 中的 UTF-8 编码问题
要求：统一 UTF-8，添加异常处理，不改变功能逻辑
完成后运行测试验证。
EOF
tmux paste-buffer -t claude-session -d

# 5. 记录到 task_map（任务名 + CC 会话名）

# 6. 进入监控循环（参考 monitoring-debate.md）
```
