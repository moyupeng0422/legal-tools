---
name: hermes-claude-collaboration
description: "MANDATORY first skill to load when Hermes needs to orchestrate Claude Code on local Windows via SSH+tmux. Covers session lifecycle, monitoring (capture-pane), R1/R2/R3 debate protocol, error recovery, and bulk file transfer. Trigger whenever: (1) user requests local file operations/code modifications/script runs/Git ops on Windows; (2) Hermes needs to monitor CC execution and handle popups/errors; (3) post-execution verification is required before replying to user. Do NOT use when CC is connected via Feishu bridge — use feishu-agent-collab skill instead."
version: 4.1.0
author: Custom
tags: [claude-code, ssh, tmux, orchestration, collaboration]
---

# Hermes × Claude Code 协作协议

> 📌 **环境特定值**（IP/路径/模型/SSH 配置）集中在 [references/environment-config.md](references/environment-config.md)。

## Overview

Hermes（云端 Ubuntu）通过两种方式与本地 Windows 上的 Claude Code 协作：

**方式 1（推荐·一次性任务）：Print Mode (`-p`)**
```
Hermes ──terminal("claude -p ...")──→ CC(Windows) ──→ 智谱 API
         ↑ stdout JSON 直接返回
```
无需 tmux，无截断，无弹窗。适合单次分析、代码审查、文档生成。

**方式 2（多轮交互）：tmux**
```
Hermes ──→ tmux claude-session ──SSH──→ CC(Windows)
              ↑ capture-pane 轮询
```
适合需要多轮辩论、用户可 attach 观察的交互式场景。

```
                    ┌─── 云端 Ubuntu ──────────────────────┐
                    │                                        │
用户 ←──→ Hermes ──→ tmux claude-session                    │
                    │    │                                   │
                    │    └── SSH ──→ Windows cmd ──→ CC     │
                    │                                        │
                    │    ←── capture-pane ── CC 输出 ←───── │
                    └────────────────────────────────────────┘
```

> **关键：tmux 在云端，不在 Windows。** Hermes 通过 `tmux send-keys` 向 session 内发送命令，SSH 连接在 tmux session 内部，CC 运行在 Windows cmd 中。

**核心原则：**

1. **不传话**：Hermes 不直接转发 CC 结论，必须独立核实后回传用户
2. **质疑优先**：CC 的技术方案、假设、执行结果都应经过校验
3. **可观测**：每个 send-keys 后必须轮询输出，不允许盲发
4. **可恢复**：任何异常都有明确恢复路径
5. **单 session 复用**：始终使用 `claude-session`，通过 `--resume` 切换对话
6. **按位置执行**：云端文件由 Hermes 直接修改；本地 Windows 文件由 CC 执行。讨论方案时双方参与，执行时各管各的

## When to Use

- 用户要求在本地机器上执行文件操作、代码修改、脚本运行、Git 操作等任务
- 需要监控 CC 执行进度并处理执行中的弹窗、提问、错误
- 需要 CC 执行后校验结果再回复用户

**不适用：** 纯文本对话（Hermes 直接回复）、云端操作（无需 SSH）、Claude Code CLI 参数查询（参考 bundled `claude-code` skill）。

> ⚠️ **仅适用于 tmux 直连的 CC。如果 CC 通过飞书 bridge 连接（回复是卡片/图片而非纯文本），请使用 `feishu-agent-collab` skill。**
> 反面案例（2026-06-22）：用户要求"严格按照协作skill"，Hermes 加载了本 tmux 技能而非飞书协作技能，被用户纠正「你们怎么在按照cc协作skill，不应该是飞书协作skill吗」。飞书 bridge CC 使用不同的通信协议（飞书消息+SSH conv 文件），不适用 tmux send-keys/capture-pane 机制。

## Print Mode（`-p`）— 推荐用于一次性任务

**这是最稳定的 Hermes-CC 协作方式，完全避开 tmux 的 send-keys 截断和 capture-pane 轮询问题。**

```bash
# 基础用法：结构化 JSON 输出
claude -p "分析这个专利的有效性" --output-format json --max-turns 10

# 精确权限控制（推荐）
claude -p "读取并分析合同" --allowedTools "Read" --max-turns 5

# 写文件
claude -p "修改维权方案" --allowedTools "Read,Edit,Write" --max-turns 15
```

**JSON 输出包含：** `session_id`、`result`、`total_cost_usd`、`num_turns`、`stop_reason`、`usage` —— 全部结构化，无需肉眼解析。

**权限控制三层：**
1. `--allowedTools` 白名单（推荐）— 精确到工具名和命令模式
2. `.claude/settings.local.json` 预授权 — 读操作自动放行，危险操作拦
3. `--dangerously-skip-permissions`（仅 GLM 后端）— 全局放行，谨慎使用

**GLM 后端特别注意：** print mode 在 Anthropic 原生后端跳过所有弹窗，但 GLM 后端可能仍弹出权限对话框。解决方案：`.claude/settings.local.json` 中 pre-authorize 读操作，或用 `--dangerously-skip-permissions`（已确认 GLM 后端可用）。参见 bundled `claude-code` skill §Non-Anthropic Backends。

**Print mode 局限：**
- 每次执行后退出，无持久会话（需 `--resume` 恢复）
- 不支持交互式审批流程（需预授权）
- 不适合需要多轮辩论的复杂任务（走 tmux）

**🔄 tmux vs Print Mode 选择决策树：**

```
需要 CC 执行操作？
├─ 否（纯讨论/分析） → Print Mode（-p）最安全，零截断风险
├─ 是 → 单次消息能完整描述任务？
│   ├─ 是 → Print Mode（-p）
│   └─ 否 → 需要 2+ 轮交互？
│       ├─ 是 → tmux
│       └─ 否 → 看是否涉及弹窗审批
│           ├─ 是（需预授权的写操作）→ Print Mode（-p）+ --allowedTools
│           └─ 是（需交互审批）→ tmux
│
需要多轮辩论（R1→R2→R3）？ → 必须 tmux（Print Mode 无法维持上下文）
需要用户可 attach 观察？ → 必须 tmux
CC 在 accept-edits/plan mode？ → tmux（但需注意短 send-keys）
```

> **默认倾向 Print Mode**：能用 `-p` 就不用 tmux。tmux 的 send-keys 截断、capture-pane 轮询、弹窗盲按是结构性缺陷，ACP 集成前只能缓解不能根除。只有 Print Mode 确实无法满足时才走 tmux。

## Body

### CC Pane 三个区域识别

capture-pane 看到的内容分三个独立区域：

```
区域① 输入框上方 → ✶ Cascading… / ✻ Churned for 40s / · Hyperspacing…
                   有 emoji = thinking，无 = 空闲。这是唯一空闲判断依据。

区域② 输入框     → > 提示符

区域③ 底部状态栏 → ⏸ plan mode on / ⏵⏵ accept edits on / 无标记=normal | X% until auto-compact
区域③包含两部分：左侧是 UI 模式（影响发送方式），右侧是 auto-compact 百分比（context 使用率）。空闲判断不看区域③，但监控中应关注 auto-compact 百分比——接近阈值（~90%）时 CC 即将自动压缩上下文，可提前预判。

### 🚨 CC 启动序列（v5 脚本化，2026-11-22）

**唯一方式：`~/.hermes/scripts/cc-start.sh "<任务名>"`**——一条命令完成六步（SSH连通→cd→启动claude→HERMES-ACTIVATE→/rename→task_map落库），每步逐项验证，任一步失败即停并输出现场。

- 任务名自动补 `Hermes:` 前缀；可带第二参数指定项目目录
- 已有活跃 CC session 时拒绝执行（防误重建），先 kill 再启动
- 终态输出 `START_OK: 任务名 | MODE_OK:xxx | 输入框干净`
- ⚠ 启动后默认 normal 模式：发讨论/TASK 前 `cc-mode.sh plan`，CC 执行操作前 `cc-mode.sh auto`

**旧六步法（手动 send-keys 逐条）已废弃**——历史违规源（漏 rename #48、C盘启动 #89、--resume 误用 #90）全部由脚本防呆。

**空闲判断铁律：只看区域①，不看区域③。** accept edits、plan mode、normal mode 都是 UI 模式，只要区域①无 emoji 标记就是空闲，可以发指令。区域③只决定发送方式（accept edits 用短 send-keys，不用 paste-buffer）。

### 前置强制检查（每次与 CC 交互前执行）

> **⚡ 检查 #-1 是所有后续检查的前提。不加载最新版 skill 就与 CC 交互 = 盲飞。**

| # | 检查项 | 命令/方法 |
|---|--------|----------|
| **-1** | **协作 skill 已加载（最新版本）** | `skill_view('hermes-claude-collaboration')` — 必须是涉及 CC 操作的**第一条工具调用**，在搜索记忆、查文件、确认上下文等任何准备工作之前。违反此条是协作质量下降的根源（#63 #0）。反面案例（2026-06-07、06-08、06-09）：连续三次先做准备工作再加载 skill，导致消息格式、辩论流程、启动序列全部违规 |
| 0 | 新会话激活序列完整（仅新会话/`/clear`后） | ① `<!-- HERMES-ACTIVATE -->` 已发且 CC 确认 ② `/rename` 已完成（带 `Hermes:` 前缀，#48）③ `claude_task_map.json` 已写入 ④ 输入框干净（capture-pane 确认 `> ` 后无残留文字）。**铁律：四步缺一不可发 TASK。** 反面案例（2026-06-03）：启动 CC 后直接发 TASK 漏掉 rename，用户指出"你还没rename" |
| 1 | tmux session 存活 | `tmux has-session -t claude-session` |
| 2 | CC 空闲（输入框上方无 emoji 标记） | **两步确认法**：① `capture-pane -S -20` 扫描最近 20 行，确认无 ✶/✽/✻/✢/· 等 thinking 动画 + 无 `●` 工具调用标记 + 无 `Would you like to proceed?` 等弹窗 ② 等待 3s 后再 `capture-pane -S -10` 二次确认快照无变化。**禁止单次 -S -5 即判空闲**——CC 在快速工具调用间隙，-S -5 抓到的 `>` 可能是瞬间快照，实际 busy |
| 3 | 状态摘要已附 | `[state: id=X step=M/N done=P ctx=摘要]` 存在 |
| 4 | 步骤 ≤ 3（步 = Hermes 指令数，非操作数） | 超过则拆分 |

### CC 协作模式激活

首次或重连时，发送激活标记让 CC 进入协作模式：

```bash
tmux send-keys -t claude-session '<!-- HERMES-ACTIVATE -->' Enter
```

CC 检测到 `<!-- HERMES-ACTIVATE -->` 或 `[HERMES:task-xxx]` 标记后，自动启用 `.claude/rules/hermes-collab.md` 中的协作规则（结构化格式、行为守则等）。无此标记时 CC 正常执行人类指令。

### 📌 硬性工具链（2026-11-21 起，强制使用，禁止裸 tmux send-keys 发消息）

> 背景：2026-11-21 确认「文本+Enter 同帧发送」会被 CC Ink 界面吞 Enter，消息永久卡框需用户手动回车（全天触发）。将正确操作固化为脚本，正确路径成为唯一路径。

| 工具 | 用途 | 替代的裸操作 |
|------|------|------------|
| `~/.hermes/scripts/cc-send.sh "消息"`<br>`cc-send.sh -f 文件` | 发送消息：文本→sleep→Enter→**自动校验输入框清空**→残留自动补键→SEND_OK/SEND_FAIL | 裸 `send-keys '文本' Enter`（必卡框） |
| `~/.hermes/scripts/cc-wait.sh -d 关键词 [-p] [-T 秒]` | 智能等待：关键词出现/CC空闲/弹窗/超时 四态即时返回，替代固定 sleep | 裸 `sleep N && capture-pane`（盲等） |

**标准流程**：`cc-send.sh "..." && cc-wait.sh -d "期望标记"`。发送返回 SEND_FAIL 或等待返回 WAIT_POPUP/WAIT_TIMEOUT 时按输出处理，不得忽略。

**技术要点（排查时参考）**：① CC 输入框裸提示符是 `>`+U+00A0 不换行空格，校验逻辑需字节级清洗（已内置于 cc-send.sh）② 忙碌判定 = emoji+省略号（如 `✽ Crystallizing…`），完成态无省略号（`✻ Baked for 5s`）③ `-f` 文件模式多行消息换行会被 tmux 折叠为一行（内容不丢）。

以下旧式 tmux 命令仅保留两类用途：shell 层命令（cd/启动/内部命令如 /rename 等单键场景可直接 send-keys，因无长文本粘贴问题）和 C-c/BTab 等控制键。**所有自然语言消息一律走 cc-send.sh**。

### 基础操作循环

每个与 CC 交互必须遵循：

```
1. 前置检查（4 项确认）
2. 任务命名 → 检查当前对话是否已命名；未命名则立即 `/rename 任务名` → 写入 `claude_task_map.json`（不等任务完成）
3. cc-send.sh 发送指令或任务（附状态摘要；脚本自动处理文本/Enter拆分+补键+清框校验）
4. 脚本返回 SEND_OK 即视为送达（内置清框校验，无需再肉眼验证截断）
5. cc-wait.sh -d "期望标记" → 等待 ACK/DONE 指纹，脚本自动识别空闲/弹窗/超时
6. 判断状态 → WAIT_DONE/WAIT_IDLE 继续 / WAIT_POPUP 处理弹窗 / WAIT_TIMEOUT 检查 CC 状态 → 事实校验
7. DONE 处理 → 检测 `<!-- DONE -->` 时提取 [TASK_MAP] 块 → 写入/更新 task_map 条目 → 执行 Verification Checklist → 汇报用户
8. COMPLETE → 发 `<!-- COMPLETE:task-X -->` 标记 task 结束
```

**状态摘要是强制的**：每条指令末尾必须附带 `[state: id=xxx step=M/N done=P next=xxx ctx=摘要]`，缺此行视为前置检查失败，不允许发送。

### 辩论豁免声明制（2026-11-22，硬约束——机制替代纪律）

**规则**：凡收到 CC 方案类输出（DONE 的 STATUS 中 `output_type: analysis`，协议 v1.1 新增字段），回复用户前必须**三选一**：

1. **发 [辩论]R2**——消息含 ≥1 个可证伪的具体质疑点，等 CC 回应后再汇报
2. **声明豁免**——回复用户时带 `（豁免原因: xxx）`，合法豁免仅三种：①纯事实查询（无方案成分）②用户已拍板（无讨论空间）③纯执行细节确认（无新主张）
3. **忽略（需理由）**——不推荐；忽略且不声明 = 传声筒违规

**依据链**：CC 输出 `output_type: analysis` → cc-wait.sh 检测 DONE 时输出 `⚠ DEBATE_REQUIRED` → Hermes 执行上述三选一。豁免声明写入审计日志（/tmp/debate_exempt.log），月度复盘豁免率——豁免率高说明提醒规则需修，而非 Hermes 不守纪律。

**依据**：#26 假辩论≠真辩论；用户 2026-11-22 指出 Hermes 反复传声筒，要求硬约束。正则判"方案类"不可靠（CC 否决），采用协议自声明（CC 是输出作者，自知事实）。

**done 语义（v2.1 明确定义）**：`done` = 本 task 中已收到 DONE 确认的最高 step 编号。只升不降。`done < step` 表示当前步正在执行或失败待处理（正常）；`done = step` 表示当前步已完成；`done > step` 异常。

**DONE 块解析**：CC 的 DONE 输出含 [TASK_MAP] 块时，Hermes 用正则 `\[TASK_MAP\](.*?)\[/TASK_MAP\]` 提取字段（task_id、step、done、session、timestamp），写入 `claude_task_map.json`。

**发送策略（2026-11-21 v4.1 修订）**：所有自然语言消息一律走 `cc-send.sh`（脚本自动拆分文本/Enter、自动补键、自动校验清框）。**TASK 消息必须单条整体发送**（`cc-send.sh -f 临时文件` 或单条直传）——分段连发会导致后续段落进入排队，CC 将 TASK 标记当独立消息处理，产生假阳性截断拒绝（47c）甚至漏执行要求项（2026-11-21 实测：task-5 三段连发，CC 只按第①段执行，②③要求漏掉）。长消息写临时文件走 `-f` 模式。paste-buffer 通道已废弃。单条指令步骤数 ≤3 的限制不变（CC 上下文限制，与发送工具无关）。

**ACK 指纹（v2.1 新增）**：CC 收到指令后回显 ACK：
```
<!-- ACK:task-X:step-3 -->
复述: <任务摘要>
校验: [task_id=task-X, step=3, total=5, done=2]
指令完整性: OK / SUSPECTED_TRUNCATION
[state: id=task-X step=3/5 done=2 ctx=摘要]
```
Hermes 比对 task_id + step 一致后才认为投递成功。30s 无 ACK 自动重发。CC 检测到以下信号标记 SUSPECTED_TRUNCATION：开标记无闭合、state 行 step 不一致、done > step、指令在句子中间突然结束。

**消息长度指纹（v3.8 新增）**：自然语言长消息（≥10 行，不含 TASK 标记）在**开头**加 `[msg:expect:N]`（N=预期行数）。CC 收到后计数实际行数，在 ACK 中回显。Hermes 比对：实际 < 预期 × 80% → 标记截断，重发。**注意：指纹必须在开头，不能放末尾（末尾本身会被截掉）。** TASK 格式消息继续用 4 个截断信号，不受此规则约束。

**PAUSE 标记（v2.1 新增）**：CC 遇到边界情况需要 Hermes 决策时，可发 `<!-- PAUSE:task-X:step-N -->`。PAUSE 后 CC 停止执行等指令，携带 reason + suggested。Hermes 四种响应：RETRY（重试当前步）、ABORT（终止 task，触发回滚讨论）、CONTINUE（按建议方向继续）、PAUSE-ACK（收到，稍后回复）。

**COMPLETE 标记（v2.1 新增）**：task 所有步骤执行完后，Hermes 发送 `<!-- COMPLETE:task-X -->`，CC 回复确认。双方都知道 task 结束，与"指令丢失/截断"可区分。

**回滚策略（v2.1 新增）**：ERROR/PAUSE 后 CC 不主动回滚。ERROR 中列出已修改文件清单（files_changed 字段），由 Hermes 决策是重试、跳过还是人工介入。文件追踪以 CC 自主记录为主（基于 Edit/Write 操作），不确定时标注 "files_changed": "uncertain"。

70. **Tailscale relay 下大文件传输：HTTP server 优于 SCP/SSH pipe（2026-06-04 新增）**：当云端和 Windows 通过 Tailscale DERP relay（非直连 P2P，延迟 ~350ms）通信时：
   - **SCP -P 2222** 传输 >2MB 文件 → 持续超时（60s+ timeout 无效）
   - **SSH pipe**（`cat file | ssh "powershell ..."`）→ 同样超时
   - **Python HTTP server + curl** → 成功（2.6MB 最终完成，耗时约 90s）

   推荐方案：云端启动临时 HTTP 服务器（`python3 -m http.server 18888 --bind 0.0.0.0`），CC 用 `curl -s http://<cloud-tailscale-ip>:18888/file.tar.gz -o C:\Users\<windows-username>\file.tar.gz` 下载。HTTP 协议在低带宽高延迟链路上比 SCP 更健壮。

   详见 `references/bulk-file-transfer.md` 方向二。

### 快速参考卡

| 操作 | 命令 |
|------|------|
| **启动会话（唯一方式）** | `~/.hermes/scripts/cc-start.sh "<任务名>"`（六步脚本化+逐项验证，2026-11-22） |
| **发送消息（唯一方式）** | `~/.hermes/scripts/cc-send.sh "消息"` 或 `-f 文件`（自动拆分文本/Enter+补键+校验） |
| **智能等待（唯一方式）** | `~/.hermes/scripts/cc-wait.sh -d "标记"` / `-p`（弹窗） / `-q`（队列自愈） / `-T 秒`（超时）。v2：`-d` 自动排除用户输入回显行（只认 CC 输出）；CC 意译回复不含字面标记时正确超时而非假阳性——**`-d` 只用于协议约定 CC 原样输出的标记（ACK/DONE/PAUSE）**，自然语言确认用 WAIT_IDLE |
| **模式切换（唯一方式）** | `~/.hermes/scripts/cc-mode.sh plan\|auto\|normal\|status`——讨论/发TASK前=plan，执行操作前=auto（2026-11-22 定稿，详见 references/cc-mode-approve-scripts.md） |
| **权限弹窗处理（唯一方式）** | `~/.hermes/scripts/cc-approve.sh dump`（读分类）→ `cc-approve.sh <N>`（批准）——Hermes 只决策选号，机械操作全脚本承载；黑名单弹窗只能用户亲手 touch ~/.hermes/HUMAN_OK 放行 |
| **Print mode（一次性任务）** | `claude -p "task" --output-format json --allowedTools "Read,Edit" --max-turns 10` |
| 检查 session | `tmux has-session -t claude-session` |
| 创建 session | `tmux new-session -d -s claude-session -x 200 -y 60` |
| 启动 CC（shell层，可裸send-keys） | `tmux send-keys -t claude-session 'cd /d "D:\\项目"' Enter; sleep 2; tmux send-keys -t claude-session 'claude' Enter` |
| 激活协作 | `cc-send.sh '<!-- HERMES-ACTIVATE -->'` |
| 监控状态 | `tmux capture-pane -t claude-session -p -S -20` |
| 快速检查 | `tmux capture-pane -t claude-session -p -S -5` |
| 接受权限（两拍法+验证） | `tmux send-keys -t claude-session '数字'; sleep 0.5; tmux capture-pane 验证>位置; tmux send-keys Enter` |
| 中断操作 | `tmux send-keys -t claude-session C-c`（控制键可直接send-keys） |
| 命名对话 | `cc-send.sh '/rename 任务名'` |
| 切换对话（CC内部） | `cc-send.sh '/resume 任务名'` |
| 压缩上下文 | `cc-send.sh '/compact focus on 主题'` |
| 退出 CC | `cc-send.sh '/exit'` |
| 切换模式 | `tmux send-keys -t claude-session BTab`（控制键） |
| PAUSE 响应 | `cc-send.sh 'RETRY/ABORT/CONTINUE/PAUSE-ACK'` |
| Task 完成 | `cc-send.sh '<!-- COMPLETE:task-X -->'` |

> **已废弃（2026-11-21）**：`load-buffer`+`paste-buffer` 长消息通道（截断风险高，被 cc-send.sh -f 取代）；「分段短 send-keys 逐条发送」（被 -f 文件模式取代）；裸 `send-keys '文本' Enter`（同帧吞 Enter，必卡框）。

> **模型说明**：CC 模型 2026-08-27 起 glm-5.2 → 用户可随时用 `/model` 切换（2026-11-21 已切 glm-5.3-flash[1M]）。启动命令用 `claude`（不带模型参数）即沿用用户默认配置；需要指定时用 CC 内部 `/model` 命令切换，勿写死在启动参数。

**Hermes 直接执行（在云端本机，无需 SSH）：** 上表所有 `tmux` 命令直接运行即可。

**从外部机器远程执行（供参考）：**

```bash
ssh -p {port} {user}@{host} "tmux send-keys -t claude-session 'claude' Enter"
ssh -p {port} {user}@{host} "tmux capture-pane -t claude-session -p -S -30"
ssh -p {port} {user}@{host} "tmux load-buffer -t claude-session /dev/stdin" <<'EOF'
长消息内容
EOF
ssh -p {port} {user}@{host} "tmux paste-buffer -t claude-session -d"
```

> 详见 references/active-discussion-protocol.md —— 活跃讨论中的每轮协议纪律，补充任务边界协议未覆盖的轮次交互规范。

## Reference 索引

> **架构终审（2026-11-22）**：hooks 方案全否决（SessionStart=伪需求：session_id 无消费场景；Stop=帧文本提取够用），CC 协作统一走脚本：start/send/wait/mode/approve 五件套 + wm CLI + output_type 协议字段。辩论硬约束=协议自声明+豁免声明制（非 hook，全协作场景统一）。决策详见 references/cc-mode-approve-scripts.md。

| Reference | 内容 | 加载时机 |
|-----------|------|---------|
| [session-lifecycle](references/session-lifecycle.md) | Session 创建/销毁、弹窗处理、任务切换、paste-buffer、发送前状态检查、预授权配置 | 首次启动 CC、处理弹窗、切换任务、发送消息前 |
| [monitoring-debate](references/monitoring-debate.md) | 监控链路、状态判定、R1/R2/R3 辩论协议（含风险分级、R2子轮、查证分工、Token规则）、写作协作流程、事实校验 | 监控 CC 执行、校验 CC 输出、裁决争议、方案讨论 |
| [monitoring-mode](references/monitoring-mode.md) | **长时蹲守监控模式**——轮询策略、自言自语格式（💭/⚠️/📋）、用户信号识别、token 预算管理、分段汇报、常见场景处理 | 用户要求持续监控 CC 对话、观察执行过程、根据输出插入检索/分析任务时 |
| [doc-review-skill-design](references/doc-review-skill-design.md) | 文件审核 Skill 设计共识（2026-06-17）——Phase 1/2 范围、架构决策、公开参考项目、检查项清单 | 构建 CC 本地法律文书审核 Skill 时 |

| [error-recovery](references/error-recovery.md) | 崩溃/权限误拒/API 限流/工具失败/SSH 断连/上下文耗尽/**长任务 SSH 反复断连恢复(§8)**/**Germinating 超时卡住(§9)**/**Edit 静默失败(§10)**/**CC 自愈批次缺口(§10)**/**长任务监控节奏(§11)**/**批量任务完成后数据完整性验证(§15)** | CC 执行异常、连接中断、长任务中断恢复、批量循环监控、**完成后的数据验证** |
| [ssh-reconnect-playbook](references/ssh-reconnect-playbook.md) | SSH 断连恢复实战——症状识别、恢复流程、常见错误 | capture-pane 显示旧内容但 SSH 已断时 |
| [ssh-diagnostics](references/ssh-diagnostics.md) | SSH 连通性诊断决策树（refused vs timeout、Tailscale 状态、防火墙、sshd） | SSH 连接不通时 |
| [cc-context-file](references/cc-context-file.md) | CC 侧 `.claude/rules/hermes-collab.md` 完整草案——部署后 CC 自动加载协作协议（含 ACK/DONE 强制包裹要求） | 首次部署或修改 context 文件时 |
| [cc-hook-data-schemas](references/cc-hook-data-schemas.md) | CC Hook 各类型 stdin 数据结构（PreToolUse/PostToolUse/Stop/Notification）、已知限制（Stop hook 不含回复文本 #136）、IM 同步方案 hook 评估 | 构建 CC hook 驱动方案（如 IM 同步、通知推送）时 |
| [v3-protocol-test-results](references/v3-protocol-test-results.md) | 2026-06-01 压力测试结果——通过/缺口/方法验证 | 检修协议或诊断协作异常时 |
| [self-audit-protocol](references/self-audit-protocol.md) | Hermes 自查 CC 协作合规性的标准化流程——触发条件、审计维度、输出格式、修复行动 | 每轮密集协作后、用户要求自查、怀疑协作质量下降时 |
| [self-audit-findings](references/self-audit-findings.md) | 2026-06-01 协作纪律自查——task_map漏记、状态摘要缺失、并发测试两难 | 自查/审计/新 session 回顾纪律漏洞时 |
| [acp-research](references/acp-research.md) | ACP 替代 tmux 方案研究——headless mode 分析、claude-agent-acp 轮子、部署前提、协议细节、架构设计、E2E 验证 | 讨论 CC 协作底层架构改进时 |
| [acp-implementation](references/acp-implementation.md) | ACP P1-P3 实施阶段所有修正细节（5个错误 + 根因）、路由策略、编排模板、集成测试结果 | ACP 集成代码审查、排错、新开发时 |
| [rmfyalk-session-architecture](references/rmfyalk-session-architecture.md) | 人民法院案例库 rmfyalk 的两层有效期机制——JWT token（~4h）vs ASP.NET Session（~20min 超时），浏览器保活方案 | CC 管理浏览器登录态、法律数据源 session 保持、token 自动刷新架构 |
| [cdp-browser-approach](references/cdp-browser-approach.md) | SSH 无法弹窗时的 CDP 替代方案——用户在桌面启动 Edge + 调试端口，CC 通过 CDP 连接操控 | CC 需要通过浏览器交互但 SSH headed 模式无窗口时 |
| [cdp-handoff-template](references/cdp-handoff-template.md) | CDP 保活交接模板——SSH CC 验证完成后如何交付给本地桌面 CC 长期接管 | 将已验证的 CDP 保活从 SSH CC 交接给本地 CC 时 |
| [edge-troubleshooting](references/edge-troubleshooting.md) | Edge + Playwright 排错——exitCode=21 的三类根因（中文路径/锁文件残留/进程残留）及修复步骤 | Edge 启动失败、Playwright launch_persistent_context 报错 |
| [bulk-file-transfer](references/bulk-file-transfer.md) | 从 Windows 到云端的批量文件传输方案——tar-over-SSH pipe vs SCP 对比、避坑指南、完整性验证 | 需要将 CC 本地整个 skill 项目目录复制到云端时 |
| [legal-article-collab-lessons](references/legal-article-collab-lessons.md) | 法律助手×CC协作起草微信公众号文章实战——辩论流程纠正、CC修正边界、条款编号双重核对、MCP弹窗监控 | 与CC协作法律类写作时 |
| [http-file-transfer](references/http-file-transfer.md) | 从云端到 Windows 的文件传输——SCP 在 Tailscale relay 下超时时的 HTTP 服务器兜底方案 | SCP/rsync 超时但 SSH 连通时 |
| [cc-mcp-skill-dev-pattern](references/cc-mcp-skill-dev-pattern.md) | CC 开发依赖 MCP Server 的 Skill 的完整模式——mcp.json + settings.json 双文件配置、依赖安装、连通验证、MCP vs CLI 架构选择 | CC 构建需要外部 MCP 服务的 Skill 时 |
| [cc-project-migration](references/cc-project-migration.md) | CC CLAUDE.local.md 项目迁移工作流——4 步循环、compact 后 total_lines 修复、子目录 junction 路径规范、受控字段确认策略、6 档分档方法论、无 frontmatter 项目处理、API 密集型 has_overflow 决策 | CC 将老项目迁移到新 schema 格式、批量迁移旧 CLAUDE.local.md 文件、分档规划迁移优先级时 |
| [cc-project-archival](references/cc-project-archival.md) | CC 项目归档工作流——5 步流程、连带 agent 审查、双版本目录归属验证、无 junction 简化、domain enum 保留规则、残留 grep 验证 | 归档已停用/被替代的项目、迁移前的僵尸清理、生态级归档（含依赖 agent）时 |
| [github-deployment](references/github-deployment.md) | CC 从 Windows 端推送 GitHub 的阻塞点与工作流——凭证检查、无 gh CLI 时的应对、推荐推流 | CC 需要创建 GitHub 仓库或 git push 时 |
|-----------|------|---------|
| [batch-classification-hybrid](references/batch-classification-hybrid.md) | 大规模数据分类的"规则引擎+AI审核"混合模式——Python规则引擎批量分类+CC逐条审核不确定案例+JSON checkpoint续接+数据完整性验证 | CC 需要对数千条数据做分类/筛选/噪音分析时（微信群记录、日志、评论等） |
| [acp_bootstrap.py](templates/acp_bootstrap.py) | ACP 快速引导脚本模板——直接复制运行，验证 SSH→ACP 全链路 | 首次部署或诊断 ACP 连通性时 |

## Research Workflow (v3.3, updated v3.32)

当用户要求 Hermes 调研和评估外部项目/技能/工具时：

### Standard flow

```
1. Hermes 定义范围 → 组装任务发给 CC
2. CC 在本地（Windows）克隆仓库 / 安装技能
3. CC 阅读 SKILL.md + 目录结构
4. CC 输出分析表（按项目：用途、依赖、存储、兼容性）
5. Hermes 补充 CC 遗漏的网络搜索结果
6. CC 整合新信息 → 完善分析
7. Hermes ↔ CC 讨论：裁剪/保留/集成决策
8. CC 输出最终方案文档（markdown）
9. Hermes 呈交用户审批
```

### Pre-research workflow（CC Web Search 不可用时）

当 CC 的 Web Search 被限流或返回 0 结果（plan mode 下常见）时，改用此模式：

```
1. Hermes 自行完成所有网络搜索（web_search + web_extract）
2. Hermes 将搜索结果整理为结构化文件（write_file）
3. Hermes 通过 SCP 传输文件到 Windows（scp → C:/Users/<windows-username>/<file>.txt）
4. Hermes 发送短指令："读取 C:\Users\<windows-username>\\<file>.txt 并按其中任务要求执行。不要使用Web搜索。"
5. CC 读取文件，分析预提供的内容，输出结论
6. Hermes 独立审核 CC 输出 → 必要时发回质疑进行 R2 辩论
```

**优势**：完全绕过 CC 不稳定的 Web Search；CC 专注分析而非搜索；SCP 避开了 plan mode 下 send-keys 截断问题（见 Pitfall #68）。

**反面案例（2026-06-04）**：律所平台模板分析任务，CC 的 Web Search 连续返回 0 结果并进入重试循环（4次 × 0 searches），浪费 ~8 分钟 token。Hermes Escape 中断后改为预研究模式——自己搜索 5 个飞书官方模板 → 编译分析文件 → SCP → CC 在 30s 内完成分析。

**Key rules for both workflows:**
- CC does ALL local operations (git clone, npx install, file reads). Hermes NEVER clones to cloud.
- Hermes does ALL web searches (CC's Web Search tool is unreliable — frequently returns 0 results).
- ClawHub skills install via `npx clawhub@latest install <slug>`, NOT git clone.
- After CC clones, Hermes sends additional info via SCP file or `[HERMES:INFO]` markers.
- Discussion uses `[HERMES:DISCUSS]` for Hermes's proposed positions, CC debates back.
- Final output is a plan document on CC's local disk; Hermes reads it via capture-pane.

## v2.1 协议升级（2026-06-02 辩论产出）

> 来源：Hermes × CC R1→R2 辩论（tmux 优化方案讨论）。10 项变更，全部共识。

| # | 变更 | 优先级 | 类型 |
|---|------|--------|------|
| 1 | ACK 回显指纹，截断判断由 Hermes 做 | P0 | 协议 |
| 2 | 短链路 ≤3 步（步=Hermes 指令数，非操作数） | P0 | 协议 |
| 3 | 截断检测信号列表（4 类） | P0 | 协议 |
| 4 | 超时重发 30s | P1 | Hermes 侧 |
| 5 | 预授权仅 `Bash(git *):allow`，其余保留弹窗 | P1 | 配置 |
| 6 | 新增 PAUSE 标记 + 4 种响应方式 | P1 | 协议 |
| 7 | 新增 COMPLETE 标记 | P1 | 协议 |
| 8 | done 语义：已确认完成的最高 step 编号，只升不降 | P1 | 协议 |
| 9 | ERROR/PAUSE 文件变更追踪约定 | P1 | 协议 |
| 10 | 回滚策略：CC 不主动回滚，列文件清单 | P1 | 协议 |

**CC 侧 8 个 Hermes 痛点（需持续改善）：**

| # | 痛点 | 本质 |
|---|------|------|
| 1 | 隐性上下文依赖 | Hermes 指令引用 CC 看不到的信息 |
| 2 | 无 PAUSE/ESCALATE 通道 | 已修复（新增 PAUSE 标记） |
| 3 | 不说"为什么" | 只给操作不给理由，限制 CC 主动性 |
| 4 | 微观管理 vs 模糊的摇摆 | 有时精确到行号，有时只说"优化一下" |
| 5 | 输出格式过度依赖 | DONE 必须精确格式，束缚 CC 表达自由 |
| 6 | 无回滚协议 | 已修复（ERROR 列文件清单 + Hermes 决策） |
| 7 | done 字段语义模糊 | 已修复（明确定义） |
| 8 | 无 task 完成信号 | 已修复（新增 COMPLETE 标记） |

**Hermes 侧纪律加强（本次讨论重点）：**
- **空闲判断**：只看输入框上方 emoji 标记（区域①），不看 UI 模式（区域③）
- **弹窗监控**：短频快速轮询，发现停止信号立即跳出，不拖延
- **消息确认**：ACK 指纹比对，30s 无 ACK 自动重发
- **发送方式**：accept edits/plan mode 用短 send-keys，不用 paste-buffer
- **CC 自动推荐识别**：`>` 开头的推荐内容不是用户输入，是 CC 自动生成的

## Common Pitfalls

0. **加载 skill 后未遵守其规则（2026-06-03 新增）**：加载了协作 skill 但继续用默认沟通方式与 CC 交互——不发状态摘要、不做两步空闲确认、消息内容不按协议格式。用户指出「你现在跟cc的对话都没有依照cc协作skill，我看到好多对话都不完整」。根因：skill_view 读取了协议内容但未在后续工具调用中严格遵守。**强制约束**：加载协作 skill 后发送第一条消息前，必须通过 checklist 确认：状态摘要 [state:...] 有吗？两步确认（-S -20 → 3s → -S -10）做了吗？单条消息 ≤300 字符吗（plan mode）？三条缺一不可。
1. **把 Hermes 专属偏好强加给 CC（2026-06-24 新增）**：用户对 Hermes 的偏好（如「全部做完再汇报」「无需我介入」）仅约束 Hermes 自身，不得作为指令传达给 CC/芭迪/传令员。CC 有自己的交互模式（弹窗确认、plan 阶段询问用户），Hermes 不应干预。反面案例：Hermes 发送「请全程执行不中断，5个阶段全部完成后统一汇报，不要中间停顿问我」给 CC——这是越权操作。

1. **CC Web Search 不可用 + 重试循环** — CC 的网络搜索经常返回 0 结果（`Did 0 searches in Xs`）。更糟的是，CC 可能进入**重试循环**，重复执行相同失败的查询 4-6 次。**Hermes 必须 (a)** 自行完成所有网络搜索，**(b)** 在检测到重试循环时中断 CC（Escape），然后通过 SCP 文件提供预研究内容（`scp task.txt → CC 读取文件`）。永远不要依赖 CC 自行搜索。SCP 预研究模式详见 Research Workflow §Pre-research workflow。
2. **禁止 `--dangerously-skip-permissions`**：使用正常模式 + `settings.local.json` 预授权安全操作
5. **恢复用 `--resume <Hermes任务名>`，禁止 `--continue`（2026-06-06 修正）**：CC 的 session 存储在 Windows 本地 `~/.claude/`，`--continue` 会恢复最近 session（即用户本地正在使用的对话），导致 Hermes 看到并干扰用户的实时对话。Hermes 必须始终：(a) 新任务用 `claude` 启动全新 session，然后 `/rename Hermes:<任务名>`（带前缀避免与用户 session 冲突）；(b) 恢复旧任务用 `claude --resume Hermes:<任务名>` 精确指定。**绝对禁止 `--continue` 和无参数 `--resume`。**
6. **弹窗盲按风险**：权限弹窗不要一律 `y`，需审查操作内容；Trust 弹窗可以盲按 Enter
7. **监控超时 ≠ CC 完成**：连续 3 次相同输出可能是 CC 卡住而非完成，需判断 pane 状态
9. **accept edits 阻塞**：capture-pane 看到 `⏵⏵ accept edits on` 时，paste-buffer 发送的长消息可能只收到最后一行（CC 只解析了最后一段文本）。处理优先级：
   1. `BTab`（Shift+Tab）→ 切换到 `⏸ plan mode on`，此模式下短 send-keys 正常工作。
   2. `Escape` → `Enter` → 尝试退出 accept edits 回到正常模式
   3. **scp 文件绕过**：将长内容 scp 到 Windows（如 `/Users/<windows-username>/msg.txt`），用短 send-keys 让 CC `读取 C:\Users\<windows-username>\msg.txt`。绕过 paste-buffer 截断问题
   4. **最后手段**：`/exit` → 重新 `claude` 启动 → 再 paste-buffer。短 send-keys 不受 accept edits 影响，可用来发退出指令
10. **传话陷阱**：与 CC 协作时，Hermes 必须用自己的判断逐条分析 CC 输出（同意/反驳/修正），给出独立结论。按主题归纳 CC 建议后转述仍被视为传话——用户期望独立思考后再汇报，而非切换格式转发。收到 CC 方案后第一反应必须是「这个方案有没有问题？」而非「CC 说了 X，你怎么看？」。详见 monitoring-debate.md §3.1。
12. **CC 弹窗导航不可靠（数字键 ≠ 总有效，2026-06-25 修正）**：CC 的权限弹窗和 interview 表单导航并不可靠——按数字键后 `>` 光标**不一定移动到对应选项**。实测多次出现按 `2` + Enter 但 `>` 仍停在 option 1（弹窗未通过）。**正确流程**：① 按数字键或 Tab/Down 导航 ② **立即 capture-pane 验证 `>` 位置**（`>` 必须出现在目标选项行首）③ 确认移动后才按 Enter。若 `>` 未移动：补发 Down 直到 `>` 到位 → 再 Enter。**两拍法仍有效**（数字/Down 与 Enter 分开发送，间隔 ≥ 300ms），但增加了第②步验证。未生效时切勿重复按数字键+Enter（会重复排队），应 Ctrl+C 取消 → 等空闲 → 重发。
13. **Plan mode 下 paste-buffer 不可靠**：plan mode（`⏸ plan mode on`）和 accept-edits 模式一样，paste-buffer 可能只收到消息开头几个字（多次会话实测：~600 字消息只收到片段）。**可靠替代：分段短 send-keys**，每条 <300 字符，间隔 1-2s，总共不超过 10 条。长内容写云端文件 → scp 到 Windows → 让 CC `读取 <文件路径>`。最可靠方案：多段短 send-keys 逐条发送。
150. **CC plan mode 声称「Updated plan」但实际未修改目标内容（2026-06-28 新增）**：CC 声称更新了 plan 文件但实际遗漏了部分位置。**必须 SSH 直接读 plan 文件验证关键段落是否确实更新**。发现遗漏后用编号列表逐条指定修改内容，或通过确认面板 option 4 发送详细指令。详见 pitfalls.md #150。
15. **过度规划**：单次 paste-buffer 指令不应超过 **3 个步骤**（步 = Hermes 指令数，非操作数）。CC 上下文窗口在处理长指令时可能丢失中间步骤细节，导致执行偏差。超过 3 步的任务必须拆分发送，每步完成后确认再发下一步。
16. **沉默执行**：CC 执行中发现异常（工具失败、文件不存在）并输出了错误信息，但 Hermes 的 capture-pane 未及时捕获到响应，误判任务完成。轮询间隔不得超过 **30 秒**，CC 超过 **60 秒**无输出必须触发超时检查。
18. **task_map 漏记**：每次 `/rename` 后必须**立即**更新 `claude_task_map.json`，不要等任务完成后再补——到那时上下文已被压缩，记录必然丢失。本 skill 自身在 v3.0 测试中连续漏记 5+ 条任务，是反面教材。
20. **发送确认机制**：每次 paste-buffer 或 send-keys 后，必须确认消息完整送达。A) capture-pane -S -10 肉眼检查内容完整；B) 等待 CC 的 ACK 指纹回执（task_id + step 比对），30s 超时重发。仅依赖 paste-buffer 返回值（永远返回成功）是假象——内容可能截断但无法检测。

20a. **send-keys 文本与 Enter 必须拆分为两次调用，中间隔 ≥1.5s 并验证（2026-11-21 修订，推翻旧的同一调用铁律）**：`tmux send-keys -t claude-session '文本' Enter` 同帧发送时，CC 的 Ink 界面把整段文本+Enter 当一次粘贴处理，**Enter 被吞掉**——消息卡在输入框，CC 永远收不到，需用户手动回车。2026-11-21 全天协作均触发此问题（用户发出每条消息都靠手动回车），实测拆分后 100% 送达。

   **正确做法**（单工具调用内用 shell 顺序执行，既防中断又防吞键）：
   ```bash
   tmux send-keys -t claude-session '文本内容'; sleep 1.5; tmux send-keys -t claude-session Enter; sleep 3; tmux capture-pane -t claude-session -p -S -5
   ```

   **旧铁律为何被推翻**：旧规则（文本+Enter 同一调用）的动机是防止 Hermes turn 被打断后 Enter 不再发送。但实测证明同帧发送 Enter 本身就不可靠（Ink 粘贴处理吞键）。「配对」防了一种风险却引入了更高频的必现故障。上面的单调用串联写法兼顾两者。

   **检测方法**：capture-pane 看到输入框 `>` 后有刚发送的文本残留且 CC 空闲 → Enter 被吞 → 补发 `send-keys Enter`（可连补多次，空框按 Enter 无害，用户已授权）。
26. **假辩论 ≠ 真辩论**：收到 CC 方案后写一段独立评价再汇报用户，这不构成辩论。辩论必须是双向的——把质疑发回 CC，让 CC 回应，你再评估回应，R1→R2→R3 的轮次才算辩论。独立分析是辩论的**起点**，不是终点。独立分析后应：① 列出具体质疑 → ② 发回 CC 做 R2 质询 → ③ CC 回应后评估修正 → ④ 可能再追问 R2b/R2c → ⑤ 最终结论汇报用户。缺了 ②~④ 就是假辩论。**2026-06-02 两次触发：** 路由边界讨论和 tmux 优化讨论，均修正了 CC 的错误假设。核心教训：独立分析后若未发回 CC 质询就直接汇报用户，不管分析多深入，都是传声筒。

47. **CC 启动目录选择——分析/调研任务不应直接 cd 到目标项目目录（2026-07-05 新增）**：当任务是让 CC 分析或调研某个项目/插件/仓库时，**不要**在启动 CC 前先 `cd /d "D:\目标项目目录"`。CC 在目标目录下启动会：(a) context 被 CLAUDE.local.md 或项目约定污染；(b) CC 可能误以为需要在该项目中执行修改操作。**正确做法**：在通用目录（如 `C:\Users\<windows-username>` 或工作区根目录）启动 CC，在指令中通过路径指定 CC 读取目标项目（如「读取 D:\<projects-root>\obsidian-table-data-reader 的代码并分析」）。项目操作类任务（如开发/修改）仍按 Step 2 正常 cd 到项目目录。反面案例（2026-07-05）：分析 obsidian-table-data-reader 插件时直接 cd 到插件目录启动 CC，被用户纠正「你进错目录了，不要直接进入到插件项目目录」。
47b. **`<!-- HERMES:DISCUSS -->` 不是 tmux 协议合法标记（2026-07-05 新增）**：CC 的 tmux 协议合法标记为 `TASK / ACK / DONE / ERROR / PAUSE / DISPUTE:R1|R2|R3 / COMPLETE / RESUME / SKIP / ABORT`。`<!-- HERMES:DISCUSS -->` 是飞书群协议概念，tmux 模式下 CC 会拒绝执行并提示截断信号。发起辩论/讨论的正确格式：`[辩论R2] 质疑内容` 或 `<!-- DISPUTE:R1 -->`。注意：CC 对非 XML 标记格式的中文讨论前缀（如 `[辩论R2]`）容忍度较高，能正确理解意图并响应。

47c. **分段 send-keys 发送 TASK 消息会产生假阳性截断拒绝（2026-07-05 新增）**
47c. **分段 send-keys 发送 TASK 消息会产生假阳性截断拒绝（2026-07-05 新增）**：当 TASK 标记和任务内容通过多条 `send-keys + Enter` 分别发送时（accept edits 模式下的标准做法），CC 的协议解析器会先将第一行（TASK 标记）视为独立消息，触发截断检测（"开标记无后续内容"），输出拒绝回复。但 CC 随后会处理输入队列中的后续内容，正常执行任务。**影响**：浪费 CC token 产生不必要的拒绝分析，但不造成数据丢失或任务失败。**缓解**：可接受此代价（分段发送避免截断的价值远大于假阳性的 token 浪费），无需改变发送策略。若想避免，可将 TASK 标记和第一行内容合并为一条 send-keys（`<!-- TASK:task-1:step-1 --> 请分析...` 在同一行）。

47d. **误判 CC 完成状态——"thinking more" 不等于已回复（2026-07-05 新增）**：capture-pane 看到 CC 的 emoji 状态行带有 `thinking more` 后缀（如 `✽ Moseying… (36s · ↓ 2.8k tokens · thinking more)` 或 `✢ Discombobulating… (1m 1s · thinking more)`）时，CC **仍在处理中，未完成回复**。Hermes 不得将此时 CC 的部分输出视为"已回复"并据此汇报用户。**完成信号**：emoji 行变为无 "thinking" 后缀的完成状态（如 `✻ Worked for 2m 18s`），且输出末尾有空 `>` 提示符、内容不再变化。**判别规则**：`thinking more` = 仍在思考；`Cooked for Xs` / `Worked for Xs` / `Brewed for Xs` = 已完成。反面案例（2026-07-05）：Hermes 看到 `· Moseying… (36s · thinking more)` 后直接汇报用户"CC已回复"，用户纠正「cc还在思考啊，没回复啊，你怎么会认为cc已回复」。

47e. **CC `Skill()` 无法加载自定义 skill——需直接读文件路径（2026-07-06 新增）**：CC 的 `Skill('cc-obsidian-pm')` 等自定义 skill 调用会返回 `Unknown skill`。这些自定义 skill 定义在 CC 全局 CLAUDE.md 的 skill 配置中（指向本地 .md 文件），不属于 ClawHub/Hermes 内置 skill。**正确做法**：直接告诉 CC 读取 skill 文件的完整路径（如「读 D:\<projects-root>\\cc-obsidian-pm\\SKILL.md」），CC 用 Read 工具加载即可。反面案例（2026-07-06）：Hermes 发「请根据 cc-obsidian-pm 技能更新…」，CC 尝试 Skill() 失败，Hermes 需补发路径提示。

27. **CC interview 表单禁止裸转发（v3.16 新增）**：CC plan mode 的 interview 表单（`Enter to select`、`↑/↓ to navigate`）列出选项时，**绝对禁止**把选项列表直接转发给用户问"你看选哪个"。这是最赤裸的传声筒——用户期望的是 Hermes 先做独立分析，判断每个选项的优劣，给出推荐理由，然后才让用户拍板。**2026-06-03 触发**：CC 询问 DOM 选择器方案（选项 1/2/3），Hermes 转发选项列表问用户，用户立即指出「不要当传话筒」。正确做法：独立分析 → 指出选项的利弊/可行性 → 给出明确推荐 → 附简要理由 → 然后让用户确认。如果某个选项涉及技术事实不确定（如需要 CC 自查），先把质疑发回 CC 澄清，澄清后再汇报用户。
27. **Hermes 侧就近处理违规**：就近处理铁律是双向的。CC 提议「我帮你写一份完整的 XX 文件，可以直接粘贴到配置里」→ Hermes 不应接受。云端文件始终由 Hermes 自己写入，CC 只产出内容建议（对话中讨论即可）。处理方式：CC 若越界提议写云端文件 → 立即 C-c 取消 → 明确告诉 CC「这个文件在云端，应该 Hermes 来写，你产出规则内容到对话中即可」。
28. **SSH 断连后 capture-pane 陷阱**：SSH 断开后 tmux session 回退到本地 bash，但 scrollback 中残留大量 CC 旧输出（方案、表格、提示符），致使 capture-pane 看起来 CC 还活着。判别方法：`tail -1` 看最后一行是不是 `$ ` 或 `>` —— 是 bash 则 SSH 已断，是 `>` 带 emoji 标记则 CC 运行中。恢复流程：先 `ssh -o ConnectTimeout=10 local-win "echo OK"` 确认 SSH 通 → tmux 内重新 `ssh local-win` → 进入 CC 工作目录 → `claude --continue` 恢复。切勿在断连的 session 内直接发 `<!-- HERMES-ACTIVATE -->`——bash 会把 `!` 当历史扩展报错。
33. **DISCUSS 优先于自动建议（用户强制规则）**：CC 在 `⏵⏵ accept edits on` 模式下生成的自动建议（如 `> 开始写 P1 代码`、`> 先验证...`），CC 会**优先执行自动建议**而忽略排队的 `[HERMES:DISCUSS]` 消息。**处理：capture-pane 看到 CC 执行工具调用（● Bash/Read 等），同时有 DISCUSS 排队（`Press up to edit queued messages`）→ 立即 `C-c` 打断。DISCUSS 已在队列中，打断后 CC 会自动处理下一条消息即 DISCUSS，无需重发。** 不打断则 CC 在错误方向浪费数分钟 token。用户明确要求（2026-06-02）：「以后遇到这种情况就先打断CC，让它先处理讨论，不然执行方向会有问题」。
36. **空闲判断铁律（v3.8 新增）**：CC pane 有三个独立区域——①输入框上方（emoji 标记 ✶/✽/✻/✢/· 等，有=thinking，无=空闲）；②输入框（`>` 提示符）；③底部状态栏（左侧=UI 模式，右侧=X% until auto-compact）。**空闲只看区域①，不看区域③。** accept edits、plan mode、normal mode 只是 UI 模式，只要有 emoji 标记就不是空闲，没有就是空闲。accept edits 模式下的限制是发送方式（用短 send-keys 不用 paste-buffer），不是不可发送。不要混淆"发送方式受限"和"不可发送"。
42. **accept edits 模式可能完全阻塞所有 send-keys（v3.10 新增→v3.42 修正→v3.43 新增预防）**：实测发现 accept edits 模式下不仅是 paste-buffer 被截断，**所有 send-keys 都可能被 CC 吞掉**——包括 BTab、Escape、C-c、/exit、普通短消息。pane 看起来有 `>` 提示符处于空闲，实际完全不响应。

   **⚠️ CC context 满时的恢复策略（2026-06-29 新增→2026-06-30 补完）**：当 CC 反复报 `API Error: The model has reached its context window limit` 时：① 先尝试 tmux 发 `/compact` + Enter ② 等待观察是否处理（compact 成功后 capture-pane 会看到 `Compacted` + 重新读取 rules 文件）③ 如果 compact 也报同样错误，可能是 accept edits 模式吞消息——此时 `Escape + BTab` 切到 plan mode → `Enter` 提交 `/compact` ④ **compact 完成后 capture-pane 确认 `Compacted` → 必须 BTab 切回 accept edits（看底部状态栏确认，不要凭记忆数次数）→ 发送「继续」让 CC 恢复工作**（CC compact 后不会自动继续！）⑤ **切勿用 `--resume` 重启旧 session**——会加载同样的膨胀 context 再次撞 limit。BTab 循环顺序：normal → auto → plan → accept edits → normal（4 档）。注意：tmux 发 /compact 和手动发没有本质区别，失败的根因更多是 accept edits 模式吞消息而非发送通道。

   **⚠️ 区分两种行为模式（2026-06-10 新增）**：
   - **延迟排队**（更常见）：send-keys 不是被吞，而是排队延迟送达——可能延迟 30s~数分钟后才出现在输入框中。判别信号：CC 当前正 busy（有 emoji/thinking 标记）时发的 send-keys 会在 CC 空闲后逐条出现。**处理**：不要重复发送同一指令（会导致重复排队），耐心等待 CC 完成当前操作后再检查输入框。
   - **完全阻塞**（少见但严重）：CC 空闲但仍不响应任何输入。判别信号：连续 3 次 send-keys 后 capture-pane 无任何变化（输入框无回显、状态栏不变）→ 确认为阻塞。**推荐恢复路径（按优先级）**：1. **核弹选项（最快最可靠）**：直接 `tmux kill-session -t claude-session` 杀掉整个 tmux session → `tmux new-session -d -s claude-session -x 200 -y 60` 重建 → SSH → cd → `claude --model glm-5.2` → 激活四步法。用户明确建议：「直接杀了tmux重进就行了」——比在阻塞 session 中尝试各种恢复命令快得多。2. 轻度尝试：C-c 暴力连发 3 次 → 等 1s → Escape → Enter。3. SSH 断连检查：`ssh -o ConnectTimeout=10 local-win echo OK`。SSH 断 + accept edits 阻塞 是双重故障模式，需先恢复 SSH 再处理 CC。**注意：accept edits 并非总是完全阻塞——见陷阱 43。**



> 详见 references/active-discussion-protocol.md —— 活跃讨论中的每轮协议纪律，补充任务边界协议未覆盖的轮次交互规范。


> 📋 以上为高频核心条目。完整 150 条 pitfalls（按原编号保留）详见 [references/pitfalls.md](references/pitfalls.md)。

### 双向心跳协议（v2.1）

```
Hermes 发指令 → CC 回 ACK 指纹（task_id+step） → CC 执行 → CC 发 DONE:step_N
    ↓ 30s 未收到 ACK                          ↓ PAUSE（需决策时）
    自动重发                                   Hermes 响应后继续
                                              ↓
                                              ERROR → CC 列文件清单 → Hermes 决策
                                              ↓
                                              COMPLETE（Hermes 发）→ CC 确认
```

### 每步交互状态摘要（强制）

每次 paste-buffer 指令末尾附不超过 3 行的状态摘要：

```
[state: task_id=xxx step=3/5 done=2 next=fix_encoding ctx=已修复2个文件]
```

**done 语义：** `done` = 本 task 中已收到 DONE 确认的最高 step 编号。只升不降。done < step = 正常执行中；done = step = 当前步已完成；done > step = 异常。

### Chunk 限制（强制，v2.1 更新）

单次指令不超过 **3 个步骤**（步 = Hermes 指令数，非操作数）。CC 在单步内可自主执行多个操作（如读取 5 个文件并逐一修改）。超过 3 步则拆分为多次交互，每步确认后再发下一步。违反此限制是导致"过度规划"和上下文丢失的直接原因。

### 协议缺口（已裁决）

> 来源：v3.0 压力测试 + 辩论协议验证（详见 `references/v3-protocol-test-results.md`）

| 原始缺口 | 最终裁决 | 行动 |
|----------|---------|------|
| STATUS 缺 DONE 包裹 | ❌ 不成立 | capture-pane 误判——CC 在所有步骤中均正确使用 `<!-- DONE -->` 包裹 STATUS |
| ACK 未触发 | ✅ 成立 | 已修正——ACK 触发条件从仅 `<!-- TASK -->` 扩展为匹配任何 `TASK:xxx` 模式 |
| 验证追踪依赖 ACK | ❌ 不成立 | 验证是 CC 自身职责（Read 回确认），不依赖 Hermes ACK |

### 架构约束

| 约束 | 说明 | 影响 |
|------|------|------|
| **CC 无法主动 PING** | LLM 请求-响应模式，无时钟 | CC context 已移除 PING；超时监控完全由 Hermes 负责（60s 无 DONE → 重发） |
| **CC 自然串行** | 一次处理一条消息 | 前置检查（emoji 标记）已足够防护，无需并发锁 |

## 未来方向：Agent 原生协议

> 详见 [references/acp-research.md](references/acp-research.md)

当前 tmux 模拟终端方案存在结构性限制（send-keys 截断、capture-pane 轮询、弹窗盲按）。ACP（Agent Client Protocol）是更优的 Agent-to-Agent 通信方式。

**ACP 集成进度（2026-06-02）**：

| 阶段 | 状态 |
|------|------|
| claude-agent-acp v0.39.0 安装 | ✅ |
| ACP 握手验证 | ✅ |
| Hermes → ACP E2E（SSH pipe） | ✅ 全链路通过 |
| P0 参数结构探明 | ✅ session/new + session/prompt 流式格式 |
| P1 ACP Client 代码 | ✅ `~/.hermes/acp_client/`（5 文件，集成测试通过） |
| P2 路由策略 | ⏳ 待设计 |
| P3 CC-ACP 联合编排 | ⏳ 待设计 |

**客户端快速复用**：复制 `templates/acp_bootstrap.py`，替换 API Key 即可验证全链路。

**已验证架构**：
```
Hermes(云端) ──SSH pipe──→ claude-agent-acp (Windows) ──→ 智谱 Anthropic 端点
              stdin/stdout    ndjson (一行一JSON)
```

## Verification Checklist

**每次 CC 操作完成后强制执行，不可跳过：**

- [ ] **操作一致性**：CC 结论与 capture-pane 观察到的操作记录是否一致（文件数、修改行数、Edit 次数）
- [ ] **独立核实**：是否独立核实了关键断言（文件存在、测试通过、git 状态），而非直接转发 CC 报告
- [ ] **送达验证**：cc-send.sh 返回 SEND_OK（内置清框校验）+ cc-wait.sh 收到 ACK/DONE 指纹比对 task_id+step 一致（脚本超时自动报 WAIT_TIMEOUT，不再依赖固定 sleep）
- [ ] **状态摘要**：是否已在指令末尾附加 `[state: task_id step done next ctx]` 状态行
- [ ] **步骤限制**：单次指令步骤数是否 ≤ 3（步=指令数，非操作数）
- [ ] **偏好隔离**：指令中是否包含了仅针对 Hermes 的用户偏好（如「全部做完再汇报」）？是 → 不得传达给 CC/芭迪，用户偏好按 agent 隔离
- [ ] **Silence 检查**：CC 是否超过 60 秒无输出？是 → 触发超时检查
- [ ] **PAUSE 检测**：capture-pane 是否出现 PAUSE 标记？是 → 处理 CC 的决策请求
- [ ] **任务记录**：CC DONE 中是否含 `[TASK_MAP]` 块？ → 提取后写入 `claude_task_map.json`
- [ ] **CC 自校验**：CC DONE 中是否含 `[CHECKLIST]` 块（涉及 Write/Edit 时必填）？缺失 → 追问 CC
- [ ] **空闲确认**：CC 输入框上方是否无 emoji 标记（✶/✽/✻/✢/· 等）？是 → 空闲可接受新任务
- [ ] **COMPLETE**：task 所有步骤完成后是否发送了 COMPLETE 标记
- [ ] **计划合规**：CC 输出的内容是否与约定的 INTEGRATION_PLAN（或等同文档）一致？有无引入已排除的功能、虚构的 provider、声称不存在的特性？发现偏差先辩论修正再继续
- [ ] **CC 声称-实际核查（强制，2026-11-21 v4.1）**：凡 CC 报告「已写入/已修改文件」，Hermes 必须拉回文件（scp）做关键标记 grep/diff 验证后才能采信，不得凭 DONE 摘要汇报。2026-11-21 实测两次「声称完成但实际只改部分」（修订计划只落实 1/4 项质疑；协议修订后仍有旧表述残留）。发现未落实 → 引用具体缺失项追问，禁止笼统重发原任务
- [ ] **辩论闭环自检（强制，2026-11-22）**：本 turn 与 CC 有交互且 CC 输出为方案类（output_type: analysis）→ 汇报用户前自答：我至少提出过一个可证伪的具体质疑并发回 CC 了吗？没有 → 补辩论或带豁免声明（见「辩论豁免声明制」）
