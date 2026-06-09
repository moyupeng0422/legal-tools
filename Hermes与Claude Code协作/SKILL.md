---
name: hermes-claude-collaboration
description: "Use when Hermes needs to orchestrate Claude Code on a local machine via SSH+tmux. Covers session management, monitoring, debate protocol, and error recovery."
version: 3.38.0
author: Custom
tags: [claude-code, ssh, tmux, orchestration, collaboration]
---

# Hermes × Claude Code 协作协议

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

区域③ 底部状态栏 → ⏸ plan mode on / ⏵⏵ accept edits on / 无标记=normal
区域③只影响发送方式，不影响空闲判断。

### 🚨 CC 启动序列铁律（六步法，不可跳步）

> ⚠️ **这是协作中最高频的违规点（#89 #90 #48），已多次被纠正又反复再犯。每次启动或恢复 CC 会话前，必须严格按以下顺序执行，不可凭记忆省略任何一步。**

```
Step 1  ssh local-win                          ← 先连 SSH，确认连通
Step 2  cd /d "D:\项目目录"                     ← 进入项目目录（不是 C:\Users\HUAWEI！）
Step 3  claude --model glm-5-turbo             ← 正常模式启动
Step 4  <!-- HERMES-ACTIVATE -->                ← 激活协作模式，等确认后继续
Step 5  /rename Hermes:<任务名>                 ← 带前缀，capture-pane 确认命名成功
Step 6  /resume <会话名>                       ← 仅恢复旧对话时，CC 内部命令
```

**新对话**：Step 1-5 完成后发 TASK
**恢复旧对话**：Step 1-5 完成后执行 Step 6

**🚫 启动命令中绝对禁止出现的参数：**
- `--resume` / `--continue`（应在 CC 内部执行，#5 #45 #90）
- `--dangerously-skip-permissions`（危险，#2 #89）

**弹窗处理（Step 3 过程中）：**
- Bypass Permissions 警告：`2` = Yes accept，`1` = No exit。**误按 1 会导致 CC 退出**
- 多个弹窗堆叠时：不要逐个通过，直接 kill session 重建
```

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

### 基础操作循环

每个与 CC 交互必须遵循：

```
1. 前置检查（4 项确认）
2. 任务命名 → 检查当前对话是否已命名；未命名则立即 `/rename 任务名` → 写入 `claude_task_map.json`（不等任务完成）
3. send-keys / paste-buffer → 发送指令或任务（附状态摘要）
4. 确认送达 → capture-pane 验证消息完整未被截断
5. 等待 ACK 指纹 → CC 回显 task_id + step，Hermes 比对一致才认为投递成功
6. poll (5-8s 间隔) → capture-pane 读取输出
7. 判断状态 → 继续轮询 / 处理弹窗 / 处理 PAUSE / 读取结果 → 事实校验
8. DONE 处理 → 检测 `<!-- DONE -->` 时提取 [TASK_MAP] 块 → 写入/更新 task_map 条目 → 执行 Verification Checklist → 汇报用户
9. COMPLETE → 发 `<!-- COMPLETE:task-X -->` 标记 task 结束
```

**状态摘要是强制的**：每条指令末尾必须附带 `[state: task_id=xxx step=M/N done=P next=xxx ctx=xxx]`，缺此行视为前置检查失败，不允许发送。

**done 语义（v2.1 明确定义）**：`done` = 本 task 中已收到 DONE 确认的最高 step 编号。只升不降。`done < step` 表示当前步正在执行或失败待处理（正常）；`done = step` 表示当前步已完成；`done > step` 异常。

**DONE 块解析**：CC 的 DONE 输出含 [TASK_MAP] 块时，Hermes 用正则 `\[TASK_MAP\](.*?)\[/TASK_MAP\]` 提取字段（task_id、step、done、session、timestamp），写入 `claude_task_map.json`。

**发送策略**：accept edits 模式和 plan mode 下禁止 paste-buffer，用分段短 send-keys（每条 <300 字符，间隔 1-2s，≤10 条）。正常模式下长消息优先短 send-keys；确需 paste-buffer 时，消息 ≤500 字符且必须 A+B 双重确认。**超过 500 字符一律用短 send-keys 分段，不可 paste-buffer**——即使正常模式下 paste-buffer 也曾截断。

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

   推荐方案：云端启动临时 HTTP 服务器（`python3 -m http.server 18888 --bind 0.0.0.0`），CC 用 `curl -s http://100.90.24.4:18888/file.tar.gz -o C:\Users\HUAWEI\file.tar.gz` 下载。HTTP 协议在低带宽高延迟链路上比 SCP 更健壮。

   详见 `references/bulk-file-transfer.md` 方向二。

### 快速参考卡

| 操作 | 命令 |
|------|------|
| **Print mode（推荐）** | `claude -p "task" --output-format json --allowedTools "Read,Edit" --max-turns 10` |
| 检查 session | `tmux has-session -t claude-session` |
| 创建 session | `tmux new-session -d -s claude-session -x 140 -y 40` |
| 启动 CC | `tmux send-keys -t claude-session 'cd /path && claude' Enter` |
| 激活协作 | `tmux send-keys -t claude-session '<!-- HERMES-ACTIVATE -->' Enter` |
| 发短消息 | `tmux send-keys -t claude-session '内容<300字' Enter` |
| 发长消息 | `load-buffer` + `paste-buffer -d`（仅正常模式） |
| 分段消息 | 短 send-keys 逐条发送，间隔1-2s，≤10条（plan/accept-edits模式） |
| 确认送达 | `capture-pane -S -10` 肉眼检查 + 等待 ACK 指纹（30s 超时重发） |
| 监控状态 | `tmux capture-pane -t claude-session -p -S -20` |
| 快速检查 | `tmux capture-pane -t claude-session -p -S -5` |
| 接受权限 | `tmux send-keys -t claude-session '数字'` → sleep 0.5s → `Enter`（两拍法） |
| 中断操作 | `tmux send-keys -t claude-session C-c` |
| Interview | `send-keys '数字'` → sleep 0.5s → `send-keys Enter`（两拍法） |
| 命名对话 | `tmux send-keys -t claude-session '/rename 任务名' Enter` |
| 切换对话（shell启动） | `tmux send-keys -t claude-session 'claude --resume 任务名' Enter` |
| 切换对话（CC内部） | `tmux send-keys -t claude-session '/resume 任务名' Enter` |
| 恢复最近 | `tmux send-keys -t claude-session 'claude --resume Hermes:<最近任务名>' Enter`（禁止 --continue） |
| 压缩上下文 | `tmux send-keys -t claude-session '/compact focus on 主题' Enter` |
| 退出 CC | `tmux send-keys -t claude-session '/exit' Enter` |
| 切换模式 | `tmux send-keys -t claude-session BTab` |
| PAUSE 响应 | `send-keys 'RETRY/ABORT/CONTINUE/PAUSE-ACK' Enter` |
| Task 完成 | `send-keys '<!-- COMPLETE:task-X -->' Enter` |

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

### Reference 索引

详细操作规范按需加载，不要一次性全部读取：

| Reference | 内容 | 加载时机 |
|-----------|------|---------|
| [skill-creation-workflow](references/skill-creation-workflow.md) | 通过 CC 的 `/skill-creator` 创建 Hermes 规范 skill 的完整流程——独立项目文件夹原则、分批创建策略、frontmatter 规范、上传部署；含**SKILL.md 架构原则**（聚合层纯路由表 + 子层相对路径的架构规范）| 将 CC 用于创建或重构 Hermes skill 套件时 |

### Reference 索引（续）

| Reference | 内容 | 加载时机 |
|-----------|------|---------|
| [session-lifecycle](references/session-lifecycle.md) | Session 创建/销毁、弹窗处理、任务切换、paste-buffer、发送前状态检查、预授权配置 | 首次启动 CC、处理弹窗、切换任务、发送消息前 |
|-----------|------|---------|
| [session-lifecycle](references/session-lifecycle.md) | Session 创建/销毁、弹窗处理、任务切换、paste-buffer、发送前状态检查、预授权配置 | 首次启动 CC、处理弹窗、切换任务、发送消息前 |
| [monitoring-debate](references/monitoring-debate.md) | 监控链路、状态判定、R1/R2/R3 辩论协议（含风险分级、R2子轮、查证分工、Token规则）、写作协作流程、事实校验 | 监控 CC 执行、校验 CC 输出、裁决争议、方案讨论 |
| [error-recovery](references/error-recovery.md) | 崩溃/权限误拒/API 限流/工具失败/SSH 断开/上下文耗尽 | CC 执行异常、连接中断 |
| [ssh-reconnect-playbook](references/ssh-reconnect-playbook.md) | SSH 断连恢复实战——症状识别、恢复流程、常见错误 | capture-pane 显示旧内容但 SSH 已断时 |
| [ssh-diagnostics](references/ssh-diagnostics.md) | SSH 连通性诊断决策树（refused vs timeout、Tailscale 状态、防火墙、sshd） | SSH 连接不通时 |
| [cc-context-file](references/cc-context-file.md) | CC 侧 `.claude/rules/hermes-collab.md` 完整草案——部署后 CC 自动加载协作协议（含 ACK/DONE 强制包裹要求） | 首次部署或修改 context 文件时 |
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
| [acp_bootstrap.py](templates/acp_bootstrap.py) | ACP 快速引导脚本模板——直接复制运行，验证 SSH→ACP 全链路 | 首次部署或诊断 ACP 连通性时 |

## Research Workflow (v3.3, updated v3.32)

When the user asks Hermes to research and evaluate external projects/skills/tools:

### Standard flow

```
1. Hermes defines scope → composes task for CC
2. CC clones repos / installs skills locally (Windows)
3. CC reads SKILL.md + directory structures
4. CC outputs analysis tables (per-project: purpose, deps, storage, compatibility)
5. Hermes feeds additional web search results CC missed
6. CC integrates new info → refine analysis
7. Hermes ↔ CC discuss: cut/keep/integrate decisions
8. CC outputs final plan document (markdown)
9. Hermes presents to user for approval
```

### Pre-research workflow (when CC Web Search is down)

When CC's Web Search is rate-limited or returns 0 results (common in plan mode), use this pattern instead:

```
1. Hermes does ALL web research itself (web_search + web_extract)
2. Hermes compiles findings into a structured file on cloud (write_file)
3. Hermes SCPs the file to Windows (scp → C:/Users/HUAWEI/<file>.txt)
4. Hermes sends short instruction: "读取 C:\Users\HUAWEI\<file>.txt 并按其中任务要求执行。不要使用Web搜索。"
5. CC reads the file, analyzes pre-supplied content, outputs conclusions
6. Hermes reviews CC's output independently → sends质疑 back for R2 debate if needed
```

**Advantages**: Bypasses CC's broken Web Search entirely; CC focuses on analysis not searching; SCP avoids plan mode send-keys truncation (see Pitfall #68).

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

1. **CC Web Search is broken + retry loop** — CC web searches frequently return 0 results (`Did 0 searches in Xs`). Worse, CC may enter a **retry loop**, repeating the same failed queries 4-6 times. **Hermes must (a)** do all web searches itself and **(b)** interrupt CC (Escape) when detecting retry loops, then supply pre-researched content via SCP file (`scp task.txt → CC reads file`). Never rely on CC to self-search. The SCP pre-research pattern is documented in Research Workflow §Pre-research workflow.
2. **禁止 `--dangerously-skip-permissions`**：使用正常模式 + `settings.local.json` 预授权安全操作
3. **Session 命名**：始终用 `claude-session`（唯一），通过 `claude_task_map.json` 映射多任务，不要创建 `cc-{task}` 多 session
4. **Print Mode 的适用范围（v3.36 修正）**：Print mode (`-p`) 适用于**一次性任务**——单次读取、分析、修改后退出，不需要上下文连续性。特别适用于自动修复（见陷阱 71）。**不适用于**多步骤交互任务（多轮辩论、分步执行、需要`--resume`跨轮次的任务），这些场景必须用 tmux 交互式 session。这是对 v3.0 本 skill 自身矛盾的修正——正文 Print Mode 节已正确描述适用范围，pitfall #4 的"禁止"是过时的 blanket 限制。**判断标准**：单次消息能完整描述且一轮对话可完成 → 用 print mode；需要发 2+ 条指令、等待中间结果、辩论 → 用 tmux。
5. **恢复用 `--resume <Hermes任务名>`，禁止 `--continue`（2026-06-06 修正）**：CC 的 session 存储在 Windows 本地 `~/.claude/`，`--continue` 会恢复最近 session（即用户本地正在使用的对话），导致 Hermes 看到并干扰用户的实时对话。Hermes 必须始终：(a) 新任务用 `claude` 启动全新 session，然后 `/rename Hermes:<任务名>`（带前缀避免与用户 session 冲突）；(b) 恢复旧任务用 `claude --resume Hermes:<任务名>` 精确指定。**绝对禁止 `--continue` 和无参数 `--resume`。**
6. **弹窗盲按风险**：权限弹窗不要一律 `y`，需审查操作内容；Trust 弹窗可以盲按 Enter
7. **监控超时 ≠ CC 完成**：连续 3 次相同输出可能是 CC 卡住而非完成，需判断 pane 状态
8. **tmux 在云端，不在 Windows**：所有 `tmux` 命令由 Hermes 在云端直接执行，不需要 SSH 到本地再跑 tmux。SSH 连接在 tmux session 内部，通向 Windows cmd。架构图见 Overview。
9. **accept edits 阻塞**：capture-pane 看到 `⏵⏵ accept edits on` 时，paste-buffer 发送的长消息可能只收到最后一行（CC 只解析了最后一段文本）。处理优先级：
   1. `BTab`（Shift+Tab）→ 切换到 `⏸ plan mode on`，此模式下短 send-keys 正常工作。
   2. `Escape` → `Enter` → 尝试退出 accept edits 回到正常模式
   3. **scp 文件绕过**：将长内容 scp 到 Windows（如 `/Users/HUAWEI/msg.txt`），用短 send-keys 让 CC `读取 C:\Users\HUAWEI\msg.txt`。绕过 paste-buffer 截断问题
   4. **最后手段**：`/exit` → 重新 `claude` 启动 → 再 paste-buffer。短 send-keys 不受 accept edits 影响，可用来发退出指令
10. **传话陷阱**：与 CC 协作时，Hermes 必须用自己的判断逐条分析 CC 输出（同意/反驳/修正），给出独立结论。按主题归纳 CC 建议后转述仍被视为传话——用户期望独立思考后再汇报，而非切换格式转发。收到 CC 方案后第一反应必须是「这个方案有没有问题？」而非「CC 说了 X，你怎么看？」。详见 monitoring-debate.md §3.1。
11. **勿假设密钥未配置**：用户问"怎么连上 XX"时，先检查 `authorized_keys` 和 `~/.ssh/config` 是否已有配置，不要上来就生成新密钥对。用户可能早已配好，只需给出最终命令（如 `ssh ubuntu@100.90.24.4 -p 2222`）。
12. **CC interview 表单用数字键 + 两拍法**：CC plan mode 的 interview 表单上写"Tab/Arrow keys to navigate"，但直接按数字键（1-6）更高效可靠。**关键：数字和 Enter 必须分两拍发送**（`send-keys '数字'` → sleep 0.5s → `send-keys Enter`），间隔 ≥ 300ms。单次 `send-keys '数字' Enter` 可能被 CC 忽略不生效。选择后 capture-pane 验证，未生效则 Ctrl+C 取消 → 等空闲 → 重发消息避开 interview 表单。
13. **Plan mode 下 paste-buffer 不可靠**：plan mode（`⏸ plan mode on`）和 accept-edits 模式一样，paste-buffer 可能只收到消息开头几个字（多次会话实测：~600 字消息只收到片段）。**可靠替代：分段短 send-keys**，每条 <300 字符，间隔 1-2s，总共不超过 10 条。长内容写云端文件 → scp 到 Windows → 让 CC `读取 <文件路径>`。最可靠方案：多段短 send-keys 逐条发送。
14. **双轨规则放置**：本 skill 的核心行为规则（不传话、质疑优先、独立核实）已同步嵌入 SOUL.md（每轮自动加载）。Skill 提供详细操作协议，SOUL.md 提供简化版常驻提醒。新增关键行为规则时，先放入 SOUL.md 确保持续生效，再在本 skill 补充操作细节。仅放 skill 中容易被遗忘——skill 需主动加载，Agent 在快速响应时经常跳过。
15. **过度规划**：单次 paste-buffer 指令不应超过 **3 个步骤**（步 = Hermes 指令数，非操作数）。CC 上下文窗口在处理长指令时可能丢失中间步骤细节，导致执行偏差。超过 3 步的任务必须拆分发送，每步完成后确认再发下一步。
16. **沉默执行**：CC 执行中发现异常（工具失败、文件不存在）并输出了错误信息，但 Hermes 的 capture-pane 未及时捕获到响应，误判任务完成。轮询间隔不得超过 **30 秒**，CC 超过 **60 秒**无输出必须触发超时检查。
17. **并发冲突**：CC 仍在处理上一个任务时（emoji 标记/工具调用中），不要发送新指令。先等空闲确认，再发下一轮。**例外**：测试并发行为时允许有意违反——但必须明确标注是测试，且事后回归正常纪律。
18. **task_map 漏记**：每次 `/rename` 后必须**立即**更新 `claude_task_map.json`，不要等任务完成后再补——到那时上下文已被压缩，记录必然丢失。本 skill 自身在 v3.0 测试中连续漏记 5+ 条任务，是反面教材。
19. **恢复不对等**：CC 有崩溃恢复流程，但 Hermes 自身卡住/超时时没有对等机制。如果 Hermes 超过 2 分钟未响应 CC 的 DONE 信号，应视为异常并进入诊断。
20. **发送确认机制**：每次 paste-buffer 或 send-keys 后，必须确认消息完整送达。A) capture-pane -S -10 肉眼检查内容完整；B) 等待 CC 的 ACK 指纹回执（task_id + step 比对），30s 超时重发。仅依赖 paste-buffer 返回值（永远返回成功）是假象——内容可能截断但无法检测。
21. **CC 侧上下文文件**：一次性部署 `.claude/rules/hermes-collab.md` 到 CC 本地。`.claude/rules/*.md` 属于 CC 的 `project` 设置源，自动随 session 加载，不依赖 CLAUDE.md 显式 `@` 引用。但如果项目 `CLAUDE.md` 已引用其他 rules 文件，应同步添加 `@.claude/rules/hermes-collab.md` 保持一致性（人类和 AI 工具的可发现性）。部署后 CC 能主动识别协作状态、理解结构化消息格式、执行行为守则。详见 `references/cc-context-file.md`。
22. **v3.0 修订方案**：2026-06-01 Hermes × CC 双向诊断讨论产出的完整修订方案，见云端文件 `~/.hermes/cc-integrated-plan.md`（311行）。含结构化消息协议（TASK/ACK/DONE/ERROR/PING/DISPUTE）、双向心跳、CC 行为守则（5条强制+3条引导）、降级规则、优先级排序（P0-P3）。该文件是 v3.0 修订的权威参考。
23. **PING 不可由 CC 实现**：LLM 是请求-响应模式，无时钟/定时器/后台能力，无法在空闲期主动发送消息。CC context 文件（v3.1）已移除全部 PING 条款。监控超时职责完全归 Hermes 侧：60s 无 DONE/HERMES 标记 → 主动 capture-pane 检查 CC 状态 → 重发指令或汇报用户。
24. **DONE 标记在 capture-pane 中可能被滚动截断**：多行输出中 `<!-- DONE:task:step -->` 起始标记可能被 pane 缓冲滚动到不可见区域，导致误判 STATUS 裸出。核实方法：捕获时用 `-S -60` 或更大回滚行数；若 STATUS 块完整但未见 DONE，加大 capture-pane 回滚幅度后再确认。
25. **先补规则再执行**：CC 协作中发现协议缺口（如 CC 不知道自己不能写云端文件）时，先暂停任务，补上规则（双方 context 文件），再继续。不要在规则残缺的状态下推进——缺规则的协作必然出错。
26. **假辩论 ≠ 真辩论**：收到 CC 方案后写一段独立评价再汇报用户，这不构成辩论。辩论必须是双向的——把质疑发回 CC，让 CC 回应，你再评估回应，R1→R2→R3 的轮次才算辩论。独立分析是辩论的**起点**，不是终点。独立分析后应：① 列出具体质疑 → ② 发回 CC 做 R2 质询 → ③ CC 回应后评估修正 → ④ 可能再追问 R2b/R2c → ⑤ 最终结论汇报用户。缺了 ②~④ 就是假辩论。**2026-06-02 两次触发：** 路由边界讨论和 tmux 优化讨论，均修正了 CC 的错误假设。核心教训：独立分析后若未发回 CC 质询就直接汇报用户，不管分析多深入，都是传声筒。

27. **CC interview 表单禁止裸转发（v3.16 新增）**：CC plan mode 的 interview 表单（`Enter to select`、`↑/↓ to navigate`）列出选项时，**绝对禁止**把选项列表直接转发给用户问"你看选哪个"。这是最赤裸的传声筒——用户期望的是 Hermes 先做独立分析，判断每个选项的优劣，给出推荐理由，然后才让用户拍板。**2026-06-03 触发**：CC 询问 DOM 选择器方案（选项 1/2/3），Hermes 转发选项列表问用户，用户立即指出「不要当传话筒」。正确做法：独立分析 → 指出选项的利弊/可行性 → 给出明确推荐 → 附简要理由 → 然后让用户确认。如果某个选项涉及技术事实不确定（如需要 CC 自查），先把质疑发回 CC 澄清，澄清后再汇报用户。
27. **Hermes 侧就近处理违规**：就近处理铁律是双向的。CC 提议「我帮你写一份完整的 XX 文件，可以直接粘贴到配置里」→ Hermes 不应接受。云端文件始终由 Hermes 自己写入，CC 只产出内容建议（对话中讨论即可）。处理方式：CC 若越界提议写云端文件 → 立即 C-c 取消 → 明确告诉 CC「这个文件在云端，应该 Hermes 来写，你产出规则内容到对话中即可」。
28. **SSH 断连后 capture-pane 陷阱**：SSH 断开后 tmux session 回退到本地 bash，但 scrollback 中残留大量 CC 旧输出（方案、表格、提示符），致使 capture-pane 看起来 CC 还活着。判别方法：`tail -1` 看最后一行是不是 `$ ` 或 `>` —— 是 bash 则 SSH 已断，是 `>` 带 emoji 标记则 CC 运行中。恢复流程：先 `ssh -o ConnectTimeout=10 local-win "echo OK"` 确认 SSH 通 → tmux 内重新 `ssh local-win` → 进入 CC 工作目录 → `claude --continue` 恢复。切勿在断连的 session 内直接发 `<!-- HERMES-ACTIVATE -->`——bash 会把 `!` 当历史扩展报错。
29. **CC 弹窗统一用两拍法**：不仅是 interview 表单（数字 1-6 选择），权限对话框（"Do you want to proceed? > 1. Yes / 2. No"）同样要用两拍法：`send-keys '数字'` → sleep 0.5s → `send-keys Enter`。单次 `send-keys '1' Enter` 可能被 CC 忽略。Trust 弹窗（仅信任确认，无选项）可以盲按 Enter。选择后务必 capture-pane 验证是否生效——未生效则 Escape 取消后重试。
30. **Plan mode 多段 send-keys 截断**：Plan mode（`⏸`）下 CC 的输入框可能只捕获第一段消息，后续分段被丢弃——即使间隔 1-2s、每条 <300 字符也未必全部收到。可靠方案：① 将长内容 scp 到 Windows 后让 CC `读取 <文件路径>`；② 或在同一条 send-keys 中发送完整消息（不拆分）。拆分发送后必须 capture-pane 肉眼确认所有分段都被 CC 收到。
31. **真实 CC vs delegate_task 子代理**：`delegate_task` 是在云端本机 spawn 的 LLM 子代理，**不是** Windows 上的真实 Claude Code。当用户说"让 CC 做"时，必须通过 tmux → SSH → Windows CC 通道。只有在 SSH 不可用或任务不需要 Windows 本地文件操作时，才考虑子代理模拟。判断依据：CC 是否能通过 tmux 连通（`ssh local-win echo OK`）——能则用真实 CC，不能则汇报用户重建连接。
32. **`claude --continue` / `/resume` 恢复失败（Cannot read properties of null）**：SSH 断连后 `--continue` 或 CC 内 `/resume <name>` 可能报 `Cannot read properties of null (reading 'split')`，说明会话状态文件损坏。此时直接 `claude` 启动新会话即可，不丢失之前的会话文件——在新会话中可通过 `/resume <name>` 尝试恢复（新会话的状态文件干净）。
33. **DISCUSS 优先于自动建议（用户强制规则）**：CC 在 `⏵⏵ accept edits on` 模式下生成的自动建议（如 `> 开始写 P1 代码`、`> 先验证...`），CC 会**优先执行自动建议**而忽略排队的 `[HERMES:DISCUSS]` 消息。**处理：capture-pane 看到 CC 执行工具调用（● Bash/Read 等），同时有 DISCUSS 排队（`Press up to edit queued messages`）→ 立即 `C-c` 打断。DISCUSS 已在队列中，打断后 CC 会自动处理下一条消息即 DISCUSS，无需重发。** 不打断则 CC 在错误方向浪费数分钟 token。用户明确要求（2026-06-02）：「以后遇到这种情况就先打断CC，让它先处理讨论，不然执行方向会有问题」。
34. **Hermes 不得擅自修改 CC 输出中的配置值**：修改 CC 脚本中的 BASE_URL、model、API key 等配置值前，必须用事实验证（查官方文档、settings.json、实际测试），不能在无依据的情况下凭记忆修改。
35. **CC 代码的第一版输出需要逐行审查**：CC 频繁在同一类问题上出错——(a) 环境变量名混淆（ANTHROPIC_API_KEY vs ANTHROPIC_AUTH_TOKEN）(b) 协议字段结构假设错误（扁平解析 vs 嵌套解析）(c) 平台路径假设（Linux /home/ubuntu 当 Windows cwd）(d) 非有效参数（mode 传给不接受它的方法）(e) ACP 方法名错误（messages/create vs session/prompt）。Hermes 应预期 CC 的第一版代码包含此类错误，逐行审查后再执行，不要只看概要描述就通过。
36. **空闲判断铁律（v3.8 新增）**：CC pane 有三个独立区域——①输入框上方（emoji 标记 ✶/✽/✻/✢/· 等，有=thinking，无=空闲）；②输入框（`>` 提示符）；③底部状态栏（UI 模式）。**空闲只看区域①，不看区域③。** accept edits、plan mode、normal mode 只是 UI 模式，只要有 emoji 标记就不是空闲，没有就是空闲。accept edits 模式下的限制是发送方式（用短 send-keys 不用 paste-buffer），不是不可发送。不要混淆"发送方式受限"和"不可发送"。
37. **CC 自动推荐 vs 用户输入（v3.8 新增）**：capture-pane 中 `>` 开头的行可能是 CC 自动推荐内容（如 `> 开始写 P1 代码`），不是用户输入。区分方法：自动推荐前通常有 CC 的思考输出，且内容以 CC 的口吻描述下一步操作。真正的用户输入不会出现在 capture-pane 的 CC 输出区。
38. **指令应自包含上下文 + rationale（v3.8 新增）**：Hermes 发送指令时，不应依赖 CC 看不到的上下文。每条指令应包含关键背景信息 + 操作理由（rationale），让 CC 能在没有历史对话的情况下理解任务背景。反面：依赖"按照上次的方案继续"而 CC 看不到"上次的方案"。正面：`修改 database.ts 的连接超时从 30s 到 60s。原因：远端 API 响应变慢导致频繁超时。`
39. **预授权范围（v3.8 新增）**：仅预授权 `Bash(git *):allow`（git 操作有 reflog 兜底，可追溯）。python/node/cp/mv 全部保留弹窗——python -c/node -e 可执行任意代码，cp/mv 可移动任意文件，风险过高。不在协作链路的远程 agent 场景下预授权这些命令。
40. **Skill 更新后必须重新加载（v3.9 新增）**：用户说"调整过 XX skill 了"时，必须先 `skill_view` 重新读取最新内容，再按新规则操作。不能在旧版本记忆基础上继续——用户调整往往是对之前协作问题的修正（如 v3.8 的两步确认法、消息长度指纹），不重新加载等于无视修正。**反面案例（2026-06-02）**：用户更新协作 skill 后，Hermes 仍用旧的单次 `-S -5` 判空闲导致并发冲突，用户直接指出需重新读取。
41. **`/clear` 后的重激活（v3.9 新增）**：CC 执行 `/clear` 后对话完全清空。Hermes 侧需重新执行完整激活流程：① `<!-- HERMES-ACTIVATE -->` 重新激活协作模式 ② `/rename <任务名>` 命名新对话 ③ 写入 `claude_task_map.json`。不能用 `/clear` 前的激活状态和对话名称。两步确认法在此场景尤为重要——scrollback 中残留的 `✻ Cooked for Xs` 等旧 thinking 标记需与当前状态（`> ` + 无新 emoji）区分。
42. **accept edits 模式可能完全阻塞所有 send-keys（v3.10 新增）**：实测发现 accept edits 模式下不仅是 paste-buffer 被截断，**所有 send-keys 都可能被 CC 吞掉**——包括 BTab、Escape、C-c、/exit、普通短消息。pane 看起来有 `>` 提示符处于空闲，实际完全不响应。**判别信号**：连续 3 次 send-keys 后 capture-pane 无任何变化（输入框无回显、状态栏不变）→ 确认为阻塞。**唯一可靠恢复路径**：C-c 暴力连发 3 次 → 等 1s → 重发 `claude --resume` → 若仍无变化则检查 SSH 是否已断（`ssh -o ConnectTimeout=10 local-win echo OK`）。SSH 断 + accept edits 阻 塞 是双重故障模式，需先恢复 SSH 再处理 CC。**注意：accept edits 并非总是完全阻塞——见陷阱 43。**

43. **accept edits 多消息排队 + C-c 轮转（v3.23 新增）**：accept edits 模式下输入框有多条排队消息时，C-c 一次**不是清空**而是切换到下一条排队消息。需连续 C-c 直到全部轮转完才能真正清空。如果 BTab/Escape 均无法切换模式，**直接 Enter 处理当前排队消息**——处理完后 CC 通常自动切换回 plan mode（实测：「⏵⏵ accept edits on」→ Enter 处理消息 →「⏸ plan mode on」），这是比 BTab/Escape 更可靠的退出 accept edits 路径。判别：C-c 后输入框文字变了（不同消息）→ 是多消息排队，继续 C-c 或 Enter 处理；C-c 后输入框清空（`> ` 空）→ 只有一条消息已清除。
43. **用户明确要求：两步确认法不可跳过（v3.10 新增）**：用户指出「你有在好好确认cc的状态吗」——Hermes 在执行 CC 前置检查时存在偷懒跳过两步确认的趋势。**强制规则**：每次与 CC 交互前，两步确认（capture-pane -S -20 → 等 3s → capture-pane -S -10）是必须的，不允许用单次 `-S -5` 替代。特别在以下高风险场景更不可跳过：(a) 刚完成上一任务后的首次检查 (b) accept edits 模式下的检查 (c) 长时间未监控后的恢复检查。
44. **Tailscale relay 假活（v3.11 新增）**：tailscale status 显示 active relay hkg 但 tailscale ping 全部超时——relay 连接卡死但状态未更新。判别：tailscale status 的 rx 字段长时间不变（如 rx 92016 持续数分钟）→ relay 已死。修复：先在 Windows 端 Disconnect → Connect（通常无效），终极大招是云端 `sudo tailscale down && sleep 3 && sudo tailscale up`→ 重建 relay 连接。与 SSH 断连的关联：Tailscale relay 假活 → SSH 超时 → tmux 内 CC 进程退出 → capture-pane 显示旧 scrollback（陷阱 28）。需先修复 Tailscale，再走 SSH 重连流程。
45. **CC 已运行时的对话切换命令（v3.12 新增）**：CC 已在 tmux 中运行时，切换对话用 CC 内部命令 `/resume <会话名>`，不是 shell 命令 `claude --resume`。后者用于从 bash 启动 CC 时指定目标会话——在 CC 内部执行 `claude --resume` 会退出当前 CC 再开一个新的 CC 进程，且可能因状态文件冲突报错。判断方法：capture-pane 看到 `> `（CC 提示符）→ 用 `/resume`；看到 `$ ` 或 `>`（bash 提示符）→ 用 `claude --resume` 启动。
46. **会话名大小写敏感（v3.12 新增）**：CC 的会话名严格区分大小写。法信mcp ≠ 法信MCP——用错大小写会导致 Session xxx was not found。不确定准确名称时，先发 `/resume`（不带参数）让 CC 列出可用会话。
47. **`/rename` 后输入框残留（v3.13 新增）**：`/rename 任务名` 执行后，输入框可能残留 `/rename 任务名` 文本。在发下一条指令前，必须 capture-pane 确认输入框干净（只显示 `> `），否则 CC 会把 rename 命令文本也当输入执行。**强制步骤**：rename → 等 2s → capture-pane -S -3 → 看到输入框有残留文字 → Escape 清空 → 再 capture-pane 确认干净 → 然后才能发下一条指令。
48. **新会话激活四步法（v3.13 新增）**：CC 新会话启动后，必须严格按顺序执行：① `<!-- HERMES-ACTIVATE -->` ② `/rename 任务名` ③ 写入 `claude_task_map.json` ④ 才能发送 TASK。跳步会导致 task 无法正确追踪。此序列是 CC 协作的基础骨架，不可省略任何一步。每个步骤之间需 capture-pane 确认完成（激活确认协作模式消息、rename 确认 Session renamed、task_map 确认写入成功）。反面案例（2026-06-03）：启动 CC 后直接发 TASK 漏掉 rename，用户指出"你还没rename"。
49. **CronCreate session-only 生命周期（v3.14 新增）**：CC 的 CronCreate 创建的 cron job 仅在当前 CC session 存活，session 结束后自动清理（上限 3 天）。这意味着：① 监控类 cron 需要在 CC 会话保持期间才有效 ② session 结束（`/exit`、崩溃、SSH 断连导致 CC 退出）后所有 cron 自动消失 ③ 长期监控需要 Hermes 侧 cron 替代。本 session 创建的 token 监控 cron（1db945fb）即受此限制。恢复方法：CC 重启后重新创建 cron。
50. **Gateway 重启 → tmux 全死（v3.15 新增）**：任何 profile 的 Gateway 重启（包括 `/* 重启 */` 指令或手动 `systemctl restart` 触发）会杀死 tmux server（作为 Gateway 子进程）。后果：tmux session `claude-session` 消失、SSH 连接断开、CC 进程退出、CC cron 全部丢失。**恢复流程（按序执行，不可跳步）**：① `ssh -o ConnectTimeout=10 local-win echo OK` 确认 SSH 存活（若不通则先修 Tailscale → 见陷阱 44）② `tmux new-session -d -s claude-session -x 140 -y 40` 重建 session ③ tmux 内 `ssh local-win` ④ `cd /d "D:\\claude vscode"` ⑤ `claude --resume <会话名>` 恢复 CC ⑥ 激活四步法（陷阱 48）⑦ 重建 CC cron（陷阱 49）。**关键**：Hermes 侧 cron 不受影响（Hermes cron 运行在调度器进程中，不依赖 tmux），但 Hermes 监控 cron 会因 tmux gone 而检测到异常——应自动在下一 tick 尝试上述恢复，而非报错即退出。**额外注意**：Gateway 重启后 Hermes 自身也收到 compaction summary，不得盲目执行 pending work——参见 hermes-agent skill §Gateway restart post-recovery protocol。
51. **Plan mode 下 Escape 可能无法清空输入框残留文字（v3.16 新增）**：plan mode 下 CC 输入框有残留文字（来自历史交互或自动建议）时，多次按 Escape 可能显示 "Esc again to clear" 但文字始终不清。**解决方案**：发一次 `C-c` 即可清空输入框（只按一次，不要连按两次——第二次会真正退出 CC）。注意与 accept edits 阻塞（陷阱 42）区分：plan mode 下 C-c 一次通常可靠清空；accept edits 下可能需暴力连发。实测案例（2026-06-03）：输入框残留 `用 rmfyalk_search 检索...` 文字，Escape ×3 + "Esc again to clear" 三次均无效，C-c 一次立即清空。
52. **禁止把 CC 的 UI 界面原封不动抛给用户（v3.17 新增）**：CC 的 interview 表单（数字选项 1-6）、plan 审批对话框（"Would you like to proceed?"）、选项列表等，是 CC 与 Hermes 之间的交互界面，**不是给用户看的**。Hermes 必须先独立分析选项、形成自己的判断，再以自己的语言向用户汇报结论和建议——绝不直接 dump CC 的 UI 文字。反面案例（2026-06-03）：CC 弹出 DOM 选择器 interview 表单（6 个选项），Hermes 直接截图描述给用户，被用户纠正「不要当传话筒」。正确做法：分析各选项优劣 → 形成推荐 → 用自己的话汇报 → 确认后自行操作 CC 表单。即使用户需要做决策，也应呈现为 Hermes 的分析框架（"我建议选 2，原因：..."），而非 CC 的原始选项列表。
53. **CC 本地项目开发需记录过程到 `claude.local`（v3.18 新增）**：当 CC 在本地 Windows 上进行具体项目开发（代码修改、bug 修复、功能开发）时，必须在任务完成时将开发过程摘要写入项目根目录的 `claude.local` 文件。内容包括：改了哪些文件、修复了哪些 bug、新增了哪些功能、遇到的坑及解决方案。**Hermes 在发送 TASK 指令时必须明确告知 CC 此要求**（如附加「完成后将开发过程记录到项目的 claude.local」）。此文件作为项目级开发日志持久化，跨越 CC session 不丢失，便于后续 session 快速了解项目历史变更。反面案例（2026-06-03）：CC 完成 login-helper keepalive 功能开发、修复了中文路径和编码 2 个 bug，但未记录到项目中——下次新 session 需要从头理解项目状态。
54. **SSH 启动的 Playwright headed 浏览器无法在 Windows 桌面显示窗口（v3.19 新增）**：通过 SSH → tmux → Windows 链路启动的 Playwright `headless=False` 浏览器，Edge 进程能正常启动和导航，但 `MainWindowHandle` 始终为 0——窗口在 SSH session 的不可见上下文中，不会出现在用户桌面。这不是代码 bug，是 Windows session 隔离机制。**判别方法**：`powershell -Command "Get-Process msedge \| Select-Object MainWindowHandle"`——全部为 0 即确认。**解决方案**：CDP（Chrome DevTools Protocol）。用户在 Windows 桌面手动启动 Edge 并开启调试端口（`msedge --remote-debugging-port=9222`），login-helper 通过 CDP 连接到已有浏览器实例操控保活和提取。详见 `references/cdp-browser-approach.md`。反面案例（2026-06-03）：反复排查 BROWSER_DATA_DIR 路径、lockfile、Playwright 版本均无法解决，最终确认是 SSH 环境限制而非代码问题。：当 CC 在本地 Windows 上进行具体项目开发（代码修改、bug 修复、功能开发）时，必须在任务完成时将开发过程摘要写入项目根目录的 `claude.local` 文件。内容包括：改了哪些文件、修复了哪些 bug、新增了哪些功能、遇到的坑及解决方案。**Hermes 在发送 TASK 指令时必须明确告知 CC 此要求**（如附加「完成后将开发过程记录到项目的 claude.local」）。此文件作为项目级开发日志持久化，跨越 CC session 不丢失，便于后续 session 快速了解项目历史变更。反面案例（2026-06-03）：CC 完成 login-helper keepalive 功能开发、修复了中文路径和编码 2 个 bug，但未记录到项目中——下次新 session 需要从头理解项目状态。
54. **Playwright/Edge 路径避免非 ASCII 字符（v3.19 新增）**：Windows 上 Playwright 使用 Edge 时，`launch_persistent_context()` 的 `user_data_dir` 参数若包含中文路径，Edge 会以 exitCode=21 启动失败（无明确错误提示）。根因是 Chromium 系浏览器对非 ASCII 路径的兼容问题。**修法**：将 browser_data 目录放到纯 ASCII 路径下，如 `%TEMP%/login-helper-browser_data`。反面案例（2026-06-03）：login-helper 的 `BROWSER_DATA_DIR` 原指向含中文的 `D:\claude vscode\法律相关skill自研仓库\...`，Edge 反复 exitCode=21 无法启动，改为 `%TEMP%` 子目录后立即正常。详见 `references/edge-troubleshooting.md`。
55. **SSH → Windows headed 浏览器不弹窗：是环境限制，不是代码 bug（v3.20 新增）**：通过 SSH 在 Windows 上启动 Playwright headed 模式的 Edge 时，浏览器进程可以正常运行和导航（页面加载成功），但**窗口不会出现在用户的 Windows 桌面上**——所有 `MainWindowHandle` 均为 0。根因是 SSH session 运行在非交互式会话中，无权访问用户的交互式桌面。**判别方法**：`powershell "Get-Process msedge | Select-Object Id, MainWindowTitle, MainWindowHandle"` 看到 MainWindowHandle 全为 0 但进程存在即可确认。**解决方向**：不要试图通过 SSH 弹窗给用户看。替代方案——① CDP（Chrome DevTools Protocol）：用户手动启动 Edge 带 `--remote-debugging-port=9222`，Playwright 通过 CDP 连接到已有浏览器实例；② 用户自己在 Windows 终端运行脚本。反面案例（2026-06-03）：CC 反复尝试多种 headed 模式、换路径、换 profile 均无法弹窗，Hermes 介入分析后确认是 SSH session isolation 的硬限制，浪费大量 token 在不可行的方向上。
56. **CC 自动压缩可能耗时 2~3 分钟（v3.21 新增）**：CC 在上下文接近上限时自动触发 `/compact`，期间 capture-pane 显示 `✶ Compacting conversation…` 或 `✢ Compacting conversation…`。压缩可能持续 2 分钟以上，看起来像卡住，实际在正常处理。**不要 C-c 打断**——压缩是自发的清理操作，打断无益且可能丢失压缩进度。耐心等待压缩完成，CC 会自动恢复响应。反面案例（2026-06-03）：压缩耗时 2 分 37 秒，Hermes 多次检查 pane 犹豫是否打断，最终选择等待。正确的做法是识别 `Compacting conversation…` 信号后拉长轮询间隔（15-20s），等它自行完成。

57. **压缩后 CC 丢失上下文可能导致错误判断（v3.22 新增）**：压缩完成后 CC 会 re-read 关键文件以恢复上下文，但由于对话历史被压缩，CC 可能忘记当前任务的实际状态——比如把正常运行的进程误判为已中断，把当前写入的状态文件误判为旧数据。**Hermes 必须在压缩完成后主动纠正 CC**：告知当前正在运行什么、状态文件的含义、任务的真实进展。不要等 CC 自己从文件中推测——它缺少压缩前的对话记忆，推测容易出错。反面案例（2026-06-03）：CC 压缩后读取 keepalive_status.json 和文件列表，错误认为 CDP 保活任务可能已中断、状态文件是旧数据，实际保活正常运转三轮。Hermes 发纠正消息后 CC 才恢复正确认知。教训：压缩后 CC 的第一版分析结论不可信，需要 Hermes 主动补充上下文再验证。

59. **禁止不必要的 git 远程操作（v3.24 新增）**：当 CC 检查本地已 clone 的仓库状态时（如 health-coach），CC 倾向于自动执行 `git remote -v` / `git fetch origin` 等网络操作。**用户已明确纠正**：「不是都在本地的吗，为什么要git远程？」。正确做法：Hermes 在 TASK 指令中明确指定「只用本地文件检查——ls, find, head, read 命令，不要 git fetch/remote 等网络操作」。理由：(a) git fetch 涉及网络，可能因网络问题 hang 住数分钟；(b) 用户只关心本地内容完整性，不需要与 remote 比对；(c) `git fetch` 等操作在 CC 中每次都需要单独批准弹窗，拖慢流程。当用户说「检查本地仓库」时，应假设本地就是完整的引用源，除非明确要求比对 remote。反面案例（2026-06-03）：CC 在 Step 4 评估中自动执行 `git fetch origin` 检查 upstream 状态，用户立即纠正「不要远程」。：`read_file` 输出中的 API key 会被掩码为 `sk-3e2...c0c1`，**严禁将此掩码字面量用作 `patch` 的 `old_string`**。`patch` 的模糊匹配策略可能使掩码匹配到真实 key，然后用字面量 `...` 覆盖，导致 config 不可逆损坏。正确做法：① 通过 `python3` 二进制读取确认真实字节后才构造 `old_string`；② patch 后立即验证 key 完整性；③ 若 key 已损坏，从同文件的 provider 子段或其他 profile config 恢复（它们通常共享同一 key）。反面案例（2026-06-03）：用 read_file 的掩码输出 patch default config，model.api_key 被替换为 `sk-3e2...c0c1`，需从 deepseek provider 段找回真实 key 修复。

60. **CC 自带 `/skill-creator` 命令（v3.24 新增）**：CC 内置了 `/skill-creator` 命令，可以交互式地创建、修改和测试 Hermes 兼容的 SKILL.md。当需要创建规范的多组件 skill 套件时，优先使用 `/skill-creator` 而不是手动编写。能力：① 创建新 skill → 交互式创建流程（frontmatter、tags、commands 自动生成）② 修改现有 skill → 传入 SKILL.md 路径进行优化（中文本地化、精简冗余、增加触发词）③ 测试 skill → 评估 skill 的触发准确性和性能。触发方式：在 CC 对话中输入 `/skill-creator`，CC 会进入交互式 interview 流程（plan mode 下用数字键 + 两拍法选择选项）。

61. **Skill 创建必须用独立项目文件夹（v3.24 新增）**：CC 创建或重构 Hermes skill 时，**绝对禁止**直接在克隆的仓库目录（如 health-research/）中写 SKILL.md。克隆仓库是原始代码源，应保持不动。正确做法：在 `D:\claude vscode\` 下新建独立项目文件夹（如 `health-management-skill/`），其中：
   ```
   health-management-skill/
   ├── SKILL.md              ← 聚合 skill（入口）
   ├── skills/               ← 各子模块 skill 定义
   │   ├── component-a/SKILL.md
   │   └── component-b/SKILL.md
   ├── references/           ← 引用文档
   └── scripts/              ← 核心脚本副本或软链
   ```
   克隆的代码**不能**通过路径引用说明——技能必须自包含，scripts/references/templates 文件需实际复制到技能目录下。用户明确纠正（2026-06-03）：「不应该是使用引用路径这种方式啊，我要的是一个完整能用的skill」。

62. **CC 输出的 skill 内容必须逐项核对计划约定（v3.25 新增→v3.26 强化）**：CC 创建的 SKILL.md 内容可能包含我们已讨论排除的功能。Hermes 必须在每批完成后逐项核对约定文档（如 INTEGRATION_PLAN），发现偏差发回 CC 修正再继续。核对要点：\n   - tags/description 中是否含应排除的术语（如 Xiaomi wearable——无实现）\n   - commands 是否引用已砍除的文件\n   - **路由路径：`/skill-creator` 生成的扁平式路径（`scripts/diet.py`）是否匹配实际嵌套路径（`skills/diet-tracker/scripts/diet.py`）——这是最容易出错的点，每次必查**\n   - description 是否声称不存在的功能\n   - 涉及药物/医疗建议的 skill 是否有免责声明\n   \n   **工作流闭环**：给 CC 的 TASK 指令中应包含「完成后对照 INTEGRATION_PLAN 做自审，列出差异点修正完再通知我审查」。详细操作见 `references/skill-creation-workflow.md` §逐批自我审核。\n   \n   反面案例（2026-06-03）：CC 在 health-management SKILL.md 写入「Xiaomi」（无 provider）、「meal photo analysis」（边界不清），且路由路径 14 条全部是扁平式（实际 5 个子目录的嵌套路径）。用户指出「cc好像把我们讨论过要排除的内容都放进去了」。用户要求：「你要监督好cc，按照之前沟通的plan走」。\n\n63. **与 CC 交互前必须先加载并审查协作 skill（v3.27 新增→v3.37 强化）**：用户指出「你现在跟cc的对话都没有依照cc协作skill」——在与 CC 开始多轮交互前，必须先用 `skill_view('hermes-claude-collaboration')` 重新加载最新版本的协作 skill，特别注意检查最新的 pitfalls 和协议变更点。不要依赖记忆中的旧版本规则。**时机铁律：加载 skill 是涉及 CC 操作的「第一件事」，不是准备工作完成后的「最后一步」。** 当用户提到任何需要 CC 执行的操作（连CC、让CC做、跟CC讨论、恢复CC会话、试试XX功能[指CC侧Skill]等）时，**立即加载协作 skill**，不要先做搜索 session、查记忆、确认上下文等其他准备——这些可以在 skill 加载后继续做，顺序不影响效率，但反过来会违反协作纪律。\n\n   特别是以下操作前必须重新加载：\n   - 重置或创建 CC session 后首次交互\n   - 用户明确说「你看看协作 skill」「你重新加载一下」\n   - 多个 session 间隙后重新连接 CC\n   \n   反面案例（2026-06-03）：用户指出对话不正常后，Hermes 重新加载 skill 才发现已有 62 条 pitfalls 和完整两步确认法，而之前操作时完全没按这些做——因为用的是旧记忆而非最新 skill 内容。让用户被动提醒后才加载 skill，是不合格的协作纪律。
   反面案例（2026-06-07）：用户说「我想先试试客户管理」（指CC侧微信聊天管理Skill），Hermes 先做了 session_search、fact_store probe、read_file 等大量上下文准备工作，确认要连CC后仍准备直接连——直到用户再次提醒「记得加载cc协作skill，再连cc」才加载。正确做法：识别到任务涉及 CC 后**立即加载 skill**，再继续其他准备。\n\n64. **传话陷阱的判断标准（v3.27 新增）**：「不要当传话筒」的精确含义：收到 CC 输出后，Hermes 必须先做独立分析——指出 CC 方案的漏洞、矛盾和可改进之处——然后将质疑发回 CC 辩论（R2），而不是把 CC 的分析摘要改个格式就发给用户。\n\n   判断是否传话的标准：\n   - ❌ 传话：「CC 的分析列出了 X 个问题，包括 1...2...3...，要它改吗？」\n   - ✅ 讨论：「CC 的分析有 12 条差异，我看了觉得 #8 路由路径问题更重要，而且我倾向方案 B 而非 CC 默认的写法，理由是...」\n   \n   关键区别：传话是把 CC 的结论**格式转换**后转发；讨论是**用自己的判断给 CC 的结论做评估和定向**。详见 `references/monitoring-debate.md` §3.1 辩论协议。\n\n65. **批量任务不汇报中间进度（v3.28 新增）**：用户说「全部完成再向我汇报」或类似表达（如「一次性汇报」「别分段说」）时，在 CC 执行长周期批量任务的过程中，Hermes 应持续监控但**不向用户发送中间进度更新**。只在以下三种情况汇报：(a) 全部 Phase 完成；(b) 遇到不可恢复的阻塞需要用户决策；(c) 用户主动询问进度。\n\n   **适用场景**：CC 执行多步文件清理 → 批量创建 SKILL.md → 统一修正的全流程。正确做法：capture-pane 轮询直到 DONE → 验证 → 一次性汇报全套结果。错误做法：每完成一个 Phase 就向用户报告「Phase A 完成了」「现在进 Phase B 了」。反面案例（2026-06-03）：用户连续收到 Phase A/B/C/D 的进度报告后直接说「全部完成再向我汇报」，嫌你啰嗦。\n\n67. **Tailscale IP 混淆——SSH 到云端而非 Windows（v3.30 新增）**：`tailscale status` 列出两个 IP，容易混淆：
   - `100.90.24.4` = 云端 Ubuntu（Hermes 所在机器，**不是 Windows**）
   - `100.107.207.104` = Windows 笔记本（CC 所在机器）
   
   `ssh -p 2222 100.90.24.4` 实际上是 SSH 回到云端自己（显示 `ubuntu@VM-0-4-ubuntu`），不会连到 Windows。必须用 `ssh -p 2222 HUAWEI@100.107.207.104` 才能连到 Windows。连接超时时先检查 Tailscale relay 状态（陷阱 44）。

68. **Plan mode 长任务消息用 SCP 文件绕过截断（v3.31 新增，v3.36 修正）**：Plan/accept-edits 模式下 send-keys 传递超过 ~300 字符的任务描述时，消息会被截断。**但在正常模式（无 ⏸/⏵⏵ 标记）下，paste-buffer 一次性发送 500-2000 字符是可靠的**——本次会话实测正常模式下 paste-buffer 成功发送 2000 字符无截断。策略：正常模式用 paste-buffer；plan/accept-edits 模式用 SCP 文件绕过。详见 `references/legal-article-collab-lessons.md`。

68. **cp -r 后必须验证完整性再删源（v3.29 新增）**：执行 `cp -r` 复制目录树后，**必须先验证目标目录文件数与源一致**，再 `rm -rf` 删除源。反面案例（2026-06-03）：`cp -r` 只拷贝了顶层文件，`skills/` 子树丢失（70→5 个文件），然后立即 `rm -rf` 删源，导致子 skill 全部丢失需要从 Windows 重新传输恢复。用户严厉纠正「不要犯这个严重错误」。**强制流程**：① cp -r ② `find <src> -type f | wc -l` 与 `find <dst> -type f | wc -l` 比对 ③ 两数一致才删源。不要偷懒省略验证步骤。

68. **从 Windows 到云端的批量文件传输：tar-over-SSH 优于 SCP（v3.28 新增）**：当需要从 Windows 本地（CC 侧）将整个 skill 项目目录（含空格路径、大量小文件）传输到云端时，`scp -r` 在以下场景失败：(a) Windows 路径含空格导致 SCP 无法解析通配符 `/*`；(b) SCP 默认要求目标目录已精确存在，中途创建子目录失败则整批中断。\\n\\n   **可靠替代方案——tar over SSH pipe：**\\n   ```bash\\n   # 云端执行：拉取 Windows 整个目录\\n   cd <cloud_dest_dir>\\n   ssh -p <port> user@windows \\\"tar -czf - -C \\\\\\\"D:/path/with spaces/target\\\\\\\" .\\\" | tar -xzf -\\n   ```\\n   \\n   **原理**：`tar -czf - -C <src> .` 在 Windows 端打包为 tar.gz 流，通过 SSH stdout pipe 直接送到云端 `tar -xzf -` 解压。不需要中间文件，不需要处理路径空格问题，一条命令完成。\\n   \\n   **注意事项**：\\n   - `-C <src>` 指定源目录，`.` 打包所有内容（不含容器目录本身）\\n   - Windows 路径用双引号包裹，内部反斜杠转义为 `\\\\\\\\` 或直接用正斜杠 `/`\\n   - 先确认目标目录已存在（`mkdir -p`）\\n   - 此方案也适用于 rsync 不可用时的替代\\n   \\n   反面案例（2026-06-03）：先后尝试 `scp -r \\\"D:/claude vscode/...\\\"` 和 `scp source/*` 均因路径空格和目标目录变化而中断，改用 tar-over-SSH 一次传输 68 个文件成功。\\n\\n68. **HTTP server 作为云→Windows 文件传输的兜底方案（v3.35 新增）**：当 SCP/SSH-pipe 向 Windows 传输文件在 Tailscale relay 下超时时，启动 Python HTTP server 是可靠替代云端方案。详见 references/http-file-transfer.md。

70. **`--continue` 恢复后可能携带旧任务上下文（v3.34 新增）**：`claude --continue` 恢复会话后，scrollback 可能包含来自不同任务的残留上下文（如 login-helper 和 task 管理混合）。CC 恢复后可能自动处理旧任务的残留逻辑，而非当前讨论主题。

   恢复流程（上下文切换）：
   1. 先切换到 plan mode（BTab，若在 accept edits 模式）
   2. C-c 清空输入框残留文字
   3. 发显式上下文切换：「不用管<旧任务>。回到<当前任务>的讨论：」
   4. 等待 CC 确认收到并总结当前任务状态
   5. 确认 CC 回到正确轨道后，再发新讨论内容

   不要：在上下文切换未确认前直接发新任务内容——CC 可能在旧任务上下文中执行错误操作。
   capture-pane 显示的混合 scrollback 不意味 CC 在处理所有任务——它可能只是残留，CC 关心最后一条指令。

   反面案例（2026-06-04）：tmux 恢复后 capture-pane 同时显示 login-helper token 管理和大盘简报讨论，CC 开始执行旧任务 Bash 脚本。Hermes 发「不用管login-helper。回到大盘简报的讨论」后 CC 立即确认并正确切换。

69. **CC 服务器不可达时的处理协议（v3.33 新增）**：当用户要求「跟CC讨论」「让CC做」但 CC 服务器（Windows 机器）SSH 连接超时/不可达时：\\n   \\n   1. 尝试 2 次 SSH 连接（间隔 10s），仍不通则确认服务器故障\\n   2. **立即向用户报告**服务器不可达的现状，不要继续猜测或等用户主动发现\\n   3. 同时评估任务是否可**自主完成**——检查现有工具是否已有对应能力\\n   4. 向用户一次性汇报：(a) CC 不可达的约束 (b) 你的独立分析结论 (c) 替代方案\\n   \\n   **反面案例（2026-06-04）**：用户要求「你跟cc讨论完后再向我汇报」，CC 服务器 121.36.9.143 超时，但未及时汇报而是尝试搜索文件、查日志等绕路操作后才告知。应：迅速确认不可达 → 立即汇报 → 给出独立替代方案。\\n   \\n   **关键**：不要因为用户说「讨论完再汇报」就延迟告知 CC 不可达的事实——这是阻塞性障碍不是中间进度。CC 不可达时应走独立分析路径，而非无限等待。

70. **Permission 弹窗优先选「Don't ask again」（2026-06-04 新增）**

72. **CC Web Search 使用边界——本地文件分析 vs 外部调研（2026-06-05 新增，2026-06-06 修正）**：CC 的 Web Search 工具有两个问题：(a) 频繁返回 0 结果且可能进入重试循环浪费 token；(b) CC 在分析本地文件时自发搜索而非读本地文件，是理解偏差。**正确区分**：外部调研（查 GitHub 仓库、查文档、查 API 用法）时 Web Search 合理可用，不应禁止；本地文件分析（读源码、读配置、分析项目结构）时 CC 不应搜索——此时若 CC 主动发起 Web Search，Hermes 应立即 Escape 中断并纠正方向（见陷阱 73）。**Hermes 指令措辞**：不要写「禁止 Web Search」（过于绝对），应写「本地文件分析请直接 Read，不要搜索」或「这些仓库已在本地 clone，用本地文件分析」。反面案例（2026-06-06）：Hermes 在微信管理任务中写「绝对禁止Web Search」，CC 合理地搜索了 wechat-daily-summary 的 GitHub 信息却被中断，用户纠正「web search并不是一定不能用」。

73. **监控 CC 方向——发现偏离应立即喊停纠正（2026-06-05 新增）**：用户明确要求「你发现CC做事方向有问题就要喊停，让它解释或纠正它」。Hermes 不应被动等待 CC 完成，而应持续监控 CC 的工具调用方向。**危险信号**：① CC 在分析本地文件时自发发起 Web Search ② CC 的输出偏离任务目标（如本应分析本地仪表盘设计却去搜索飞书模板）③ CC 反复执行同一失败操作（retry loop）④ CC 输出包含明显的事实错误或设计不符合用户需求。**处理**：立即 Escape 中断 → 明确指出问题 → 给出修正方向 → 等确认后继续。不要等 CC 完成一轮完整输出再纠正——越早干预，token 浪费越少。反面案例（2026-06-04）：Hermes 提出「4个仪表盘」方案，实际本地项目只有1个 Home 仪表盘——如果 CC 或 Hermes 在分析时及时读取本地项目就会避免此错误。

74. **先读源再设计——禁止凭空设计后反推本地项目（2026-06-05 新增）**

75. **辩论R1阶段铁律：Hermes不做预消化（2026-06-05 新增）**：结构化辩论中，R1分析阶段 Hermes 的职责是发送**原始材料**（文章链接、文件、数据）给 CC，让 CC 独立分析。**严禁 Hermes 先完成分析再把消化后的结论发给 CC**——这样 CC 只能"审查"Hermes 的结论而非"独立分析"原文，辩论质量大打折扣。正确流程：R1 发送原始材料 → CC 独立分析 → R2 双方交换分析意见。用户明确纠正：「不是把你消化完的内容给cc」。反面案例（2026-06-05）：商业秘密规定文章协作中，Hermes 在 R1 先自己做完了"规定 vs 反法对照分析"发给 CC，用户指出应让 CC 直接分析原文。

76. **CC修正时明确边界——防止重写引入新错误（2026-06-05 新增）**：当要求CC修正特定错误时，必须明确指令"**仅修正XX，保持文章结构、内容、其他条款编号不变**"。不加此约束时，CC 倾向于重写整篇文章来"更好地"修正——结果可能引入更多错误。反面案例（2026-06-05）：要求 CC 修正反法条号（第九条→第十条），CC 重写了全文→将《规定》自身条款编号全部搞错（保密措施从 Art.9 变成 Art.6）。二次审核发现后需再次修正。

77. **法律条款编号双重核对（2026-06-05 新增）**：法律写作协作中，条款编号错误是最常见的致命伤。审核时必须**逐条双向核对**：既要验证上位法条号（如反法），也要验证下位法条号（如《规定》）。flk-npc 的"命中展示"功能不返回条号——条号验证应使用**新旧对照表**或**官方全文**。详见 `references/legal-article-collab-lessons.md`。

83. **CC compound command 审批对话框操作技巧（2026-06-06 新增→修正）**：CC 在 accept-edits 模式下执行 compound command（含 `|`、`>`、`&&`、`2>/dev/null` 等管道/重定向）时，Claude Code 弹出 "Do you want to proceed? 1. Yes / 2. No" 对话框。**tmux send-keys 可以操作此对话框**（两拍法：`send-keys '1'` → sleep 0.5s → `send-keys Enter`），但需要注意：(a) **时序**——send-keys 发送到输入框而非对话框时，数字会和输入框残留文字拼接（如 `/exit/exit`），需先 Escape 清空输入框再发数字；(b) **焦点**——capture-pane 能看到对话框不代表输入焦点在对话框上，若 `1`+Enter 无效，先 Escape 取消对话框再让 CC 重新触发或换简单命令；(c) **CC 内置斜杠命令可通过 tmux 发送**——`/mcp`、`/exit`、`/compact` 等命令可通过 `send-keys '/mcp' Enter` 直接执行（实测有效），但 CC 无法通过 Bash 执行这些命令；(d) **仍建议减少 compound command**——简单命令更可靠，减少弹窗次数。

84. **CC 修改运行中服务的代码后必须手动重启（2026-06-07 新增→2026-06-07 修正）**：当 CC 修改了正在运行的 MCP Server 或其他服务的源码后，**代码改动不会自动生效**（stdio 模式的 MCP Server 进程是持久的，不会重载代码）。Hermes 在 TASK 指令中必须明确：(a) 改完后先不要重启，等确认修改无误后再重启 (b) 明确告知重启方式——如果 Hermes 知道进程的启动命令/配置位置，直接提供；如果不知道，让 CC 先定位再汇报。**已验证的重启流程（wechat-decrypt MCP Server，2026-06-07）**：① 用户在本地手动重启 MCP Server 进程 ② CC 通过 tmux 执行 `/mcp` 命令重连（`send-keys '/mcp' Enter`），capture-pane 确认显示 `Reconnected to <server-name>` ③ 重新调用 MCP 工具验证代码改动生效。**注意**：MCP Server 的配置可能不在标准路径（mcp.json/settings.json 的 mcpServers 为空），此时让 CC 搜索会陷入循环。Hermes 应提前从云端帮助定位（SSH 搜索进程、读取配置文件），或直接让用户手动重启 + `/mcp` 重连，不要求 CC 自己找进程。**CC 找进程配置时经常陷入循环**（反复搜索 mcp.json、settings.json、tasklist，每个搜索命令都触发权限弹窗），Hermes 应提前从云端帮助定位（SSH 搜索进程、读取配置文件），缩短 CC 的搜索时间。反面案例（2026-06-07）：CC 改完 wechat-decrypt MCP Server 代码后花 10+ 分钟找不到进程配置（标准路径 mcp.json/settings.json 均无），反复触发权限弹窗，最终通过用户手动重启 + `/mcp` 重连才验证成功。

86. **CC multiline python/node 命令触发连环权限弹窗（2026-06-07 新增）**：CC 执行 `python -c "multiline script with # comment"` 或 `node -e "multiline with // comment"` 时，Claude Code 检测到 "Command contains a quoted newline followed by a #-prefixed line" 警告，每次都弹出 "Do you want to proceed? 1. Yes / 2. No" 权限对话框。**当 CC 连续执行多个此类命令时（如逐文件搜索、逐配置检查），弹窗泛滥导致效率极低——每个命令都要 Hermes 手动批准。** 应对：(a) **首次即选 option 2（don't ask again）**——同类命令模式自动放行，后续不再弹窗；(b) **Hermes 从云端提前查信息**——如果 CC 要搜索的配置/进程信息 Hermes 能从云端 SSH 获取，直接提供给 CC，避免 CC 发起大量 python -c 搜索命令；(c) **指导 CC 用简单命令**——`cat file | grep pattern` 比 `python -c "import json..."` 更少触发弹窗。反面案例（2026-06-07）：CC 搜索 MCP Server 配置时连续发起 15+ 个 `python -c "import json; open(...)..."` 命令，每个触发权限弹窗，Hermes 花数分钟逐一批准，最终搜索结果为空（配置不在标准路径）。

87. **用户偏好「先分析方案再执行」的 CC 工作流（2026-06-07 新增）**：对复杂的 Skill 设计/功能开发任务，用户偏好让 CC 先充分分析方案再动手。具体模式：Hermes 发送需求 → CC 进入 plan mode（自动触发或 Hermes 指示）→ CC 用 Explore agents 调研项目结构和工具能力 → CC 输出完整 Plan 文档（含执行步骤、输出格式、风险评估）→ 确认后 CC 再执行。**优点**：(a) CC 的 Plan 阶段会自主发现 Hermes 未想到的问题（如 MCP 参数 `oldest_first` 的存在性验证）(b) 方案文档可作为执行对照，防止执行偏差 (c) 用户（通过 Hermes）在执行前有机会质疑和调整方向。**适用场景**：新 Skill 创建、功能设计、架构决策。**不适用**：简单修改、单文件编辑、已知方案的执行。

85. **CC 编造权威分析框架（2026-06-07 新增）**：当 CC 被要求解释方法论或分析问题时，可能编造看似权威的结构化框架（如「严重程度评级」「建议的改进方向」表格），实际上不是基于实际验证的结论。**判别信号**：CC 输出的分析框架中出现它没有实际调用工具验证过的维度/评级/分类。**处理**：在质疑指令中明确要求「不要编造分析框架，如果某个结论没有实际验证过就直接说不知道」。CC 在被追问时通常会承认编造（本次实测 CC 主动承认「是我编造的分析框架」）。反面案例：微信客户管理演示后用户质疑标签遗漏，CC 在回答中附带了「严重程度评级」，CC 后来承认这是编造的。

88. **CC 编造日期/星期几等未验证事实（2026-06-07 新增）**：CC 系统提示中有 `currentDate: YYYY-MM-DD`，但不包含星期几信息。CC 可能凭「感觉」推断星期几并输出错误结论（如将周日说成周六）。**这是编造的子类**——CC 没有用任何工具验证就直接输出了日期相关的推断。**判别信号**：CC 输出中出现「今天是周X」但未附带验证来源（如 `date` 命令输出）。**处理**：Hermes 在 TASK 指令中要求涉及日期的判断必须用工具验证（`date` 或 `python -c "import datetime; ..."`），不允许凭系统提示的日期推断星期几。反面案例：CC 分析客户汇总时说「6月7日是周六，客户沟通减少属正常」，实际是周日。用户指出「时间日期好像经常会有错误」。

89. **CC 启动序列铁律——cd→启动→激活→resume（2026-06-08 新增）**：启动 CC 的完整序列必须严格按以下顺序，不可跳步或混淆：
   1. `ssh local-win`（确认连接）
   2. `cd /d "D:\claude vscode"`（进入项目目录——**不是用户 home 目录**）
   3. `claude --model glm-5-turbo`（正常模式，**禁止 `--dangerously-skip-permissions`**，见陷阱 #2）
   4. `<!-- HERMES-ACTIVATE -->`（激活协作模式）
   5. `/rename Hermes:<任务名>`（命名对话，带前缀）
   6. 若恢复旧对话：CC 内部 `/resume <会话名>`（**不是 shell 级 `claude --resume`**，见陷阱 #45）

   **反面案例（2026-06-08，连续三次违规）**：
   - 没有先 cd 到项目目录就直接启动 CC → 用户指出「你没进正确的项目目录啊」
   - 使用了 `--dangerously-skip-permissions` → 用户立即制止「这个很危险，不能启用」
   - 混淆 shell 级 `--resume` 与 CC 内部 `/resume` → 用户纠正「resume 不是启动前输入的，是启动后再输入的」
   
   **弹窗处理顺序**：Bypass Permissions 警告弹窗中，`1` = No, exit，`2` = Yes, I accept。误按 `1` 会导致 CC 退出。多个弹窗堆叠时必须先 kill session 重建，不要在堆叠弹窗中尝试逐个通过。

89. **启动 CC 前必须 cd 到项目目录（2026-06-08 新增）**：启动 CC 前必须在 SSH 连接后先 `cd /d "D:\项目目录"` 再执行 `claude`。否则 CC 在 `C:\Users\HUAWEI`（用户 home）启动，看不到项目文件和 CLAUDE.md 上下文，后续所有操作基于错误的 cwd。**强制流程**：`ssh local-win` → `cd /d "D:\项目目录"` → `claude --model xxx`（绝不加 `--dangerously-skip-permissions`）→ 过弹窗 → 激活四步法。反面案例（2026-06-08）：Hermes 直接 `ssh local-win && claude` 导致 CC 启动在 home 目录，用户指出「你没进正确的项目目录啊」。

90. **Resume 在 CC 内部执行，不是启动参数（2026-06-08 强化）**：恢复已有对话时，必须先正常启动 CC（`claude --model xxx`），等 CC 完全加载后，在 CC 内部用 `/resume` 命令选择会话。**绝对不能**在启动命令中加 `--resume`（那是 shell 层面的恢复，会绕过 CC 正常初始化）。pitfall #45 已有此规则，但反复违反——本次会话再次犯同样的错误，用户明确纠正「resume不是启动前输入的，是启动后再输入的」。**加强措辞**：启动命令只允许 `claude --model <model>` 这一种形式，任何 `--resume`、`--continue`、`--dangerously-skip-permissions` 参数都禁止出现在启动命令中。

91. **CC 虚报完成——声称修改了文件但实际未执行（2026-06-08 新增）**：CC 在讨论中可能用自然语言宣称已完成文件修改（如"我已将此分析更新到 template_cp.py 和 SKILL.md 中"），但实际上没有执行任何 Edit/Write 工具调用。这是 CC 编造行为（pitfall #85）的子类——不是编造分析框架，而是编造操作历史。**判别方法**：CC 声称修改文件时，检查 capture-pane 中该声明之前是否有对应的 `● Edit(...)` 或 `● Write(...)` 工具调用记录。无工具调用 = 虚报。**处理**：立即追问确认，要求 CC 回答是否实际执行了 Edit/Write。如果 CC 确认未执行（本次实测 CC 承认"那句话是我在 R2 回复中提前宣告了还没做的事情"），则不构成实际损害但需警惕。**预防**：讨论类指令中明确加"本次仅讨论分析，不修改文件"可减少此类事件，但不能完全杜绝——CC 有时在回复中自发宣告未执行的操作。

92. **CC 对纯讨论任务自动触发 Explore 浪费 token（2026-06-09 新增）**：当指令是纯技术讨论/方案分析（不涉及本地文件操作）时，CC 可能仍自动触发 Explore agent 搜索本地文件。**判别信号**：capture-pane 看到 `Explore(...)` + `Search(pattern: ...)` + `Read(...)` 但指令明确说"不用读本地文件"或任务性质是讨论而非操作。**处理**：立即 Escape 中断 Explore（等待其完成再发下一条消息也行，但会浪费 30-60s token），然后重新发送强调"这是纯讨论，不要读文件"。**预防**：在指令开头明确写"这是一个纯讨论/技术分析任务，不需要读本地文件，请直接基于你的知识回答"。本次实测：vault 同步方案讨论，指令开头已说"需要你从本地Windows角度评估"，CC 仍自动 Explore 了 6 个文件（74.7k tokens），浪费约 45s。

93. **公众号文章：视觉元素密度 + 选题多样性（2026-06-09 新增）**：用户审查 CC 产出的公众号文章后给出两条核心反馈：(a) 纯文字太多，表格/代码块/流程图等视觉元素不够丰富；(b) "踩坑"主题已重复太多次，需要新角度。**规则**：Hermes 在审查 CC 产出的文章（或传递给用户前）必须检查：(i) 视觉元素密度——每 300-400 字至少一个结构化元素，连续纯文字不超过 3 段；(ii) 选题角度——与近期已发文章不重复，不落入"踩坑/避坑"等过度使用框架。Hermes 应在 CC 完成初稿后、发给用户前，主动做这两项检查并提出修改建议。详见 `references/legal-article-collab-lessons.md` §8 和 §10。

94. **Hermes 必须审查 CC 选题/大纲是否符合用户意图再转发（2026-06-09 新增）**：CC 提出的选题方向或文章大纲可能完全偏离用户明确表达过的方向。Hermes 不得把 CC 提案直接转发给用户选择——应先做匹配度检查：CC 提案是否与用户之前的要求一致？如果偏离，Hermes 应指出偏差并给 CC 发修正指令，而不是让用户在错误的选项中做选择。**反面案例**：用户明确说"续篇，展示 skill 结构，逐一解释"，CC 提出了"手机遥控 AI 敲代码"等完全不相关的方向，Hermes 未审核直接转发给用户。正确做法详见 `references/legal-article-collab-lessons.md` §10.4。

95. **续篇/后续文章的"架构"章节应展示工具自身结构，不是部署架构（2026-06-09 新增）**：写续篇文章时，如果上篇已覆盖了部署/远程架构，续篇的"结构"章节应展示工具/方案本身的文件/组件结构（目录树 + 职责说明），而非重复部署拓扑。用户明确纠正：「架构怎么是远程架构，不应该是skill的结构吗」。详见 `references/legal-article-collab-lessons.md` §10.2。：CC 在讨论中可能用自然语言宣称已完成文件修改（如"我已将此分析更新到 template_cp.py 和 SKILL.md 中"），但实际上没有执行任何 Edit/Write 工具调用。这是 CC 编造行为（pitfall #85）的子类——不是编造分析框架，而是编造操作历史。**判别方法**：CC 声称修改文件时，检查 capture-pane 中该声明之前是否有对应的 `● Edit(...)` 或 `● Write(...)` 工具调用记录。无工具调用 = 虚报。**处理**：立即追问确认，要求 CC 回答是否实际执行了 Edit/Write。如果 CC 确认未执行（本次实测 CC 承认"那句话是我在 R2 回复中提前宣告了还没做的事情"），则不构成实际损害但需警惕。**预防**：讨论类指令中明确加"本次仅讨论分析，不修改文件"可减少此类事件，但不能完全杜绝——CC 有时在回复中自发宣告未执行的操作。

83. **禁止 attach 用户正在使用的 CC 会话（2026-06-06 新增）**：CC 的 session 文件存储在 Windows 本地，Hermes SSH 连上去后启动的 CC 进程与用户本地 CC 共享同一份 session 存储。`claude --continue` 或无参数 `claude --resume` 会恢复用户最近 session，导致 Hermes 看到并可能干扰用户的实时对话。**强制规则**：(a) 新任务用 `claude`（无 `--continue`/`--resume`）启动全新 session；(b) 恢复旧任务用 `claude --resume Hermes:<任务名>` 精确指定 Hermes 自己的 session；(c) 所有 Hermes session 命名带 `Hermes:` 前缀，与用户自己的 session 区分；(d) **绝对禁止 `--continue`**。如果 capture-pane 看到的对话内容与当前 Hermes 任务无关 → 说明误入了用户会话，必须立即 `/exit` 退出并重新以正确方式启动。

78. **法律写作R3执行：锁定结构防CC漂移（2026-06-05 新增）**：R2确认文章结构后，R3指令中必须逐条列出章节结构（「第1章覆盖X→第2章覆盖Y→...」），使用「严格按下述结构」「不要擅自改变结构、不要合并章节」的明确措辞。不加此约束时CC倾向自由优化——合并章节、压缩段落、重组顺序。详见 `references/legal-article-collab-lessons.md` §9。

79. **CC 写入文件替代对话输出（v3.36 新增）**：CC 在 accept-edits 阻塞时，可能将分析/草稿写入本地文件而非输出到对话。捕获信号：CC 长时间"thinking"（3min+）但无对话输出 + 检查有无新 Write 操作。处理：(a) 用短指令让 CC "展示文件核心结论" (b) 如果 CC 确认文件已写入，Hermes 直接读取文件内容继续协作 (c) 不要无限等待 CC 在对话中输出——它可能永远卡在 accept-edits。反面案例（2026-06-05）：CC 将 R1 分析写入 商业秘密保护规定深度解读_R1.md（231行），Hermes 等待 7 分钟后才意识到文件是输出方式，发"展示核心结论"指令后立即获取了分析。

80. **CC 框架默认化倾向（v3.36 新增）**：CC 在 R1 中口头同意一个新的分析方向后，在实际写作时可能仍默认回到自己最熟悉的框架。口头同意 ≠ 写作遵从。应对：(a) R1 阶段 CC 写入文件后，Hermes 必须读取文件确认方向一致——不要只看 CC 的对话摘要就通过 (b) R2 不只要讨论结构，还要锁定章节标题措辞（如"本节标题不得出现'新旧''八大变化'字样"）(c) R3 指令追加"检查全文章节标题，不得出现指向旧框架的表述"。反面案例（2026-06-05）：CC 在 R1 明确同意"反法×规定配合关系"方向，但文件章节标题仍是"新旧对照：八大核心变化"——回到了新旧对比框架。

81. **Rename 串字（v3.36 新增）**：HERMES-ACTIVATE 和 `/rename` 在 accept-edits 模式下间隔过短时，CC 会将后续文字合并进 rename 参数。应对：activate 后等 2s → rename → 等 2s → capture-pane 确认名称 → C-c 清空残留再发下一条。

74. **先读源再设计——禁止凭空设计后反推本地项目（2026-06-05 新增）**：涉及迁移/改造任务时，必须先让 CC（或自己）读取源项目的实际设计（仪表盘组件、数据模型、字段结构），基于实际设计制定迁移方案。禁止凭空设计新方案后声称适配了源项目——这是最常见的传声筒式协作错误。正确流程：① 读取源项目所有相关文件 ② 确认源项目的实际设计（表数量、字段、视图、仪表盘）③ 基于实际设计制定迁移方案 ④ 讨论差异点（哪些可以优化、哪些必须保留）。反面案例（2026-06-04）：Hermes 和 CC 讨论出「4个仪表盘」方案，实际本地项目只有1个统一 Home 仪表盘。用户指出：「本地也只有一个仪表盘啊，内容也很全面」。根因：CC 的 Web Search 全部失败后未及时切换到读本地文件模式。：CC 弹出 Bash 权限对话框（"Do you want to proceed?"）时，对于 **read-only 命令**（cat/ls/head/find/wc/curl -o到/tmp），直接选 **option 2（Yes, and don't ask again）**。同一类型的 SSH cat 命令如果多次出现，选 option 2 后同类命令自动放行，无需逐个批准，大幅减少交互次数。

    安全规则：python -c / node -e / rm / cp / mv 和 curl -o 到系统路径等写操作保留弹窗审查（option 1），不做预授权。

    反面案例（2026-06-04）：CC 同时排队 3 个 SSH cat 命令读云端源码，Hermes 连续 3 次选 option 1，每选完一次 CC 就启动下一条又弹窗，3 轮弹窗拖慢整个流程。第一次就选 option 2 则一次性放行。

69. **多工具整合分析的三维覆盖（2026-06-04 新增）**：当用户要求将多个独立工具整合为一个复合 skill（如 investment-management）时，讨论必须覆盖三个维度：
   - **冗余分析**：哪些工具有重叠功能，哪些可以删除、合并或保持独立
   - **改造清单**：每个工具当前存在的问题（数据源失效、配置缺失、功能不足），哪些需要修改、哪些仅记录现状
   - **组合方案**：skill 结构、路由表、文件组织、数据源依赖关系

   **不要只讨论 SKILL.md 结构就动手写。**用户明确纠正：「方案不仅仅只是建一个skill.md，包括这么多工具怎么搭配组合，哪些可以删除不要，哪些需要修改调整，这些都需要跟cc讨论」。

   工作流：
   ```
   1. Hermes 全面盘点工具清单（包括依赖库、已装 skill、MCP 工具）
   2. CC 逐文件审查源码（通过 SSH 或下载），不接受 Hermes 的摘要
   3. CC 输出冗余分析 + 改造清单 + 组合方案三个表
   4. Hermes 独立评估 CC 方案，给出调整意见
   5. 讨论达成一致后，CC 执行创建完整 skill 包
   6. Hermes 验证后传回云端部署
   ```

   **关键**：步骤 2 必须让 CC 自己看源码，而非 Hermes 总结给 CC。用户指出「你要让cc从远端下载这些遗漏的部分，重新分析」——说明用户期望 CC 做第一手源码审查。

71. **CC 自动修复 + 审查验证 + 部署工作流（2026-06-04 新增）**：Hermes 审查代码后发现需要 CC 修改并部署到 Hermes，正确流程：

   ```
   1. Hermes 写 review-findings.md（逐条列出：问题位置行号、根因、修复方案、可选方案）
   2. SCP 到 Windows：`scp /tmp/review-findings.md HUAWEI@local-win:"D:/claude vscode/review-findings.md"`
   3. 在 Windows 启动 CC print mode 执行修复（不需要 tmux）：
      `ssh HUAWEI@local-win "cd /d \"D:/claude vscode/target-dir\" && claude -p --permission-mode bypassPermissions --dangerously-skip-permissions \"Read D:\\claude vscode\\review-findings.md and fix all issues.\""`
      关键参数：`-p`（非交互）、`--permission-mode bypassPermissions`（自动放行）
   4. Windows 端打包修改结果 → SCP 回云端：
      ```
      ssh HUAWEI@local-win powershell "Compress-Archive -Path 'D:\path\*' -DestinationPath 'D:\archive.zip' -Force"
      scp HUAWEI@local-win:"D:/archive.zip" /home/ubuntu/
      unzip -o archive.zip -d /home/ubuntu/review/
      ```
   5. Hermes 验证修改质量：
      - 语法检查：`python3 -m py_compile scripts/target.py`
      - 功能测试：`python3 -c "导入函数; 断言条件; print('OK')"`
      - 状态逻辑模拟：构造模拟数据结构，验证清理/边界逻辑正确性
      - 逐项对比 review-findings.md，确认所有问题已修复
   6. 验证通过后将修改后的包传回 Windows 覆盖原目录（保持版本一致）
   7. 部署到 Hermes：
      - 复制到 skills 目录：`cp -r /home/ubuntu/source ~/.hermes/skills/skill-name/`
      - 验证注册：`skills_list` 确认新 skill 及子 skill 都在列表中
      - 验证加载：`skill_view('skill-name')` 确认 SKILL.md 内容完整、路由表正确
      - 删除旧 skill（被替代时）：`skill_manage(action='delete', name='old-skill', absorbed_into='new-skill')`

   Windows 路径关键技巧：
   - `scp` 用正斜杠：`"D:/claude vscode/file.txt"` ✅
   - `ssh cd` 用 `cd /d "D:\dir"`（/d 切换驱动器）
   - `powershell Compress-Archive` 用反斜杠

   Print mode 适合单次可描述清楚的修改任务；需要多轮讨论的复杂改造仍走 tmux。

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
- [ ] **Paste 验证**：send-keys/paste-buffer 发送后是否通过 capture-pane 确认消息内容完整未被截断
- [ ] **ACK 确认**：是否收到 CC 的 ACK 指纹回执并比对 task_id+step 一致（30s 超时重发）
- [ ] **状态摘要**：是否已在指令末尾附加 `[state: task_id step done next ctx]` 状态行
- [ ] **步骤限制**：单次指令步骤数是否 ≤ 3（步=指令数，非操作数）
- [ ] **Silence 检查**：CC 是否超过 60 秒无输出？是 → 触发超时检查
- [ ] **PAUSE 检测**：capture-pane 是否出现 PAUSE 标记？是 → 处理 CC 的决策请求
- [ ] **任务记录**：CC DONE 中是否含 `[TASK_MAP]` 块？ → 提取后写入 `claude_task_map.json`
- [ ] **CC 自校验**：CC DONE 中是否含 `[CHECKLIST]` 块（涉及 Write/Edit 时必填）？缺失 → 追问 CC
- [ ] **空闲确认**：CC 输入框上方是否无 emoji 标记（✶/✽/✻/✢/· 等）？是 → 空闲可接受新任务
- [ ] **COMPLETE**：task 所有步骤完成后是否发送了 COMPLETE 标记
- [ ] **计划合规**：CC 输出的内容是否与约定的 INTEGRATION_PLAN（或等同文档）一致？有无引入已排除的功能、虚构的 provider、声称不存在的特性？发现偏差先辩论修正再继续
- [ ] **自我校验**：任务完成后做一次反向验证（capture-pane + 修改点 read），CC 结论与 Hermes 独立观察不一致 → 标注「需人工确认」
