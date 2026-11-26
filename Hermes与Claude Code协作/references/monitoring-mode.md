# 监控模式（长时蹲守 CC 会话）

> 触发条件：用户要求持续监控 CC 对话、观察 CC 执行过程、根据 CC 输出插入检索/分析任务。
> 本 reference 是 hermes-claude-collaboration skill 的按需补充——监控中所有 tmux 操作遵循主 SKILL.md 的基础协议。

## 概述

监控模式 = Hermes **不退出 turn**，持续轮询 CC 输出，发现问题时以**自言自语**形式汇报，识别用户插入的问题时以自言自语形式答复，用户明确停止后才结束监控。

核心场景：
- 用户在 CC 对话框中操作（打字、发指令），Hermes 在后台观察
- 用户要求 Hermes "看着 CC 执行"，发现问题及时指出
- CC 执行长任务（调研、批量处理），Hermes 持续跟踪进度
- 多任务穿插：监控中用户要求 Hermes 插入检索、阅读文件等子任务

### 🚫 禁止用后台进程替代同 turn 轮询（2026-06-29 新增）

监控模式的本质是 **Hermes 不退出 turn，在同一 turn 内循环 `terminal("sleep N && tmux capture-pane ...")`**。**绝对禁止**用以下方式"启动监控"：

1. `terminal(background=true)` + `watch_patterns` 启动独立后台 shell 脚本轮询
2. 任何形式的"先启动监控进程，再发指令"的两阶段模式

**错误示例**（2026-06-29 触发）：
```
terminal(background=true, command="bash /tmp/hermes-cc-monitor.sh", watch_patterns=["[📝]"])
```
用户纠正："不应该是同turn监控才对吗"——监控不是独立的前置步骤，而是发指令给 CC 的同一 turn 内就持续 capture-pane。

**正确模式**：
```
# 同一 turn 内：发指令 → 轮询 → 轮询 → 轮询 ...（不退出 turn）
tmux send-keys "指令内容" Enter
sleep 8 && tmux capture-pane ...    # 第1轮轮询
sleep 8 && tmux capture-pane ...    # 第2轮轮询
...                                 # 直到用户说停
```

**根因**：background process 把"监控"从"交互的一部分"异化为"独立服务"，导致 Hermes 退出 turn 等通知，违背了监控模式"不退出 turn"的核心约束。

### 🚫 杀掉后台脚本后仍不可退出 turn（2026-06-29 强化）

更隐蔽的错误模式：Hermes 杀掉了错误的后台脚本，口头解释了正确做法，**然后退出 turn 结束回复**——用户必须再发一条"继续监控"才真正启动轮询。

**错误三连击**（2026-06-29 重复触发 2 次）：
```
用户: "不应该是同turn监控才对吗"
Hermes: 杀后台 → 解释正确模式 → ❌ 退出 turn

用户: "你怎么又杀掉后台监控后就擅自结束了，同turn监控呢"
Hermes: 杀后台 → 再次解释 → ❌ 又退出 turn

用户: "继续监控"（第三次才真正执行）
```

**强制约束**：当用户纠正监控方式后，Hermes 必须**立即在同一 turn 内执行正确操作**（开始 capture-pane 轮询），而不是解释完正确做法就结束 turn。解释正确做法和实际执行正确做法是两件事，必须同时完成。

## 启动条件

用户明确表达以下任一意图时激活：
- "持续监控" / "帮我盯着" / "看看 CC 在干什么"
- "发现问题就自言自语" / "💭 形式汇报"
- "我在输入框里问 hermes 就回复"
- "不中断监控" / "继续监控" / "还在监控"

## 轮询策略

| 场景 | 轮询间隔 | capture-pane 参数 |
|------|---------|------------------|
| CC 正在处理（有 emoji/thinking 标记） | 20-30s | `-S -3`（看尾部几行即可） |
| CC 空闲等待用户输入 | 20-25s | `-S -3`（检测新输入） |
| CC 刚开始新操作（工具调用出现） | 30-45s（等工具执行） | `-S -5`（看工具输出） |
| 用户开始编辑输入框 | 10-15s（追编辑进度） | `-S -3`（看编辑内容变化） |
| 长时间无变化（>2min） | 45-60s（降低频率节省 token） | `-S -3` |

**关键原则：**
- 每次轮询都带 `sleep N &&` 前缀，不要连续无间隔 poll
- 每轮 poll 后输出一行状态（💭 标记 + 简要观察）
- CC 空闲时不反复报"空闲"——每 2-3 轮报一次"无变化。继续"即可
- **用户开始编辑输入框时加速轮询**，追编辑内容但不抢在发送前回复

### Auto-compact 预判

capture-pane 底部状态栏右侧显示 `X% until auto-compact`（context 使用率）。监控中应关注此数值：

| auto-compact 百分比 | 含义 | 监控动作 |
|-------------------|------|---------|
| < 70% | 正常 | 正常轮询 |
| 70-85% | 接近阈值 | 可在 💭 中标注：`💭 context 82%，CC 可能很快 compact。继续等：` |
| > 85% | 即将触发 | 标注 ⚠️：`⚠️ CC context 88%，即将 auto-compact。compact 后 CC 需回读文件恢复上下文，期间会有短暂输出中断。` |
| compact 已触发 | CC 输出中出现 compact 相关信息 | 跟踪 CC 回读的文件数量，预期完成时间 |

**注意：auto-compact 百分比属于区域③，不影响空闲判断。不要因为百分比高就认为 CC 忙碌。**

## 自言自语格式

所有监控中的汇报统一使用 emoji 前缀，**不直接回复用户**：

| 前缀 | 含义 | 使用场景 |
|------|------|---------|
| 💭 | 一般观察/状态更新 | CC 开始新任务、输出新内容、状态变化 |
| ⚠️ | 发现问题/异常/质疑 | CC 卡住、Web Search 返回 0、输出可疑、token 异常 |
| 📋 | 独立分析/对比/补充 | CC 给出结论后 Hermes 的独立判断、调研补充 |

**格式模板：**
```
💭 CC 正在读取 5 个文件恢复上下文（compact 后）。继续等：
⚠️ CC 4 个 Web Search 全 0（已知问题），可能需要喂材料。继续等：
📋 我的独立质疑：CC 说"X 是弱项"——实际上 Y 才是真正的原因。理由：...
💭 你开始输入了——"你能帮我..."。还在编辑中，继续等：
```

**自言自语规则：**
1. **不中断 turn**——所有 💭/⚠️/📋 后面紧跟下一次 poll 的工具调用，不等待用户回复
2. **发现问题立即标注**——不攒到一起汇报，发现就标
3. **独立质疑必须有依据**——⚠️ 和 📋 不能凭感觉，必须基于事实（已观察到的输出、已验证的数据）
4. **不替 CC 做决策**——发现 CC 可能走错方向时标注 ⚠️，但不主动发指令纠正（除非用户要求或 CC 明确卡住）

## 用户信号识别

### 直接提问信号（用户在 CC 输入框中 @ Hermes）
- 包含 "询问hermes" / "问hermes" / "hermes" 字样
- 或 CC 收到的指令中包含要求 CC 转询 Hermes 的内容

**响应方式：**
- 以 💭 或 📋 前缀回复（不切换到直接回复模式）
- 回复内容后继续轮询，不退出监控
- 如果需要执行工具调用（web_search、web_extract 等），执行后继续轮询
- **注意**：CC 无法主动联系 Hermes，当用户在 CC 输入框中说"询问hermes"时，Hermes（监控中）应主动响应，而不是等待 CC 转达——CC 没有转发能力

### 中途任务插入信号——立即并行执行，不可只 acknowledge（2026-06-28 强化）

- 用户单独发给 Hermes 的消息（不经 CC）
- 如"你也一起调研一下"、"帮我搜一下 X"、"读一下 Y 文件"

**响应方式（强制三步）：**
1. **立即在 turn 内执行**——用 Hermes 自身工具（web_search/web_extract/terminal 等），不能只 acknowledge 后继续 passively poll
2. 以 💭 或 📋 前缀输出结果
3. 完成后立即恢复轮询

**默认行为规则（2026-06-28 新增，见 pitfall #148/#149）：**
- "调研/搜索/查一下"不带限定词 → **默认 web_search/web_extract**（网络调研）
- "看一下 XX 文件" → **委派给 CC Read**（本地文件，见 #97a）
- **不在 CC tmux session 内创建新 window**——所有 Hermes 侧操作用 Hermes 自身工具（见 #149）

**反面案例（2026-06-28）**：
- 用户说「你也调研一下仪表盘方案」，Hermes 只 acknowledge 后继续 poll CC，没有实际执行搜索。用户纠正「你没有遵守协议，我发的问题是让你监控的同时操作」
- 另一次 Hermes 尝试 SSH 到 Windows 读本地文件做调研，用户纠正「是让你网络调研，不是本地」
- Hermes 在 CC 的 tmux session 里创建了 hermes-research window，用户发现后纠正「你把cc的tmux窗口弄乱了」

### 停止监控信号

**🚨 严禁自行结束监控（2026-06-28 用户纠正）**

监控模式的退出条件**只有用户明确表达**。以下情况**不算**停止信号：
- CC 空闲等待输入 → 继续轮询
- CC 完成了某一步任务 → 继续监控下一步
- CC 弹出 plan 确认/执行界面 → 继续观察
- 轮询多轮无变化 → 降低频率但**不退出**
- max_turns 接近上限 → 输出分段汇报后**等用户说「继续监控」**，不要直接结束

**只有以下才算停止信号：**
- 用户明确说"停止监控" / "不用监控了" / "可以了" / "退出监控"
- 用户发出了与监控无关的**新独立问题**（表示注意力完全转移）
- 用户直接跟 CC 对话说"不用盯着了"

**反面案例（2026-06-28）**：Hermes 在 CC 完成辩论、进入 plan 确认阶段后，回复了审核结论并自行结束 turn 等用户。用户纠正「不要擅自结束监控」——即使 CC 当前没有需要 Hermes 介入的操作，监控也应持续直到用户明确停止。

## Token 预算管理

监控模式是 token 大户（每次 poll 消耗一次工具调用）。管理策略：

| 预算阶段 | max_turns 剩余 | 策略 |
|---------|---------------|------|
| 充裕 | > 50 | 正常轮询（20-30s） |
| 警戒 | 30-50 | 降低频率（30-45s），减少状态更新文字 |
| 紧张 | 15-30 | 仅轮询关键事件（工具调用完成、弹窗出现），减少 💭 输出 |
| 临界 | < 15 | **必须输出汇报总结 + 建议用新 session 继续**，不可耗尽 |

**重要：** 如果监控被 max_turns 截断（如遇到 "maximum number of tool-calling iterations" 错误），下一条回复应包含监控状态总结，以便用户知道截断前看到了什么。

### 分段汇报策略

当 max_turns 接近上限或轮询时间过长时，应主动分段：

```
💭 监控汇报（第一段）：
- CC 完成了 X 任务
- 正在处理 Y
- 当前状态：Z

（第一段汇报结束，下一 turn 继续监控。如需继续请说"继续监控"。）
```

这样用户可以选择：①继续监控（新 session 继承上下文）②提问 ③做其他事

## 常见场景处理

### CC Web Search 全 0
```
⚠️ CC Web Search 全 0 结果（X 个查询均失败，已知问题）。CC 可能 fallback 到 webReader 或本地分析。继续等：
```
如果 CC 进入重试循环（同一搜索重复 3+ 次）：
```
⚠️ CC Web Search 重试循环（第 4 次搜索仍 0 结果）。这是已知问题，CC 不会自动停止。如需要 Hermes 中断并喂材料，请说"中断CC并喂材料"。
```

### CC 长时间 thinking 无输出
```
💭 CC token 停在 Xk 不动，已 Y 分钟。可能在 deep thinking。继续等：
```
超过 5 分钟无变化：
```
⚠️ CC 可能卡住（X 分钟 token 不动）。建议检查：① CC 是否在等外部资源 ② SSH 是否断连 ③ 是否陷入死循环
```

### CC 完成 compact
```
💭 CC compact 完成，正在回读文件恢复上下文（已读取 X 个文件）。继续等：
```

### CC 输出值得质疑的结论
```
📋 CC 给出结论：X。我的独立质疑：Y。理由：① Z1 ② Z2。等你继续操作。
```
注意：不主动发辩论给 CC（除非用户要求），仅标注质疑供用户参考。

### ⚠️ 「询问hermes」信号——严禁切出监控模式（2026-06-27 用户纠正）

> **这是监控模式中最容易被违反的规则，已多次触发。**

用户在 CC 输入框中输入「询问hermes」/「问hermes」时，CC **无法直接联系 Hermes**（没有跨 agent 通信能力）。Hermes 看到这个信号后应主动响应，但**必须在监控格式内响应**：

| 正确 ✅ | 错误 ❌ |
|---------|---------|
| 以 `💭` 或 `📋` 前缀回复 | 以正常对话格式直接回复（无 emoji 前缀） |
| 回复后立即继续轮询 | 等用户回应或结束 turn |
| turn 内完成 | 退出监控模式进入对话模式 |

**错误根因**：Hermes 看到「询问hermes」后下意识切换为「被呼叫 → 回答」的正常对话模式，忘了自己仍处于监控 turn 中。

**强制自检**：每次识别到「询问hermes」信号后，在组织回复前默念：**我还在监控 turn 中 → 用 💭 前缀 → 回复后继续 poll**。此规则已写入 pitfalls.md #134 和 monitoring-mode.md §用户信号识别，三处冗余提醒仍有违反风险——说明需要更强的行为约束。

### CC 执行中途被用户打断
```
💭 你发了"..."给 CC，CC 已接收。继续观察 CC 处理：
```

### CC Explore agent 启动——Hermes 应主动并行搜索（2026-06-27 新增）

当监控中观察到 CC 启动 Explore agent（capture-pane 出现 `Explore(...)` + `WebSearch(...)` 调用）时：

1. **立即在 turn 内发起并行 web_search**——覆盖 CC 正在搜索的主题，以 📋 格式输出结果。原因：CC 的 Web Search 在大陆网络大概率全 0（见 pitfalls #140），Hermes 是唯一可靠的外部搜索通道。
2. **观察 Explore agent 的 token 增长**：如果 token 停滞 >2 分钟（capture-pane 底部状态栏 token 数不变），说明 Web Search 全 0 在重试循环中。
3. **评估是否建议中断**：Explore 持续 >5 分钟且无有效产出时，用 ⚠️ 标注建议用户 Escape 中断。

```
⚠️ CC 启动 Explore agent 搜索"xxx"。已知 Web Search 大概率全 0，我先并行搜索覆盖。
📋 [Hermes 搜索结果]...
💭 CC Explore 仍在搜索（Xm，token 停滞），可能在 fallback 到 webReader。继续等：
```

### 监控中处理 CC Bash 弹窗（2026-06-28 新增，2026-06-29 强化）

当 CC 在执行过程中触发权限确认弹窗（`Do you want to proceed? 1. Yes / 2. No`）时，Hermes **默认自动处理**，无需用户逐次授权。

1. **capture-pane 确认弹窗内容**——看具体是什么命令触发的弹窗
2. **自动按 Yes 的场景**（无需汇报）：
   - read-only 命令（ls、cat、find、grep、wc、head、tail 等）
   - git 操作（git add、git commit、git push、git pull、git checkout 等）
   - 测试脚本运行（pytest、npm test、node test 等）
   - 构建命令（npm build、tsc、cargo build 等）
   - 文件读取/写入（Read、Write 工具调用——CC 工具弹窗）
   - 任何非破坏性、非不可逆的操作
3. **必须汇报用户的场景**（暂停轮询，💭 标注弹窗内容等用户决策）：
   - 删除/破坏性操作（rm -rf、rmdir、git clean、git reset --hard）
   - Python/Node 直接执行代码块（python -c、node -e）——无法预审内容
   - 网络请求/外部命令（curl、wget、scp、ssh 到非本地机器）
   - 任何涉及用户可能想了解或反对的操作
4. **处理流程**：capture-pane → 判断安全级别 → 安全则 `send-keys '1' Enter` + capture-pane 验证 → 继续轮询；敏感则 💭 汇报 → 等用户回复
5. **每次处理前确认选项编号**——参考 pitfalls #83 的心算验证规则（Yes 对应编号可能是 1 也可能是 y，看弹窗实际选项）

**注意**：弹窗处理属于监控职责的一部分，处理完毕后立即继续轮询，不退出监控 turn。用户可能同时处理多件事，Hermes 帮忙处理常规弹窗避免 CC 被阻塞等待。

**⚠️ accept edits 模式下的弹窗拦截陷阱（2026-06-29 新增）**：当 capture-pane 同时看到 Bash 确认弹窗（`Do you want to proceed? 1. Yes / 2. No`）和底部状态栏 `accept edits on (shift+tab to cycle)` 时，**两拍法（#29 的 `send-keys '1'` → sleep → `send-keys Enter`）的 Enter 会被 accept edits 模式拦截**，数字键可能已选中但 Enter 不生效。Escape 会**取消** Bash 命令而非退出 accept edits（下次需重新触发命令）。**正确流程**：
1. 先发 `BTab`（Shift+Tab）切换到 plan mode（`⏸ plan mode on`）——退出 accept edits 但不取消 Bash 弹窗
2. 再用两拍法：`send-keys '1'` → sleep 0.5s → `send-keys Enter`
3. capture-pane 验证弹窗消失 + CC 继续执行
4. 如仍无效，杀 session 重建（最快恢复路径，见 pitfall #42 核弹选项）

**反面案例（2026-06-29）**：Hermes 连续尝试 3 次 `send-keys '1' Enter` 均无效，后用 Escape 取消了 Bash 命令，需重新发指令让 CC 触发命令。

### 监控中直接向 CC 发送消息——tmux send-keys（2026-06-27 新增）

当用户要求 Hermes「跟 CC 讨论」或用户自己与 CC 讨论时要求 Hermes 介入，Hermes 可通过 `tmux send-keys` 直接向 CC 发送消息（无需用户手动粘贴转发）：

**发送方式（accept edits / plan mode）：**
```
tmux send-keys -t claude-session "消息内容"    # 发送
tmux send-keys -t claude-session Enter           # 确认发送
tmux capture-pane -t claude-session -p -S -3     # 验证送达
```

**规则：**
- 每条消息 ≤ 300 字符（短 send-keys，不拆分多段）
- 发送后必须 capture-pane 验证消息出现在 CC 输入框中
- CC 处理前必须确认空闲（无 emoji 标记）——不是必须，但建议等 CC 空闲再发
- 消息内容应自包含（含背景 + 理由），见 pitfalls #38

**长消息绕过：** 超过 300 字符的消息，写入云端文件 → SCP 到 Windows → 短 send-keys 让 CC 读取文件（见 pitfalls #68）。

**适用场景：**
- 用户说「你也跟 CC 讨论」→ Hermes 直接发消息给 CC
- CC 输出需要 Hermes 独立审核后发回质疑（辩论模式 R2）
- CC 需要 Hermes 侧的信息（搜索结果、文件内容等）

### 监控轮询间隔上限——弹窗出现后必须及时发现（2026-07-05 新增）

**问题**：轮询间隔过长（60-120s）导致 CC 弹窗（权限确认、Bash 确认等）出现后 Hermes 长时间未处理，CC 处于等待状态。用户说「你怎么会没有发现弹窗」。

**规则**：监控模式下的轮询间隔不得超过以下上限：

| 场景 | 最大轮询间隔 | 理由 |
|------|------------|------|
| CC 正在执行工具调用（有 emoji/thinking） | **30s** | 工具可能在数秒内完成并弹出确认框 |
| CC 刚完成一轮输出（emoji 消失→无 emoji） | **15s** | 完成后可能立即弹出新弹窗（plan 确认、满意度调查等） |
| CC 空闲等待用户输入（长时间无变化） | **60s** | 唯一可拉长间隔的场景 |

**关键**：`sleep 60 && capture-pane` 或 `sleep 90 && capture-pane` 在 CC 活跃执行期间**绝对不可接受**——CC 的工具调用可能在 10-30s 内完成并弹出确认框，轮询间隔 60-90s 意味着弹窗最多等 90s 才被处理。

**反面案例（2026-07-05）**：PM 迁移监控中 Hermes 使用 60-120s 轮询间隔，CC 的 Bash 权限弹窗出现后 Hermes 需要等 60-90s 才发现并处理。用户纠正。

### CC 满意度调查弹窗——「How is Claude doing?」（2026-06-29 新增）

**现象**：CC v2.1.72 在每个 thinking 周期结束后可能弹出满意度调查：

```
● How is Claude doing this session? (optional)
  1: Bad    2: Fine   3: Good   0: Dismiss
```

**处理方式**：
- `0`（Dismiss）是正确选项——不评分、不参与、直接跳过
- **但 `0` 会被 CC 误处理为用户消息**：`send-keys '0' Enter` 后，CC 可能解释 `0` 的含义（如写成 "○" 或说「好的，其他项目不动」），然后显示下一条用户消息 `> 0` 作为输入——即 dismiss 输入变成了 CC 对话中的内容
- 这是 CC 自身的行为限制，不是 Hermes 的配置问题

**负面影响**：
- `0` 作为 dismiss 输入被 CC 作为用户消息处理会触发「Interrupted — What should Claude do instead?」，打断 CC 当前操作
- 可能造成连续循环：Hermes dismiss（`0` + Enter）→ CC 处理 `0` 作为消息 → 再次弹出调查 → 再次 dismiss

**策略**：
1. **不主动 dismiss**：如果 CC 处于空闲等待用户输入状态，且调查弹窗不会阻塞后续操作，可以忽略不处理——CC 不会因为弹窗未回复而卡住
2. **仅当弹窗确实阻塞操作时才处理**（如 CC 正在 `Waiting…` 等待输入才能继续）
3. **处理时用 Escape 而非 `0`**：Escape 取消弹窗效果等同于 Dismiss，且不会被 CC 当作消息内容。`tmux send-keys -t claude-session Escape`
4. **Escape 无效时的兜底**：`tmux send-keys -t claude-session '0' Enter`——接受 `0` 被当作消息的副作用（CC 会说「好的」并重新等待），然后等 CC 再次空闲后直接跳过

**根因**：CC 的 satisfaction survey 是独立的 UI 弹窗，不是 Chat 类型的交互（如 Bash 确认弹窗），`0` 既是 dismiss 的选项编号，也是一个有效的文本字符。当前版本（v2.1.72）将 dismiss 按键同时解释为消息内容。等待 CC 后续版本修复此行为。

### CC 错误恢复循环检测——「换工具不换假设」（2026-06-29 新增）

当 CC 遇到 FileNotFoundError 或类似错误后，陷入**同一错误路径上反复换工具重试**的循环时（如用 `os.listdir` 失败 → 换 `cmd dir` → 换 `ls` → 全指向同一错误路径），Hermes 应识别此模式：

```
⚠️ CC 错误恢复循环：连续 N 次在同一错误路径「X」上换工具重试（已用：tool1, tool2, tool3）。
   这是「换工具不换假设」模式——CC 没有质疑路径本身是否正确。
   如果 CC 5 分钟内未自行突破，建议你考虑 Escape 中断或发指令让其 ls 父目录验证。
```

**干预阈值**：
- 3 次同类错误 → 💭 标注观察，不干预（CC 通常能自纠正）
- 5 次 / 3 分钟 → ⚠️ 标注并提醒用户（CC 可能无法自行突破）
- 超过 5 分钟仍在循环 → 建议用户 Escape 中断

**根因**：CC 的默认错误恢复策略是"换一种方式重试同一假设"，而非"质疑假设本身"。CC 已在 `general-pitfalls.md` 中新增硬规则（FileNotFoundError 第一步 ls 父目录），未来应减少此类循环。

### CC interview 被拒——「想从哪个角度澄清」是正常行为（2026-06-27 新增）

用户拒绝 CC 的 interview Tool use 后，CC 会确定性地说「想先听你的想法。你想从哪个角度澄清？」——**这不是异常，不需要 ⚠️ 标注或干预**。用户拒绝 interview 是想提供自由格式输入，CC 会自然等待。静默观察即可，不干预用户与 CC 的 interview 交互节奏。详见 pitfalls #141。
