# Reference: 错误恢复

CC 执行过程中的各类异常场景及恢复流程。

## Table of Contents

- [1. CC 崩溃](#1-cc-崩溃)
- [2. 权限弹窗误拒](#2-权限弹窗误拒)
- [3. API 限流 / 计费错误](#3-api-限流-计费错误)
- [4. 工具执行失败](#4-工具执行失败)
- [5. SSH 连接断开](#5-ssh-连接断开)
- [6. 上下文窗口耗尽](#6-上下文窗口耗尽)
- [7. 事实校验未通过](#7-事实校验未通过)
- [8. CC 长任务 SSH 断连恢复（2026-06-10 实战）](#8-cc-长任务-ssh-断连恢复（2026-06-10-实战）)
- [9. CC Germinating 超长卡住（2026-06-10 实战）](#9-cc-germinating-超长卡住（2026-06-10-实战）)
- [10. Accept Edits 渐进式阻塞（2026-06-10 实战）](#10-accept-edits-渐进式阻塞（2026-06-10-实战）)
  - [阻塞渐进演变](#阻塞渐进演变)
  - [触发条件](#触发条件)
  - [恢复路径](#恢复路径)
  - [预防措施](#预防措施)
  - [与 §9 的关系](#与-9-的关系)
- [11. CC Session 名不匹配用户记忆（2026-06-11 实战）](#11-cc-session-名不匹配用户记忆（2026-06-11-实战）)
- [12. /exit CC 丢失当前批次进度（2026-06-11 实战）](#12-exit-cc-丢失当前批次进度（2026-06-11-实战）)
- [13. Edit/Write 静默失败产生数据缺口（2026-06-10 实战）](#13-editwrite-静默失败产生数据缺口（2026-06-10-实战）)
- [14. Auto-compact 导致批量输出文件重复 + CC 搜索浪费（2026-06-11 实战）](#14-auto-compact-导致批量输出文件重复-cc-搜索浪费（2026-06-11-实战）)
- [15. 批量任务完成后数据完整性验证（2026-06-11 实战）](#15-批量任务完成后数据完整性验证（2026-06-11-实战）)
  - [验证方法（Hermes 从云端 SSH 执行）](#验证方法（hermes-从云端-ssh-执行）)
  - [验证后处理](#验证后处理)
  - [SSH PowerShell `$_` 变量 corruption 注意事项](#ssh-powershell-_-变量-corruption-注意事项)
- [12. 长任务监控节奏优化（2026-06-10 实战）](#12-长任务监控节奏优化（2026-06-10-实战）)
- [16. Accept Edits 模式下 Bash 权限弹窗不响应（2026-06-17 实战）](#16-accept-edits-模式下-bash-权限弹窗不响应（2026-06-17-实战）)
- [17. CC 写入路径不一致（2026-06-17 实战）](#17-cc-写入路径不一致（2026-06-17-实战）)
- [端到端示例：处理 API 限流](#端到端示例：处理-api-限流)

---

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

> ⚠️ **Tailscale relay 下 SSH keepalive 无效（2026-06-10 实测）**：当 Tailscale 走 DERP relay（非直连 P2P）时，`ServerAliveInterval=5`、`ServerAliveCountMax=3`、`TCPKeepAlive=yes` 等参数**无法防止 SSH 断连**——实测仍每 2-3 分钟 Broken pipe。relay 链路本身不稳定（丢包率高、延迟 300-800ms），TCP keepalive 探针不足以维持连接。**不要在此场景浪费精力调 keepalive 参数**——接受断连现实，按 §8 的恢复流程快速重连即可。判断方法：`tailscale ping` 显示 `via DERP(xxx)` 且 `direct connection not established` = relay 模式。

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

## 8. CC 长任务 SSH 断连恢复（2026-06-10 实战）

**场景**：CC 在执行批量循环任务（如 MCP 分页导出数千条数据）时，SSH 因 Tailscale relay 不稳定反复断连（Broken pipe），CC 进程被杀。需要在 CC 重启后从断点继续。

**恢复流程（已验证 3 轮）：**

```
SSH 断连 → CC 被杀
    ① 检查 Tailscale：tailscale status / tailscale ping（relay 假活时 down+up）
    ② 重连 SSH：ssh -o ConnectTimeout=20 -o ServerAliveInterval=10 <ssh-alias>
    ③ 重建 tmux（如需要）
    ④ SSH → cd → claude 启动 CC
    ⑤ 激活四步法（HERMES-ACTIVATE → rename → task_map）
    ⑥ 发恢复指令（关键：让 CC 自己确认进度）
```

**关键技巧——让 CC 自查文件续接：**

不要凭 Hermes 记忆的 offset 告诉 CC 从哪继续（记忆可能因 compaction 不准确）。直接发：

```
读取 <目标文件> 的末尾 20 行，确认最后写入到哪个 offset，
然后从 offset+50 继续拉取并写入。不要问我要不要继续，一直跑完。
```

CC 能通过 Read 文件末尾确定最后的 offset 和日期范围，自动跳到正确位置继续。即使 compaction 发生过，只要文件存在，CC 就能恢复。

**Compaction 后的自动恢复**：CC 在执行循环任务时触发 `/compact`，压缩后可能"忘记"当前 offset。但如果目标文件持续写入（Edit append），CC re-read 文件后能自动定位到正确 offset。实测：CC compaction 后自动跳过已写入的 offset，从断点继续。

## 9. CC Germinating 超长卡住（2026-06-10 实战）

**检测**：capture-pane 显示 `✻ Germinating for 10m+` 无变化。

**判别**：
- 正常 Germinating 通常 30s-2min 完成
- **超过 3 分钟**且 pane 无任何变化（工具调用标记、输出行）→ 卡住
- 连续 3 次 capture-pane（间隔 15s）内容完全相同 → 确认卡住

**恢复**：
```
首次中断：C-c
    ├── 恢复响应（出现新输出）→ 观察结果，可能 MCP 已返回+Edit 已成功写入
    └── 仍无响应（3min+）→ C-c×2 或 Escape+C-c
        ├── 恢复 → 继续
        └── 仍无响应 → 可能 SSH 已断（检查 `tmux capture-pane` 最后一行）
            ├── 末行显示 `client_loop: send disconnect: Broken pipe` → SSH 断连，走 §8 恢复
            └── 末行正常但 CC 不响应 → /exit 退出 CC → 重新启动
```

**注意**：C-c 打断后，CC 的上一次工具调用可能已成功完成（如 MCP 返回了数据、Edit 已写入文件），只是输出被吞。**不要假设中断 = 失败**——先检查文件是否已有新内容再决定是否重发。

**反面案例**：本次 session 中 CC Germinating 3m37s，Hermes C-c 打断后发现 Edit 已成功写入 Batch 18（文件行数增加），但误判为卡住发了恢复指令，导致 CC 重新拉取已写入的批次。

## 10. Accept Edits 渐进式阻塞（2026-06-10 实战）

**关键发现：accept edits 阻塞不是全有全无，而是渐进加重的。** 完整记录了从「能用」到「完全死锁」的演变。

### 阻塞渐进演变

```
Phase 1: 正常可用（CC 刚启动 / 刚回复完一条短消息）
  → send-keys 正常送达，偶尔有 2-3s 延迟
  → 两拍法（'1' → sleep 0.5 → Enter）正常操作权限弹窗
  → paste-buffer 可能被截断但 send-keys 可靠

Phase 2: 间歇吞输入（CC 处理过多工具调用后）
  → send-keys 有时被吞（发送后不出现在输入框）
  → Enter 不一定触发 CC 拾取排队的消息
  → 需要额外按 Enter 或 C-c 才能唤醒

Phase 3: 完全阻塞（CC 在 accept edits 模式下执行含大量工具调用的回复后）
  → 所有按键被吞：Enter / BTab / Escape / C-c×3 / /exit 全部无效
  → 输入框无任何响应，pane 画面冻结
  → tmux send-keys 无法恢复，**必须本地终端操作或杀掉 CC**
```

### 触发条件

- **高频触发**：CC 在 accept edits 模式下执行含多次 bash/python/grep 工具调用的回复后（如噪音统计 3 次 bash 权限弹窗后进入 Phase 3）
- **低频触发**：短回复、无工具调用的对话通常不会触发
- **假设**：频繁的权限弹窗交互可能让 accept edits 的输入处理队列紊乱

### 恢复路径

```
Phase 1-2（间歇吞输入）：
  ① C-c 打断 → 重新发送指令
  ② Enter 再次触发（消息可能在输入框排队但未被拾取）
  ③ /compact 后重试

Phase 3（完全阻塞，tmux 侧无解）：
  ① C-c ×3 连发（⚠️ 本次验证失败，按键全部被吞）
  ② BTab / Escape / /exit（⚠️ 本次验证全部失败）
  ③ 全部失败 → **tmux 侧无法恢复**
     方案 A: 用户在 Windows 本地终端 attach tmux 后按 Escape / /exit
     方案 B: tmux kill-pane → 重建 pane + SSH → 重启 CC
     方案 C: SSH kill CC 进程
```

### 预防措施

- 减少在 accept edits 下的工具调用频率，或提前切换到 plan mode
- 长任务中途 C-c + 重新发送比等 CC 自然结束更安全
- 关键操作前可用 C-c + /exit 退出 CC → 不带 accept edits 重启

### 与 §9 的关系

accept edits 完全阻塞 ≠ Germinating 超长，但症状相似：
- Germinating 超长：区域①有 emoji+thinking文字（C-c 能打断）
- 完全阻塞：区域①无 emoji，CC 已回复完毕但输入死锁（C-c 打不断）

## 11. CC Session 名不匹配用户记忆（2026-06-11 实战）

**场景**：Hermes compaction 摘要记录了旧 session 名（如"微信群噪音分析"），但 CC 侧该 session 在后续工作中被 rename 成了新名字（如"微信群主题分类"）。用户凭记忆要求恢复旧名，实际任务内容在新名 session 中。

**判别**：`claude --resume` 列表中找不到用户指定的 session 名。

**处理**：
1. 不反复搜索不存在的名字
2. 按 **session size（最大）+ recency（最近活跃）** 排序，选择最可能的候选
3. resume 后通过 `capture-pane` 确认对话内容匹配目标任务（看文件路径、变量名、输出格式）
4. 若不匹配，Escape 退出 resume 重选下一个候选

**预防**：compaction 摘要中的 session 名可能过时，不要作为唯一恢复定位依据。

## 12. /exit CC 丢失当前批次进度（2026-06-11 实战）

**场景**：CC 正在批量循环任务中处理某批次（已读取数据但未完成 Edit），Hermes 发 `/exit`，当前批次进度丢失。

**规则**：CC 处于 thinking 状态（`✢`/`✻` emoji 标记）时，**不要发 `/exit`**。等当前批次完成（capture-pane 看到 Edit/Write 工具结果 + "第N批完成"输出）再中断。

**例外**：SSH 断连不可避免时，仅损失当前未完成批次，resume 后让 CC 从该批次重新开始。

## 13. Edit/Write 静默失败产生数据缺口（2026-06-10 实战）

**场景**：CC 在批量循环中执行 Edit 追加数据到文件，但部分 Edit 调用静默失败（返回 error 或被拒绝），导致文件中出现 offset 缺口（如缺少 offset=1650 的 Batch 25），而 CC 以为已全部写入。

**检测方法**：
1. CC 报告总批次 N 但文件行数不符
2. CC 自己发现"缺少 Batch X"
3. Hermes 检查文件：`grep -c "offset=" file.md` 与预期批次不匹配

**预防**：
- 在 TASK 指令中要求 CC "每批写入后用 Read 验证文件末尾是否包含本批数据"
- 循环结束后要求 CC 做一次完整性检查（数批次 vs 数行 vs 起止 offset）

**恢复**：
- 让 CC 重新拉取缺失的 offset 范围并补写
- 如果 CC 已 compaction 丢失了缺失记录，Hermes 可通过 `grep` 文件找到最大连续 offset，从断点开始补

**CC 自愈能力（2026-06-10 实战验证）**：

CC 在完成全量循环后（offset 返回 0 条），**自动检测并修复了缺失批次**：
1. CC 报告文件中有批次缺口（如缺少 Batch 25 offset=1650）
2. 自动用 MCP 重新拉取缺失 offset 的数据
3. 用 Edit 在正确位置插入补入的数据
4. 用 `grep -oP 'Batch \d+'` 检查所有批次编号连续性
5. 确认无更多缺口

这说明 CC 在 batch 循环任务中具备自检和自愈能力。**Hermes 不需要手动补漏**——只要在 TASK 指令末尾加一句「写完后检查批次连续性，补上缺失的批次」，CC 就能自行处理。但需注意：CC 的 grep 完整性检查可能触发 bash 权限弹窗，弹窗在 accept edits 模式下可能吞输入（见 pitfall #108），此时 Hermes 需远程执行检查替代。

## 14. Auto-compact 导致批量输出文件重复 + CC 搜索浪费（2026-06-11 实战）

**场景**：CC 在批量循环任务（逐批 Read→分析→Edit 追加→下一批）中触发 auto-compact。

**症状链**：
1. CC 正在处理第 N 批，auto-compact 触发
2. compact 后 CC 重写第 N 批（或上一批）→ 输出文件中出现**重复的批次条目**
3. 重复导致后续 Edit 的 search/replace 找不到唯一匹配 → `Error editing file`
4. CC 连续重试 Edit 失败（3-4 次）
5. CC 同时陷入"理解文件结构"的 Pontificating（搜索 `^## 第\d+批` 等），浪费 5-22+ 分钟

**根因**：compact 压缩了对话历史，CC 丢失了"已写入哪些批次"的精确记忆。恢复时 CC re-read 输出文件，但 compact 可能导致 CC 的 Edit 追加逻辑在错误位置执行（不是文件末尾），产生重复。

**预防（TASK 指令中）**：
```
- compact 后只需 Read 输出文件最后 20 行确认最后批次号即可，不要搜索整个文件
- 发现 Edit 失败时，跳过分析直接 Read 源文件下一批继续
- 每批写入后确认成功（Edit 返回无 error）
```

**恢复**：
```
CC Edit 连续失败 + Pontificating 超过 5min
  → C-c 打断
  → 发直接指令：
    "不要分析文件结构了，直接从第 N 批（行 X-Y）继续。
     读取源文件对应 100 行，逐条判断后追加写入输出文件。
     自动循环直到全部完成。"
  → CC 通常在第 3-4 次 Edit 重试后成功写入
```

**事后清理**：任务全部完成后，Hermes 从云端 SSH 读取输出文件，定位重复批次（搜索连续两个 `## 第N批`），删除 compact 产物（第一个），保留正确写入的（最后一个）。

**监控节奏调整**：compact 后 CC 的 Pontificating 阶段应视为"可能需要干预"窗口——如果 Pontificating 超过 5 分钟且 CC 输出中出现 "Let me understand the full file structure" 或搜索 `^## 第` 等模式，应 C-c 打断并直接指示 CC 跳过分析继续执行。

## 15. 批量任务完成后数据完整性验证（2026-06-11 实战）

**为什么需要**：CC 报告"全部完成"时，实际可能存在：(a) 缺失批次（CC 跳过了某些行范围）(b) 重复批次（compact 导致重写）(c) 行覆盖不完整。**CC 的完成报告不可信**——它可能只计数了批次标题数量，未验证连续性和唯一性。

**实测案例**：CC 声称 78 批全部完成（K511+E578=1089 条），实际第2批和第68批完全缺失（210 行未处理），第61/62/63 批严重重复（61 出现 3 次）。

### 验证方法（Hermes 从云端 SSH 执行）

当 CC 的输出文件有结构化批次标题（如 `## 第N批(行X-Y)`）时，用 Python 脚本验证：

```bash
# 1. SCP 验证脚本到 Windows
scp /tmp/verify_batches.py <ssh-alias>:"D:\\tmp\\verify_batches.py"

# 2. SSH 执行
ssh <ssh-alias> "python -u D:\\tmp\\verify_batches.py"
```

**验证脚本模板**（[`templates/batch-verify.py`](../templates/batch-verify.py)）：

```python
"""批量任务输出文件完整性验证。检查：批次连续性、唯一性、源行覆盖。"""
import glob, re
from collections import Counter

# 配置
OUTPUT_FILE = r'<windows-tmp>\*输出文件*.md'  # glob 模式
SOURCE_TOTAL_LINES = 7737               # 源文件总行数
EXPECTED_BATCH_RANGE = (1, 78)          # 预期批次范围

f = sorted(glob.glob(OUTPUT_FILE))[0]
lines = open(f, encoding='utf-8').readlines()

# 1. 批次连续性和唯一性
batch_count = Counter()
batch_ranges = {}
for l in lines:
    m = re.search(r'第(\d+)批', l)
    if m:
        n = int(m.group(1))
        batch_count[n] += 1
    m2 = re.match(r'## 第(\d+)批[（(]行(\d+)-(\d+)', l)
    if m2:
        n, s, e = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        batch_ranges[n] = (s, e)

all_expected = set(range(EXPECTED_BATCH_RANGE[0], EXPECTED_BATCH_RANGE[1]+1))
actual = set(batch_count.keys())
missing = sorted(all_expected - actual)
dupes = sorted([(k,v) for k,v in batch_count.items() if v > 1], key=lambda x:-x[1])

print(f"Total batch headers: {sum(batch_count.values())}")
print(f"Unique batches: {len(batch_count)}/{EXPECTED_BATCH_RANGE[1]-EXPECTED_BATCH_RANGE[0]+1}")
if missing:
    print(f"MISSING batches: {missing}")
if dupes:
    print(f"DUPLICATED batches: {dupes}")

# 2. 源行覆盖
covered = set()
for n, (s, e) in batch_ranges.items():
    covered.update(range(s, e+1))
uncovered = sorted(set(range(1, SOURCE_TOTAL_LINES+1)) - covered)
if uncovered:
    # Group into ranges
    ranges, start, end = [], uncovered[0], uncovered[0]
    for x in uncovered[1:]:
        if x == end + 1:
            end = x
        else:
            ranges.append((start, end))
            start = end = x
    ranges.append((start, end))
    print(f"UNCOVERED source lines: {len(uncovered)} total, ranges: {ranges}")

# 3. Keep/Exclude 条目计数
keep = sum(1 for l in lines if re.search(r'^\| K\d+ \|', l.strip()))
exclude = sum(1 for l in lines if re.search(r'^\| E\d+ \|', l.strip()))
print(f"Keep entries: {keep}, Exclude entries: {exclude}")
```

### 验证后处理

```
验证通过（无缺失/无重复）
  → 汇报用户完成

发现缺失批次
  → 让 CC 补做缺失的行范围（发精确的行号范围）

发现重复批次
  → 保留最后一个（正确写入），删除前面的（compact 产物）
  → 用 Python 脚本或手动 sed 定位删除

两者都有
  → 先补缺失，再清重复
```

### SSH PowerShell `$_` 变量 corruption 注意事项

通过 SSH 发送 PowerShell 命令时，`$_`（PowerShell 管道变量）会被 SSH 的 shell 解释为 `<cloud-home>`（本地工作目录）。这导致任何使用 `$_.Line`、`$_.Group` 等的 PowerShell 命令输出错误。

**变通方案**（按可靠性排序）：
1. **用 Python 代替 PowerShell**：`ssh <ssh-alias> "python -u -c \"...\""` — 最可靠
2. **SCP 脚本文件后执行**：先 `scp script.py <ssh-alias>:"D:\\tmp\\"` 再 `ssh <ssh-alias> "python D:\\tmp\\script.py"`
3. **用 `cmd /c` + findstr**：简单计数时可用，但不支持复杂逻辑

## 12. 长任务监控节奏优化（2026-06-10 实战）

CC 执行批量循环任务（如 50条/batch × 120 轮）时，Hermes 的 capture-pane 轮询间隔应根据 CC 当前状态动态调整：

| CC 状态 | 轮询间隔 | 理由 |
|---------|---------|------|
| 刚发送指令/恢复后 | 30-60s | 等待 CC 开始处理 |
| 稳定批量循环中（每批 MCP+Edit） | 120-180s | 每批约 1-2 分钟，太频繁浪费上下文 |
| compaction 后 | 60s | CC 可能恢复后走偏，需较快确认 |
| 怀疑卡住（Germinating/Simmering 超过 3min） | 30s × 3 次确认 | 需快速判断是否真的卡住 |
| 接近终点（预期剩余 <5 批） | 60s | 准备捕获完成信号 |
| SSH 断连恢复后 | 60s | 确认 CC 正常恢复 |

**节省上下文的关键**：稳定循环阶段用 120-180s 间隔，而非全程 15-30s。本次 session 监控约 2 小时，每 2 分钟一次轮询共约 60 次调用——如果全程 15 秒一次则是 480 次，差距巨大。

**卡住检测**：连续 3 次 capture-pane（间隔 15-30s）画面完全一致（特别是 Germinating/Simmering 时间戳冻结）→ 确认卡住。但卡住 ≠ 什么都没做——先检查文件是否已有新内容（见 §9 注意事项）。

## 16. Accept Edits 模式下 Bash 权限弹窗不响应（2026-06-17 实战）

**场景**：CC 在 accept edits 模式下执行 bash 命令（mv/rm/grep 等），触发权限确认弹窗：

```
Do you want to proceed?
> 1. Yes
  2. No

Esc to cancel · Tab to amend
```

**症状**：tmux send-keys 发送 `'1' Enter`、`Enter`、Tab+`'1'` 等均无效，弹窗界面不响应。连续尝试 3 次以上仍无法通过数字键选择。最终 Escape 取消弹窗后 CC 报告 "Interrupted · What should Claude do instead?"。

**与 §10 的关系**：这是 §10 accept edits 渐进式阻塞的特定子场景——不一定进展到 Phase 3 完全死锁，但 bash 弹窗的选择器单独失灵。即使 send-keys 短消息（非 paste-buffer）正常工作，弹窗选择器仍无响应。

**根因推测**：accept edits 模式下 CC 的 TUI 弹窗选择器与 tmux send-keys 的按键注入存在兼容问题——数字键可能被路由到输入框而非弹窗选项。

**绕过方案（按推荐度排序）**：

1. **SSH 直接执行**（最可靠）：
   ```bash
   # Windows 用 PowerShell（rm 不可用）
   ssh -p <ssh-port> <ssh-user>@host 'powershell -Command "Remove-Item -Force \"path1\",\"path2\""'
   # mv 操作
   ssh -p <ssh-port> <ssh-user>@host 'powershell -Command "Move-Item \"src\" \"dest\""'
   ```

2. **让 CC 用 Write 工具替代 mv/rm**：
   ```
   不要用 mv 命令。改用：先 Read 源文件获取内容，
   然后 Write 写入目标路径（相同文件名），
   最后用 Bash rm 删除原文件（或让 Hermes 远程删）。
   ```
   Write 工具不受弹窗影响（PreToolUse:Write hook error 不阻塞写入）。

3. **预授权规则**（长期方案）：
   在 CC 的 `settings.local.json` 中为常用命令添加 allow 规则。但注意协作协议规定仅预授权 git（见 session-lifecycle.md 预授权表），mv/rm/rm 预授权需谨慎。

**预防**：在 TASK 指令中明确告知 CC "避免使用 mv/rm 等 bash 命令移动文件，改用 Read→Write 方式"。

## 17. CC 写入路径不一致（2026-06-17 实战）

**场景**：CC 在项目中执行批量文件创建时，部分文件写入了错误的目录路径。例如，`法律WIKI\concepts\` 是正确路径，但 CC 将新文件写入了 `法律概念库\concepts\`（旧库路径）。

**根因**：CC 的 SKILL.md / CLAUDE.local.md 中配置的默认路径与项目实际使用的路径不一致。CC 参照自身配置而非项目现有文件的分布。

**检测**：Hermes 在 CC 汇报后，对写入路径做一致性检查——比对 CC 报告的写入路径与项目已知文件的分布。

**修复流程**：
1. 确认正确路径（检查已有文件分布）
2. 用 Read 获取错误路径下文件内容
3. 用 Write 写入正确路径（Write 不受 bash 弹窗影响）
4. 远程删除原文件（`ssh + powershell Remove-Item`，见 §16 绕过方案 1）

**预防（TASK 指令中）**：
- 明确写入路径："所有概念页写入 `法律WIKI\concepts\` 目录"
- 要求 CC 在写入前先确认目标目录中已有文件的命名模式

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
