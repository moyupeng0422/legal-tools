# Common Pitfalls (完整集)

> SKILL.md 仅保留约 20 条核心高频条目，完整条目按原编号排列于此。
> 
> ## 编号规则

> - **原始编号保留**：本文件保留 SKILL.md 中的原始编号（0–133），不重新编号，避免引用断链。
> - **同号异义**：原始编号有重复且内容不同（如 #54 Playwright headed vs 非 ASCII 路径），按 a/b 后缀区分（如 #54a、#54b）。
> - **同号同义**：原始编号重复但内容相同（如多次 copy-paste），合并为一条，取最完整版本。
> - **已知断号**：#58、#63-#67、#82、#98、#124（编号体系已乱，实际使用未受影响，不补齐）。

## 重复编号处理记录

  - #1（×2，内容不同，已用 a/b 后缀区分）
  - #27（×2，内容不同，已用 a/b 后缀区分）
  - #54（×2，内容不同，已用 a/b 后缀区分）
  - #68（×3，内容不同，已用 a/b 后缀区分）
  - #70（×2，内容不同，已用 a/b 后缀区分）
  - #69（×2，内容不同，已用 a/b 后缀区分）
  - #74（×2，内容相同，已合并）
  - #89（×2，内容不同，已用 a/b 后缀区分）
  - #97（×2，内容不同，已用 a/b 后缀区分）

## Table of Contents（按类别分组）

- **启动序列/session 管理**: #3, #5, #8, #32, #41, #47, #48, #49, #50, #54, #89, #89a, #90, #110, #111, #112, #113, #118, #119, #123, #138
- **弹窗/权限处理**: #2, #6, #9, #12, #27, #29, #42, #55, #70a, #83, #86, #108, #128, #130
- **消息发送/截断**: #9, #13, #24, #30, #42, #68, #68b, #99, #119
- **协议标记**: #18, #24, #69, #126
- **传话/辩论**: #10, #26, #75, #78, #92, #126, #131, #132
- **监控/超时**: #7, #73, #102, #105, #107, #108
- **编码/Windows 环境**: #8, #54, #55, #68b, #97, #97a
- **CC 工具行为**: #1a, #72, #92, #110, #111, #122, #135, #136, #137
- **写作协作**: #77, #78, #93, #95, #120
- **批量任务/context**: #68b, #100, #101, #104, #107, #114, #115, #116, #118, #121
- **SSH/网络**: #28, #44, #54, #55, #68b, #97, #97a, #106
- **代码审查**: #35, #55, #84, #103
- **其他**: #0, #1, #4, #11, #14, #15, #16, #17, #19, #20, #21, #22, #23, #25, #27a, #31, #33, #34, #36, #37, #38, #39, #40, #43, #45, #46, #51, #52, #53, #54a, #56, #57, #59, #60, #61, #62, #68a, #69a, #70, #71, #74, #76, #79, #80, #81, #85, #87, #88, #91, #94, #96, #109, #117, #125, #127, #129, #133

## 全部 Pitfalls（按原编号顺序）

### #0. 加载 skill 后未遵守其规则（2026-06-03 新增）

0. **加载 skill 后未遵守其规则（2026-06-03 新增）**：加载了协作 skill 但继续用默认沟通方式与 CC 交互——不发状态摘要、不做两步空闲确认、消息内容不按协议格式。用户指出「你现在跟cc的对话都没有依照cc协作skill，我看到好多对话都不完整」。根因：skill_view 读取了协议内容但未在后续工具调用中严格遵守。**强制约束**：加载协作 skill 后发送第一条消息前，必须通过 checklist 确认：状态摘要 [state:...] 有吗？两步确认（-S -20 → 3s → -S -10）做了吗？单条消息 ≤300 字符吗（plan mode）？三条缺一不可。

### #1. 把 Hermes 专属偏好强加给 CC（2026-06-24 新增） _（同号变体之一）_

1. **把 Hermes 专属偏好强加给 CC（2026-06-24 新增）**：用户对 Hermes 的偏好（如「全部做完再汇报」「无需我介入」）仅约束 Hermes 自身，不得作为指令传达给 CC/芭迪/传令员。CC 有自己的交互模式（弹窗确认、plan 阶段询问用户），Hermes 不应干预。反面案例：Hermes 发送「请全程执行不中断，5个阶段全部完成后统一汇报，不要中间停顿问我」给 CC——这是越权操作。

### #1a. CC Web Search is broken + retry loop _（同号变体之一）_

1. **CC Web Search is broken + retry loop** — CC web searches frequently return 0 results (`Did 0 searches in Xs`). Worse, CC may enter a **retry loop**, repeating the same failed queries 4-6 times. **Hermes must (a)** do all web searches itself and **(b)** interrupt CC (Escape) when detecting retry loops, then supply pre-researched content via SCP file (`scp task.txt → CC reads file`). Never rely on CC to self-search. The SCP pre-research pattern is documented in Research Workflow §Pre-research workflow.

### #2. 禁止 `--dangerously-skip-permissions`

2. **禁止 `--dangerously-skip-permissions`**：使用正常模式 + `settings.local.json` 预授权安全操作

### #3. Session 命名

3. **Session 命名**：始终用 `claude-session`（唯一），通过 `claude_task_map.json` 映射多任务，不要创建 `cc-{task}` 多 session

### #4. Print Mode 的适用范围（v3.36 修正）

4. **Print Mode 的适用范围（v3.36 修正）**：Print mode (`-p`) 适用于**一次性任务**——单次读取、分析、修改后退出，不需要上下文连续性。特别适用于自动修复（见陷阱 71）。**不适用于**多步骤交互任务（多轮辩论、分步执行、需要`--resume`跨轮次的任务），这些场景必须用 tmux 交互式 session。这是对 v3.0 本 skill 自身矛盾的修正——正文 Print Mode 节已正确描述适用范围，pitfall #4 的"禁止"是过时的 blanket 限制。**判断标准**：单次消息能完整描述且一轮对话可完成 → 用 print mode；需要发 2+ 条指令、等待中间结果、辩论 → 用 tmux。

### #5. 恢复用 `--resume <Hermes任务名>`，禁止 `--continue`（2026-06-06 修正）

5. **恢复用 `--resume <Hermes任务名>`，禁止 `--continue`（2026-06-06 修正）**：CC 的 session 存储在 Windows 本地 `~/.claude/`，`--continue` 会恢复最近 session（即用户本地正在使用的对话），导致 Hermes 看到并干扰用户的实时对话。Hermes 必须始终：(a) 新任务用 `claude` 启动全新 session，然后 `/rename Hermes:<任务名>`（带前缀避免与用户 session 冲突）；(b) 恢复旧任务用 `claude --resume Hermes:<任务名>` 精确指定。**绝对禁止 `--continue` 和无参数 `--resume`。**

### #6. 弹窗盲按风险

6. **弹窗盲按风险**：权限弹窗不要一律 `y`，需审查操作内容；Trust 弹窗可以盲按 Enter

### #7. 监控超时 ≠ CC 完成

7. **监控超时 ≠ CC 完成**：连续 3 次相同输出可能是 CC 卡住而非完成，需判断 pane 状态

### #8. tmux 在云端，不在 Windows

8. **tmux 在云端，不在 Windows**：所有 `tmux` 命令由 Hermes 在云端直接执行，不需要 SSH 到本地再跑 tmux。SSH 连接在 tmux session 内部，通向 Windows cmd。架构图见 Overview。

### #9. accept edits 阻塞

9. **accept edits 阻塞**：capture-pane 看到 `⏵⏵ accept edits on` 时，paste-buffer 发送的长消息可能只收到最后一行（CC 只解析了最后一段文本）。处理优先级：
   1. `BTab`（Shift+Tab）→ 切换到 `⏸ plan mode on`，此模式下短 send-keys 正常工作。
   2. `Escape` → `Enter` → 尝试退出 accept edits 回到正常模式
   3. **scp 文件绕过**：将长内容 scp 到 Windows（如 `<windows-userhome>/msg.txt`），用短 send-keys 让 CC `读取 <windows-userhome>\msg.txt`。绕过 paste-buffer 截断问题
   4. **最后手段**：`/exit` → 重新 `claude` 启动 → 再 paste-buffer。短 send-keys 不受 accept edits 影响，可用来发退出指令

### #10. 传话陷阱

10. **传话陷阱**：与 CC 协作时，Hermes 必须用自己的判断逐条分析 CC 输出（同意/反驳/修正），给出独立结论。按主题归纳 CC 建议后转述仍被视为传话——用户期望独立思考后再汇报，而非切换格式转发。收到 CC 方案后第一反应必须是「这个方案有没有问题？」而非「CC 说了 X，你怎么看？」。详见 monitoring-debate.md §3.1。

### #11. 勿假设密钥未配置

11. **勿假设密钥未配置**：用户问"怎么连上 XX"时，先检查 `authorized_keys` 和 `~/.ssh/config` 是否已有配置，不要上来就生成新密钥对。用户可能早已配好，只需给出最终命令（如 `ssh ubuntu@<cloud-tailscale-ip> -p <ssh-port>`）。

### #12. CC 弹窗导航不可靠——数字键不一定移动 `>` 光标（v3.10 修正→v3.50 同步详细版）

12. **CC 弹窗导航不可靠——数字键不一定移动 `>` 光标（v3.10 修正→v3.50 同步详细版）**：CC 的权限弹窗和 interview 表单导航并不可靠——按数字键后 `>` 光标**不一定移动到对应选项**。实测多次出现按 `2` + Enter 但 `>` 仍停在 option 1（弹窗未通过）。**正确流程**：① 按数字键或 Tab/Down 导航 ② **立即 capture-pane 验证 `>` 位置**（`>` 必须出现在目标选项行首）③ 确认移动后才按 Enter。若 `>` 未移动：补发 Down 直到 `>` 到位 → 再 Enter。**两拍法仍有效**（数字/Down 与 Enter 分开发送，间隔 ≥ 300ms），但增加了第②步验证。未生效时切勿重复按数字键+Enter（会重复排队），应 Ctrl+C 取消 → 等空闲 → 重发。注意 option 1 是默认选中时直接 Enter 即可通过。Tab 可以切换选项描述文本（如 "Yes, and tell Claude what to do next" ↔ "Yes"），但不移动 `>` 光标。

### #13. Plan mode 下 paste-buffer 不可靠

13. **Plan mode 下 paste-buffer 不可靠**：plan mode（`⏸ plan mode on`）和 accept-edits 模式一样，paste-buffer 可能只收到消息开头几个字（多次会话实测：~600 字消息只收到片段）。**可靠替代：分段短 send-keys**，每条 <300 字符，间隔 1-2s，总共不超过 10 条。长内容写云端文件 → scp 到 Windows → 让 CC `读取 <文件路径>`。最可靠方案：多段短 send-keys 逐条发送。

### #14. 双轨规则放置

14. **双轨规则放置**：本 skill 的核心行为规则（不传话、质疑优先、独立核实）已同步嵌入 SOUL.md（每轮自动加载）。Skill 提供详细操作协议，SOUL.md 提供简化版常驻提醒。新增关键行为规则时，先放入 SOUL.md 确保持续生效，再在本 skill 补充操作细节。仅放 skill 中容易被遗忘——skill 需主动加载，Agent 在快速响应时经常跳过。

### #15. 过度规划

15. **过度规划**：单次 paste-buffer 指令不应超过 **3 个步骤**（步 = Hermes 指令数，非操作数）。CC 上下文窗口在处理长指令时可能丢失中间步骤细节，导致执行偏差。超过 3 步的任务必须拆分发送，每步完成后确认再发下一步。

### #16. 沉默执行

16. **沉默执行**：CC 执行中发现异常（工具失败、文件不存在）并输出了错误信息，但 Hermes 的 capture-pane 未及时捕获到响应，误判任务完成。轮询间隔不得超过 **30 秒**，CC 超过 **60 秒**无输出必须触发超时检查。

### #17. 并发冲突

17. **并发冲突**：CC 仍在处理上一个任务时（emoji 标记/工具调用中），不要发送新指令。先等空闲确认，再发下一轮。**例外**：测试并发行为时允许有意违反——但必须明确标注是测试，且事后回归正常纪律。

### #18. task_map 漏记

18. **task_map 漏记**：每次 `/rename` 后必须**立即**更新 `claude_task_map.json`，不要等任务完成后再补——到那时上下文已被压缩，记录必然丢失。本 skill 自身在 v3.0 测试中连续漏记 5+ 条任务，是反面教材。

### #19. 恢复不对等

19. **恢复不对等**：CC 有崩溃恢复流程，但 Hermes 自身卡住/超时时没有对等机制。如果 Hermes 超过 2 分钟未响应 CC 的 DONE 信号，应视为异常并进入诊断。

### #20. 发送确认机制

20. **发送确认机制**：每次 paste-buffer 或 send-keys 后，必须确认消息完整送达。A) capture-pane -S -10 肉眼检查内容完整；B) 等待 CC 的 ACK 指纹回执（task_id + step 比对），30s 超时重发。仅依赖 paste-buffer 返回值（永远返回成功）是假象——内容可能截断但无法检测。

### #21. CC 侧上下文文件

21. **CC 侧上下文文件**：一次性部署 `.claude/rules/hermes-collab.md` 到 CC 本地。`.claude/rules/*.md` 属于 CC 的 `project` 设置源，自动随 session 加载，不依赖 CLAUDE.md 显式 `@` 引用。但如果项目 `CLAUDE.md` 已引用其他 rules 文件，应同步添加 `@.claude/rules/hermes-collab.md` 保持一致性（人类和 AI 工具的可发现性）。部署后 CC 能主动识别协作状态、理解结构化消息格式、执行行为守则。详见 `references/cc-context-file.md`。

### #22. v3.0 修订方案

22. **v3.0 修订方案**：2026-06-01 Hermes × CC 双向诊断讨论产出的完整修订方案，见云端文件 `~/.hermes/cc-integrated-plan.md`（311行）。含结构化消息协议（TASK/ACK/DONE/ERROR/PING/DISPUTE）、双向心跳、CC 行为守则（5条强制+3条引导）、降级规则、优先级排序（P0-P3）。该文件是 v3.0 修订的权威参考。

### #23. PING 不可由 CC 实现

23. **PING 不可由 CC 实现**：LLM 是请求-响应模式，无时钟/定时器/后台能力，无法在空闲期主动发送消息。CC context 文件（v3.1）已移除全部 PING 条款。监控超时职责完全归 Hermes 侧：60s 无 DONE/HERMES 标记 → 主动 capture-pane 检查 CC 状态 → 重发指令或汇报用户。

### #24. DONE 标记在 capture-pane 中可能被滚动截断

24. **DONE 标记在 capture-pane 中可能被滚动截断**：多行输出中 `<!-- DONE:task:step -->` 起始标记可能被 pane 缓冲滚动到不可见区域，导致误判 STATUS 裸出。核实方法：捕获时用 `-S -60` 或更大回滚行数；若 STATUS 块完整但未见 DONE，加大 capture-pane 回滚幅度后再确认。

### #25. 先补规则再执行

25. **先补规则再执行**：CC 协作中发现协议缺口（如 CC 不知道自己不能写云端文件）时，先暂停任务，补上规则（双方 context 文件），再继续。不要在规则残缺的状态下推进——缺规则的协作必然出错。

### #26. 假辩论 ≠ 真辩论

26. **假辩论 ≠ 真辩论**：收到 CC 方案后写一段独立评价再汇报用户，这不构成辩论。辩论必须是双向的——把质疑发回 CC，让 CC 回应，你再评估回应，R1→R2→R3 的轮次才算辩论。独立分析是辩论的**起点**，不是终点。独立分析后应：① 列出具体质疑 → ② 发回 CC 做 R2 质询 → ③ CC 回应后评估修正 → ④ 可能再追问 R2b/R2c → ⑤ 最终结论汇报用户。缺了 ②~④ 就是假辩论。**2026-06-02 两次触发：** 路由边界讨论和 tmux 优化讨论，均修正了 CC 的错误假设。核心教训：独立分析后若未发回 CC 质询就直接汇报用户，不管分析多深入，都是传声筒。

### #27. CC interview 表单禁止裸转发（v3.16 新增） _（同号变体之一）_

27. **CC interview 表单禁止裸转发（v3.16 新增）**：CC plan mode 的 interview 表单（`Enter to select`、`↑/↓ to navigate`）列出选项时，**绝对禁止**把选项列表直接转发给用户问"你看选哪个"。这是最赤裸的传声筒——用户期望的是 Hermes 先做独立分析，判断每个选项的优劣，给出推荐理由，然后才让用户拍板。**2026-06-03 触发**：CC 询问 DOM 选择器方案（选项 1/2/3），Hermes 转发选项列表问用户，用户立即指出「不要当传话筒」。正确做法：独立分析 → 指出选项的利弊/可行性 → 给出明确推荐 → 附简要理由 → 然后让用户确认。如果某个选项涉及技术事实不确定（如需要 CC 自查），先把质疑发回 CC 澄清，澄清后再汇报用户。

### #27a. Hermes 侧就近处理违规 _（同号变体之一）_

27. **Hermes 侧就近处理违规**：就近处理铁律是双向的。CC 提议「我帮你写一份完整的 XX 文件，可以直接粘贴到配置里」→ Hermes 不应接受。云端文件始终由 Hermes 自己写入，CC 只产出内容建议（对话中讨论即可）。处理方式：CC 若越界提议写云端文件 → 立即 C-c 取消 → 明确告诉 CC「这个文件在云端，应该 Hermes 来写，你产出规则内容到对话中即可」。

### #28. SSH 断连后 capture-pane 陷阱

28. **SSH 断连后 capture-pane 陷阱**：SSH 断开后 tmux session 回退到本地 bash，但 scrollback 中残留大量 CC 旧输出（方案、表格、提示符），致使 capture-pane 看起来 CC 还活着。判别方法：`tail -1` 看最后一行是不是 `$ ` 或 `>` —— 是 bash 则 SSH 已断，是 `>` 带 emoji 标记则 CC 运行中。恢复流程：先 `ssh -o ConnectTimeout=10 <ssh-alias> "echo OK"` 确认 SSH 通 → tmux 内重新 `ssh <ssh-alias>` → 进入 CC 工作目录 → `claude --continue` 恢复。切勿在断连的 session 内直接发 `<!-- HERMES-ACTIVATE -->`——bash 会把 `!` 当历史扩展报错。

### #29. CC 弹窗统一用两拍法

29. **CC 弹窗统一用两拍法**：不仅是 interview 表单（数字 1-6 选择），权限对话框（"Do you want to proceed? > 1. Yes / 2. No"）同样要用两拍法：`send-keys '数字'` → sleep 0.5s → `send-keys Enter`。单次 `send-keys '1' Enter` 可能被 CC 忽略。Trust 弹窗（仅信任确认，无选项）可以盲按 Enter。选择后务必 capture-pane 验证是否生效——未生效则 Escape 取消后重试。

### #30. Plan mode 多段 send-keys 截断

30. **Plan mode 多段 send-keys 截断**：Plan mode（`⏸`）下 CC 的输入框可能只捕获第一段消息，后续分段被丢弃——即使间隔 1-2s、每条 <300 字符也未必全部收到。可靠方案：① 将长内容 scp 到 Windows 后让 CC `读取 <文件路径>`；② 或在同一条 send-keys 中发送完整消息（不拆分）。拆分发送后必须 capture-pane 肉眼确认所有分段都被 CC 收到。

### #31. 真实 CC vs delegate_task 子代理

31. **真实 CC vs delegate_task 子代理**：`delegate_task` 是在云端本机 spawn 的 LLM 子代理，**不是** Windows 上的真实 Claude Code。当用户说"让 CC 做"时，必须通过 tmux → SSH → Windows CC 通道。只有在 SSH 不可用或任务不需要 Windows 本地文件操作时，才考虑子代理模拟。判断依据：CC 是否能通过 tmux 连通（`ssh <ssh-alias> echo OK`）——能则用真实 CC，不能则汇报用户重建连接。

### #32. `claude --continue` / `/resume` 恢复失败（Cannot read properties of null）

32. **`claude --continue` / `/resume` 恢复失败（Cannot read properties of null）**：SSH 断连后 `--continue` 或 CC 内 `/resume <name>` 可能报 `Cannot read properties of null (reading 'split')`，说明会话状态文件损坏。此时直接 `claude` 启动新会话即可，不丢失之前的会话文件——在新会话中可通过 `/resume <name>` 尝试恢复（新会话的状态文件干净）。

### #33. DISCUSS 优先于自动建议（用户强制规则）

33. **DISCUSS 优先于自动建议（用户强制规则）**：CC 在 `⏵⏵ accept edits on` 模式下生成的自动建议（如 `> 开始写 P1 代码`、`> 先验证...`），CC 会**优先执行自动建议**而忽略排队的 `[HERMES:DISCUSS]` 消息。**处理：capture-pane 看到 CC 执行工具调用（● Bash/Read 等），同时有 DISCUSS 排队（`Press up to edit queued messages`）→ 立即 `C-c` 打断。DISCUSS 已在队列中，打断后 CC 会自动处理下一条消息即 DISCUSS，无需重发。** 不打断则 CC 在错误方向浪费数分钟 token。用户明确要求（2026-06-02）：「以后遇到这种情况就先打断CC，让它先处理讨论，不然执行方向会有问题」。

### #34. Hermes 不得擅自修改 CC 输出中的配置值

34. **Hermes 不得擅自修改 CC 输出中的配置值**：修改 CC 脚本中的 BASE_URL、model、API key 等配置值前，必须用事实验证（查官方文档、settings.json、实际测试），不能在无依据的情况下凭记忆修改。

### #35. CC 代码的第一版输出需要逐行审查

35. **CC 代码的第一版输出需要逐行审查**：CC 频繁在同一类问题上出错——(a) 环境变量名混淆（ANTHROPIC_API_KEY vs ANTHROPIC_AUTH_TOKEN）(b) 协议字段结构假设错误（扁平解析 vs 嵌套解析）(c) 平台路径假设（Linux <cloud-home> 当 Windows cwd）(d) 非有效参数（mode 传给不接受它的方法）(e) ACP 方法名错误（messages/create vs session/prompt）。Hermes 应预期 CC 的第一版代码包含此类错误，逐行审查后再执行，不要只看概要描述就通过。

### #36. 空闲判断铁律（v3.8 新增）

36. **空闲判断铁律（v3.8 新增）**：CC pane 有三个独立区域——①输入框上方（emoji 标记 ✶/✽/✻/✢/· 等，有=thinking，无=空闲）；②输入框（`>` 提示符）；③底部状态栏（左侧=UI 模式，右侧=X% until auto-compact）。**空闲只看区域①，不看区域③。** accept edits、plan mode、normal mode 只是 UI 模式，只要有 emoji 标记就不是空闲，没有就是空闲。accept edits 模式下的限制是发送方式（用短 send-keys 不用 paste-buffer），不是不可发送。不要混淆"发送方式受限"和"不可发送"。**区域③右侧的 auto-compact 百分比不用于空闲判断，但监控中应关注——接近阈值（~90%）时 CC 即将自动压缩上下文。**

### #37. CC 自动推荐 vs 用户输入（v3.8 新增）

37. **CC 自动推荐 vs 用户输入（v3.8 新增）**：capture-pane 中 `>` 开头的行可能是 CC 自动推荐内容（如 `> 开始写 P1 代码`），不是用户输入。区分方法：自动推荐前通常有 CC 的思考输出，且内容以 CC 的口吻描述下一步操作。真正的用户输入不会出现在 capture-pane 的 CC 输出区。

### #38. 指令应自包含上下文 + rationale（v3.8 新增）

38. **指令应自包含上下文 + rationale（v3.8 新增）**：Hermes 发送指令时，不应依赖 CC 看不到的上下文。每条指令应包含关键背景信息 + 操作理由（rationale），让 CC 能在没有历史对话的情况下理解任务背景。反面：依赖"按照上次的方案继续"而 CC 看不到"上次的方案"。正面：`修改 database.ts 的连接超时从 30s 到 60s。原因：远端 API 响应变慢导致频繁超时。`

### #39. 预授权范围（v3.8 新增）

39. **预授权范围（v3.8 新增）**：仅预授权 `Bash(git *):allow`（git 操作有 reflog 兜底，可追溯）。python/node/cp/mv 全部保留弹窗——python -c/node -e 可执行任意代码，cp/mv 可移动任意文件，风险过高。不在协作链路的远程 agent 场景下预授权这些命令。

### #40. Skill 更新后必须重新加载（v3.9 新增）

40. **Skill 更新后必须重新加载（v3.9 新增）**：用户说"调整过 XX skill 了"时，必须先 `skill_view` 重新读取最新内容，再按新规则操作。不能在旧版本记忆基础上继续——用户调整往往是对之前协作问题的修正（如 v3.8 的两步确认法、消息长度指纹），不重新加载等于无视修正。**反面案例（2026-06-02）**：用户更新协作 skill 后，Hermes 仍用旧的单次 `-S -5` 判空闲导致并发冲突，用户直接指出需重新读取。

### #41. `/clear` 后的重激活（v3.9 新增）

41. **`/clear` 后的重激活（v3.9 新增）**：CC 执行 `/clear` 后对话完全清空。Hermes 侧需重新执行完整激活流程：① `<!-- HERMES-ACTIVATE -->` 重新激活协作模式 ② `/rename <任务名>` 命名新对话 ③ 写入 `claude_task_map.json`。不能用 `/clear` 前的激活状态和对话名称。两步确认法在此场景尤为重要——scrollback 中残留的 `✻ Cooked for Xs` 等旧 thinking 标记需与当前状态（`> ` + 无新 emoji）区分。

### #42. accept edits 模式可能完全阻塞所有 send-keys（v3.10 新增→v3.42 修正→v3.43 新增预防）

42. **accept edits 模式可能完全阻塞所有 send-keys（v3.10 新增→v3.42 修正→v3.43 新增预防）**：实测发现 accept edits 模式下不仅是 paste-buffer 被截断，**所有 send-keys 都可能被 CC 吞掉**——包括 BTab、Escape、C-c、/exit、普通短消息。pane 看起来有 `>` 提示符处于空闲，实际完全不响应。

   **⚠️ 区分两种行为模式（2026-06-10 新增）**：
   - **延迟排队**（更常见）：send-keys 不是被吞，而是排队延迟送达——可能延迟 30s~数分钟后才出现在输入框中。判别信号：CC 当前正 busy（有 emoji/thinking 标记）时发的 send-keys 会在 CC 空闲后逐条出现。**处理**：不要重复发送同一指令（会导致重复排队），耐心等待 CC 完成当前操作后再检查输入框。
   - **完全阻塞**（少见但严重）：CC 空闲但仍不响应任何输入。判别信号：连续 3 次 send-keys 后 capture-pane 无任何变化（输入框无回显、状态栏不变）→ 确认为阻塞。**推荐恢复路径（按优先级）**：1. **核弹选项（最快最可靠）**：直接 `tmux kill-session -t claude-session` 杀掉整个 tmux session → `tmux new-session -d -s claude-session -x 200 -y 60` 重建 → SSH → cd → `claude --model glm-5.2` → 激活四步法。用户明确建议：「直接杀了tmux重进就行了」——比在阻塞 session 中尝试各种恢复命令快得多。2. 轻度尝试：C-c 暴力连发 3 次 → 等 1s → Escape → Enter。3. SSH 断连检查：`ssh -o ConnectTimeout=10 <ssh-alias> echo OK`。SSH 断 + accept edits 阻塞 是双重故障模式，需先恢复 SSH 再处理 CC。**注意：accept edits 并非总是完全阻塞——见陷阱 43。**

_（v3.43 新增预防段落：见相关 pitfall 的预防措施）_


> 详见 references/active-discussion-protocol.md —— 活跃讨论中的每轮协议纪律，补充任务边界协议未覆盖的轮次交互规范。

### #43. 用户明确要求：两步确认法不可跳过（v3.10 新增）

43. **用户明确要求：两步确认法不可跳过（v3.10 新增）**：用户指出「你有在好好确认cc的状态吗」——Hermes 在执行 CC 前置检查时存在偷懒跳过两步确认的趋势。**强制规则**：每次与 CC 交互前，两步确认（capture-pane -S -20 → 等 3s → capture-pane -S -10）是必须的，不允许用单次 `-S -5` 替代。特别在以下高风险场景更不可跳过：(a) 刚完成上一任务后的首次检查 (b) accept edits 模式下的检查 (c) 长时间未监控后的恢复检查。

### #44. Tailscale relay 假活（v3.11 新增→v3.46 补充）

44. **Tailscale relay 假活（v3.11 新增→v3.46 补充）**：tailscale status 显示 active relay hkg 但 tailscale ping 全部超时——relay 连接卡死但状态未更新。判别：tailscale status 的 rx 字段长时间不变（如 rx 92016 持续数分钟）→ relay 已死。**诊断方向优先级**：SSH 超时时，**先检查云端 Tailscale 状态**（历史多次案例均为云端侧问题），不要先假设本地 Windows 有问题。检查顺序：① `tailscale status` 看 rx 是否停滞 ② `ping <windows-tailscale-ip>` 测试连通 ③ 云端 `sudo tailscale down && sleep 3 && sudo tailscale up`（注意：down 后需等 10-15s 让 up 完全重建连接，期间 status 可能短暂显示 `-`）④ 如果云端 status 显示 `-` 但 ping 已通，说明 relay 刚建立、状态显示延迟，可直接尝试 SSH。修复：先在 Windows 端 Disconnect → Connect（通常无效），终极大招是云端 `sudo tailscale down && sleep 3 && sudo tailscale up`→ 重建 relay 连接。与 SSH 断连的关联：Tailscale relay 假活 → SSH 超时 → tmux 内 CC 进程退出 → capture-pane 显示旧 scrollback（陷阱 28）。需先修复 Tailscale，再走 SSH 重连流程。

### #45. CC 已运行时的对话切换命令（v3.12 新增）

45. **CC 已运行时的对话切换命令（v3.12 新增）**：CC 已在 tmux 中运行时，切换对话用 CC 内部命令 `/resume <会话名>`，不是 shell 命令 `claude --resume`。后者用于从 bash 启动 CC 时指定目标会话——在 CC 内部执行 `claude --resume` 会退出当前 CC 再开一个新的 CC 进程，且可能因状态文件冲突报错。判断方法：capture-pane 看到 `> `（CC 提示符）→ 用 `/resume`；看到 `$ ` 或 `>`（bash 提示符）→ 用 `claude --resume` 启动。

### #46. 会话名大小写敏感（v3.12 新增）

46. **会话名大小写敏感（v3.12 新增）**：CC 的会话名严格区分大小写。法信mcp ≠ 法信MCP——用错大小写会导致 Session xxx was not found。不确定准确名称时，先发 `/resume`（不带参数）让 CC 列出可用会话。

### #47. `/rename` 后输入框残留（v3.13 新增）

47. **`/rename` 后输入框残留（v3.13 新增）**：`/rename 任务名` 执行后，输入框可能残留 `/rename 任务名` 文本。在发下一条指令前，必须 capture-pane 确认输入框干净（只显示 `> `），否则 CC 会把 rename 命令文本也当输入执行。**强制步骤**：rename → 等 2s → capture-pane -S -3 → 看到输入框有残留文字 → Escape 清空 → 再 capture-pane 确认干净 → 然后才能发下一条指令。

### #48. 新会话激活四步法（v3.13 新增）

48. **新会话激活四步法（v3.13 新增）**：CC 新会话启动后，必须严格按顺序执行：① `<!-- HERMES-ACTIVATE -->` ② `/rename 任务名` ③ 写入 `claude_task_map.json` ④ 才能发送 TASK。跳步会导致 task 无法正确追踪。此序列是 CC 协作的基础骨架，不可省略任何一步。每个步骤之间需 capture-pane 确认完成（激活确认协作模式消息、rename 确认 Session renamed、task_map 确认写入成功）。反面案例（2026-06-03）：启动 CC 后直接发 TASK 漏掉 rename，用户指出"你还没rename"。

### #49. CronCreate session-only 生命周期（v3.14 新增）

49. **CronCreate session-only 生命周期（v3.14 新增）**：CC 的 CronCreate 创建的 cron job 仅在当前 CC session 存活，session 结束后自动清理（上限 3 天）。这意味着：① 监控类 cron 需要在 CC 会话保持期间才有效 ② session 结束（`/exit`、崩溃、SSH 断连导致 CC 退出）后所有 cron 自动消失 ③ 长期监控需要 Hermes 侧 cron 替代。本 session 创建的 token 监控 cron（1db945fb）即受此限制。恢复方法：CC 重启后重新创建 cron。

### #50. Gateway 重启 → tmux 全死 + sidecar 全死（v3.15 新增→v3.41 扩展）

50. **Gateway 重启 → tmux 全死 + sidecar 全死（v3.15 新增→v3.41 扩展）**：任何 profile 的 Gateway 重启（包括 `/* 重启 */` 指令或手动 `systemctl restart` 触发）会杀死 tmux server（作为 Gateway 子进程）+ sidecar（hermes_feishu_card runner，作为 Gateway cgroup 子进程）。后果：tmux session `claude-session` 消失、SSH 连接断开、CC 进程退出、CC cron 全部丢失、**飞书流式卡片停止工作**（sidecar 被 kill 后新 gateway 不自动拉起）。

### #51. Plan mode 下 Escape 可能无法清空输入框残留文字（v3.16 新增）

51. **Plan mode 下 Escape 可能无法清空输入框残留文字（v3.16 新增）**：plan mode 下 CC 输入框有残留文字（来自历史交互或自动建议）时，多次按 Escape 可能显示 "Esc again to clear" 但文字始终不清。**解决方案**：发一次 `C-c` 即可清空输入框（只按一次，不要连按两次——第二次会真正退出 CC）。注意与 accept edits 阻塞（陷阱 42）区分：plan mode 下 C-c 一次通常可靠清空；accept edits 下可能需暴力连发。实测案例（2026-06-03）：输入框残留 `用 rmfyalk_search 检索...` 文字，Escape ×3 + "Esc again to clear" 三次均无效，C-c 一次立即清空。

### #52. 禁止把 CC 的 UI 界面原封不动抛给用户（v3.17 新增）

52. **禁止把 CC 的 UI 界面原封不动抛给用户（v3.17 新增）**：CC 的 interview 表单（数字选项 1-6）、plan 审批对话框（"Would you like to proceed?"）、选项列表等，是 CC 与 Hermes 之间的交互界面，**不是给用户看的**。Hermes 必须先独立分析选项、形成自己的判断，再以自己的语言向用户汇报结论和建议——绝不直接 dump CC 的 UI 文字。反面案例（2026-06-03）：CC 弹出 DOM 选择器 interview 表单（6 个选项），Hermes 直接截图描述给用户，被用户纠正「不要当传话筒」。正确做法：分析各选项优劣 → 形成推荐 → 用自己的话汇报 → 确认后自行操作 CC 表单。即使用户需要做决策，也应呈现为 Hermes 的分析框架（"我建议选 2，原因：..."），而非 CC 的原始选项列表。

### #53. CC 本地项目开发需记录过程到 `claude.local`（v3.18 新增）

53. **CC 本地项目开发需记录过程到 `claude.local`（v3.18 新增）**：当 CC 在本地 Windows 上进行具体项目开发（代码修改、bug 修复、功能开发）时，必须在任务完成时将开发过程摘要写入项目根目录的 `claude.local` 文件。内容包括：改了哪些文件、修复了哪些 bug、新增了哪些功能、遇到的坑及解决方案。**Hermes 在发送 TASK 指令时必须明确告知 CC 此要求**（如附加「完成后将开发过程记录到项目的 claude.local」）。此文件作为项目级开发日志持久化，跨越 CC session 不丢失，便于后续 session 快速了解项目历史变更。反面案例（2026-06-03）：CC 完成 login-helper keepalive 功能开发、修复了中文路径和编码 2 个 bug，但未记录到项目中——下次新 session 需要从头理解项目状态。

### #54. SSH 启动的 Playwright headed 浏览器无法在 Windows 桌面显示窗口（v3.19 新增） _（同号变体之一）_

54. **SSH 启动的 Playwright headed 浏览器无法在 Windows 桌面显示窗口（v3.19 新增）**：通过 SSH → tmux → Windows 链路启动的 Playwright `headless=False` 浏览器，Edge 进程能正常启动和导航，但 `MainWindowHandle` 始终为 0——窗口在 SSH session 的不可见上下文中，不会出现在用户桌面。这不是代码 bug，是 Windows session 隔离机制。**判别方法**：`powershell -Command "Get-Process msedge \| Select-Object MainWindowHandle"`——全部为 0 即确认。**解决方案**：CDP（Chrome DevTools Protocol）。用户在 Windows 桌面手动启动 Edge 并开启调试端口（`msedge --remote-debugging-port=9222`），login-helper 通过 CDP 连接到已有浏览器实例操控保活和提取。详见 `references/cdp-browser-approach.md`。反面案例（2026-06-03）：反复排查 BROWSER_DATA_DIR 路径、lockfile、Playwright 版本均无法解决，最终确认是 SSH 环境限制而非代码问题。：当 CC 在本地 Windows 上进行具体项目开发（代码修改、bug 修复、功能开发）时，必须在任务完成时将开发过程摘要写入项目根目录的 `claude.local` 文件。内容包括：改了哪些文件、修复了哪些 bug、新增了哪些功能、遇到的坑及解决方案。**Hermes 在发送 TASK 指令时必须明确告知 CC 此要求**（如附加「完成后将开发过程记录到项目的 claude.local」）。此文件作为项目级开发日志持久化，跨越 CC session 不丢失，便于后续 session 快速了解项目历史变更。反面案例（2026-06-03）：CC 完成 login-helper keepalive 功能开发、修复了中文路径和编码 2 个 bug，但未记录到项目中——下次新 session 需要从头理解项目状态。

### #54a. Playwright/Edge 路径避免非 ASCII 字符（v3.19 新增） _（同号变体之一）_

54. **Playwright/Edge 路径避免非 ASCII 字符（v3.19 新增）**：Windows 上 Playwright 使用 Edge 时，`launch_persistent_context()` 的 `user_data_dir` 参数若包含中文路径，Edge 会以 exitCode=21 启动失败（无明确错误提示）。根因是 Chromium 系浏览器对非 ASCII 路径的兼容问题。**修法**：将 browser_data 目录放到纯 ASCII 路径下，如 `%TEMP%/login-helper-browser_data`。反面案例（2026-06-03）：login-helper 的 `BROWSER_DATA_DIR` 原指向含中文的 `<windows-project-root>\法律相关skill自研仓库\...`，Edge 反复 exitCode=21 无法启动，改为 `%TEMP%` 子目录后立即正常。详见 `references/edge-troubleshooting.md`。

### #55. SSH → Windows headed 浏览器不弹窗：是环境限制，不是代码 bug（v3.20 新增）

55. **SSH → Windows headed 浏览器不弹窗：是环境限制，不是代码 bug（v3.20 新增）**：通过 SSH 在 Windows 上启动 Playwright headed 模式的 Edge 时，浏览器进程可以正常运行和导航（页面加载成功），但**窗口不会出现在用户的 Windows 桌面上**——所有 `MainWindowHandle` 均为 0。根因是 SSH session 运行在非交互式会话中，无权访问用户的交互式桌面。**判别方法**：`powershell "Get-Process msedge | Select-Object Id, MainWindowTitle, MainWindowHandle"` 看到 MainWindowHandle 全为 0 但进程存在即可确认。**解决方向**：不要试图通过 SSH 弹窗给用户看。替代方案——① CDP（Chrome DevTools Protocol）：用户手动启动 Edge 带 `--remote-debugging-port=9222`，Playwright 通过 CDP 连接到已有浏览器实例；② 用户自己在 Windows 终端运行脚本。反面案例（2026-06-03）：CC 反复尝试多种 headed 模式、换路径、换 profile 均无法弹窗，Hermes 介入分析后确认是 SSH session isolation 的硬限制，浪费大量 token 在不可行的方向上。

### #56. CC 自动压缩可能耗时 2~3 分钟（v3.21 新增）

56. **CC 自动压缩可能耗时 2~3 分钟（v3.21 新增）**：CC 在上下文接近上限时自动触发 `/compact`，期间 capture-pane 显示 `✶ Compacting conversation…` 或 `✢ Compacting conversation…`。压缩可能持续 2 分钟以上，看起来像卡住，实际在正常处理。**不要 C-c 打断**——压缩是自发的清理操作，打断无益且可能丢失压缩进度。耐心等待压缩完成，CC 会自动恢复响应。反面案例（2026-06-03）：压缩耗时 2 分 37 秒，Hermes 多次检查 pane 犹豫是否打断，最终选择等待。正确的做法是识别 `Compacting conversation…` 信号后拉长轮询间隔（15-20s），等它自行完成。

### #57. 压缩后 CC 丢失上下文可能导致错误判断（v3.22 新增）

57. **压缩后 CC 丢失上下文可能导致错误判断（v3.22 新增）**：压缩完成后 CC 会 re-read 关键文件以恢复上下文，但由于对话历史被压缩，CC 可能忘记当前任务的实际状态——比如把正常运行的进程误判为已中断，把当前写入的状态文件误判为旧数据。**Hermes 必须在压缩完成后主动纠正 CC**：告知当前正在运行什么、状态文件的含义、任务的真实进展。不要等 CC 自己从文件中推测——它缺少压缩前的对话记忆，推测容易出错。反面案例（2026-06-03）：CC 压缩后读取 keepalive_status.json 和文件列表，错误认为 CDP 保活任务可能已中断、状态文件是旧数据，实际保活正常运转三轮。Hermes 发纠正消息后 CC 才恢复正确认知。教训：压缩后 CC 的第一版分析结论不可信，需要 Hermes 主动补充上下文再验证。

### #59. 禁止不必要的 git 远程操作（v3.24 新增）

59. **禁止不必要的 git 远程操作（v3.24 新增）**：当 CC 检查本地已 clone 的仓库状态时（如 health-coach），CC 倾向于自动执行 `git remote -v` / `git fetch origin` 等网络操作。**用户已明确纠正**：「不是都在本地的吗，为什么要git远程？」。正确做法：Hermes 在 TASK 指令中明确指定「只用本地文件检查——ls, find, head, read 命令，不要 git fetch/remote 等网络操作」。理由：(a) git fetch 涉及网络，可能因网络问题 hang 住数分钟；(b) 用户只关心本地内容完整性，不需要与 remote 比对；(c) `git fetch` 等操作在 CC 中每次都需要单独批准弹窗，拖慢流程。当用户说「检查本地仓库」时，应假设本地就是完整的引用源，除非明确要求比对 remote。反面案例（2026-06-03）：CC 在 Step 4 评估中自动执行 `git fetch origin` 检查 upstream 状态，用户立即纠正「不要远程」。：`read_file` 输出中的 API key 会被掩码为 `sk-3e2...c0c1`，**严禁将此掩码字面量用作 `patch` 的 `old_string`**。`patch` 的模糊匹配策略可能使掩码匹配到真实 key，然后用字面量 `...` 覆盖，导致 config 不可逆损坏。正确做法：① 通过 `python3` 二进制读取确认真实字节后才构造 `old_string`；② patch 后立即验证 key 完整性；③ 若 key 已损坏，从同文件的 provider 子段或其他 profile config 恢复（它们通常共享同一 key）。反面案例（2026-06-03）：用 read_file 的掩码输出 patch default config，model.api_key 被替换为 `sk-3e2...c0c1`，需从 deepseek provider 段找回真实 key 修复。

### #60. CC 自带 `/skill-creator` 命令（v3.24 新增）

60. **CC 自带 `/skill-creator` 命令（v3.24 新增）**：CC 内置了 `/skill-creator` 命令，可以交互式地创建、修改和测试 Hermes 兼容的 SKILL.md。当需要创建规范的多组件 skill 套件时，优先使用 `/skill-creator` 而不是手动编写。能力：① 创建新 skill → 交互式创建流程（frontmatter、tags、commands 自动生成）② 修改现有 skill → 传入 SKILL.md 路径进行优化（中文本地化、精简冗余、增加触发词）③ 测试 skill → 评估 skill 的触发准确性和性能。触发方式：在 CC 对话中输入 `/skill-creator`，CC 会进入交互式 interview 流程（plan mode 下用数字键 + 两拍法选择选项）。

### #61. Skill 创建必须用独立项目文件夹（v3.24 新增）

61. **Skill 创建必须用独立项目文件夹（v3.24 新增）**：CC 创建或重构 Hermes skill 时，**绝对禁止**直接在克隆的仓库目录（如 health-research/）中写 SKILL.md。克隆仓库是原始代码源，应保持不动。正确做法：在 `<windows-project-root>\` 下新建独立项目文件夹（如 `health-management-skill/`），其中：
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

### #62. CC 输出的 skill 内容必须逐项核对计划约定（v3.25 新增→v3.26 强化）

62. **CC 输出的 skill 内容必须逐项核对计划约定（v3.25 新增→v3.26 强化）**：CC 创建的 SKILL.md 内容可能包含我们已讨论排除的功能。Hermes 必须在每批完成后逐项核对约定文档（如 INTEGRATION_PLAN），发现偏差发回 CC 修正再继续。核对要点：\n   - tags/description 中是否含应排除的术语（如 Xiaomi wearable——无实现）\n   - commands 是否引用已砍除的文件\n   - **路由路径：`/skill-creator` 生成的扁平式路径（`scripts/diet.py`）是否匹配实际嵌套路径（`skills/diet-tracker/scripts/diet.py`）——这是最容易出错的点，每次必查**\n   - description 是否声称不存在的功能\n   - 涉及药物/医疗建议的 skill 是否有免责声明\n   \n   **工作流闭环**：给 CC 的 TASK 指令中应包含「完成后对照 INTEGRATION_PLAN 做自审，列出差异点修正完再通知我审查」。详细操作见 `references/skill-creation-workflow.md` §逐批自我审核。\n   \n   反面案例（2026-06-03）：CC 在 health-management SKILL.md 写入「Xiaomi」（无 provider）、「meal photo analysis」（边界不清），且路由路径 14 条全部是扁平式（实际 5 个子目录的嵌套路径）。用户指出「cc好像把我们讨论过要排除的内容都放进去了」。用户要求：「你要监督好cc，按照之前沟通的plan走」。\n\n63. **与 CC 交互前必须先加载并审查协作 skill（v3.27 新增→v3.37 强化）**：用户指出「你现在跟cc的对话都没有依照cc协作skill」——在与 CC 开始多轮交互前，必须先用 `skill_view('hermes-claude-collaboration')` 重新加载最新版本的协作 skill，特别注意检查最新的 pitfalls 和协议变更点。不要依赖记忆中的旧版本规则。**时机铁律：加载 skill 是涉及 CC 操作的「第一件事」，不是准备工作完成后的「最后一步」。** 当用户提到任何需要 CC 执行的操作（连CC、让CC做、跟CC讨论、恢复CC会话、试试XX功能[指CC侧Skill]等）时，**立即加载协作 skill**，不要先做搜索 session、查记忆、确认上下文等其他准备——这些可以在 skill 加载后继续做，顺序不影响效率，但反过来会违反协作纪律。\n\n   特别是以下操作前必须重新加载：\n   - 重置或创建 CC session 后首次交互\n   - 用户明确说「你看看协作 skill」「你重新加载一下」\n   - 多个 session 间隙后重新连接 CC\n   \n   反面案例（2026-06-03）：用户指出对话不正常后，Hermes 重新加载 skill 才发现已有 62 条 pitfalls 和完整两步确认法，而之前操作时完全没按这些做——因为用的是旧记忆而非最新 skill 内容。让用户被动提醒后才加载 skill，是不合格的协作纪律。
   反面案例（2026-06-07）：用户说「我想先试试客户管理」（指CC侧微信聊天管理Skill），Hermes 先做了 session_search、fact_store probe、read_file 等大量上下文准备工作，确认要连CC后仍准备直接连——直到用户再次提醒「记得加载cc协作skill，再连cc」才加载。正确做法：识别到任务涉及 CC 后**立即加载 skill**，再继续其他准备。\n\n64. **传话陷阱的判断标准（v3.27 新增）**：「不要当传话筒」的精确含义：收到 CC 输出后，Hermes 必须先做独立分析——指出 CC 方案的漏洞、矛盾和可改进之处——然后将质疑发回 CC 辩论（R2），而不是把 CC 的分析摘要改个格式就发给用户。\n\n   判断是否传话的标准：\n   - ❌ 传话：「CC 的分析列出了 X 个问题，包括 1...2...3...，要它改吗？」\n   - ✅ 讨论：「CC 的分析有 12 条差异，我看了觉得 #8 路由路径问题更重要，而且我倾向方案 B 而非 CC 默认的写法，理由是...」\n   \n   关键区别：传话是把 CC 的结论**格式转换**后转发；讨论是**用自己的判断给 CC 的结论做评估和定向**。详见 `references/monitoring-debate.md` §3.1 辩论协议。\n\n65. **批量任务不汇报中间进度（v3.28 新增→v3.47 扩展）**：用户说「全部完成再向我汇报」或类似表达（如「一次性汇报」「别分段说」「无需我介入」）时，在 CC 执行长周期批量任务的过程中，Hermes 应持续监控但**不向用户发送中间进度更新**。只在以下三种情况汇报：(a) 全部 Phase 完成；(b) 遇到不可恢复的阻塞需要用户决策；(c) 用户主动询问进度。

**CC plan 含中间停顿时发补充指令覆盖**：CC 的 plan 可能内置「每个阶段完成后询问用户」逻辑，与用户「全部做完再汇报」偏好冲突。当检测到 CC plan 中有此模式时，在 CC 开始执行前或空闲间隙立即发送补充指令（如「全程执行不中断，5个阶段全部完成后统一汇报结果，不要在每个阶段完成后停下来问我。遇到需要确认的操作按方案直接执行。」），覆盖 CC 的默认行为。不要等 CC 在每个阶段完成后弹窗提问时才临时处理——此时 CC 已经停下来了。**注意**：补充指令应在 CC 空闲时发送（无 emoji 标记），避免打断正在进行的工具调用。\n\n   **适用场景**：CC 执行多步文件清理 → 批量创建 SKILL.md → 统一修正的全流程。正确做法：capture-pane 轮询直到 DONE → 验证 → 一次性汇报全套结果。错误做法：每完成一个 Phase 就向用户报告「Phase A 完成了」「现在进 Phase B 了」。反面案例（2026-06-03）：用户连续收到 Phase A/B/C/D 的进度报告后直接说「全部完成再向我汇报」，嫌你啰嗦。\n\n67. **Tailscale IP 混淆——SSH 到云端而非 Windows（v3.30 新增）**：`tailscale status` 列出两个 IP，容易混淆：
   - `<cloud-tailscale-ip>` = 云端 Ubuntu（Hermes 所在机器，**不是 Windows**）
   - `<windows-tailscale-ip>` = Windows 笔记本（CC 所在机器）
   
   `ssh -p <ssh-port> <cloud-tailscale-ip>` 实际上是 SSH 回到云端自己（显示 `ubuntu@<cloud-hostname>`），不会连到 Windows。必须用 `ssh -p <ssh-port> <ssh-user>@<windows-tailscale-ip>` 才能连到 Windows。连接超时时先检查 Tailscale relay 状态（陷阱 44）。

### #68. 长消息用 SCP 文件绕过截断——所有模式通用（v3.31 新增，v3.36 修正→v3.45 再修正） _（同号变体之一）_

68. **长消息用 SCP 文件绕过截断——所有模式通用（v3.31 新增，v3.36 修正→v3.45 再修正）**：paste-buffer 的可靠性上限比预期更低——**正常模式下 2800 字符也会被截断**（2026-06-16 实测：step-3 指令 2848 chars，capture-pane 只显示末尾片段）。之前 v3.36 认为正常模式 500-2000 字符可靠，实际不可信。**更新策略：任何模式（normal/plan/accept-edits）下，消息超过 500 字符一律用 SCP 文件方式**——写云端文件 → SCP 到 Windows → 短 send-keys 让 CC 读取文件。这是唯一可靠的长消息传递方式。短 send-keys 仍可用于 ≤300 字符的快速指令。详见 `references/legal-article-collab-lessons.md`。

### #68a. cp -r 后必须验证完整性再删源（v3.29 新增） _（同号变体之一）_

68. **cp -r 后必须验证完整性再删源（v3.29 新增）**：执行 `cp -r` 复制目录树后，**必须先验证目标目录文件数与源一致**，再 `rm -rf` 删除源。反面案例（2026-06-03）：`cp -r` 只拷贝了顶层文件，`skills/` 子树丢失（70→5 个文件），然后立即 `rm -rf` 删源，导致子 skill 全部丢失需要从 Windows 重新传输恢复。用户严厉纠正「不要犯这个严重错误」。**强制流程**：① cp -r ② `find <src> -type f | wc -l` 与 `find <dst> -type f | wc -l` 比对 ③ 两数一致才删源。不要偷懒省略验证步骤。

### #68b. 从 Windows 到云端的批量文件传输：tar-over-SSH 优于 SCP（v3.28 新增） _（同号变体之一）_

68. **从 Windows 到云端的批量文件传输：tar-over-SSH 优于 SCP（v3.28 新增）**：当需要从 Windows 本地（CC 侧）将整个 skill 项目目录（含空格路径、大量小文件）传输到云端时，`scp -r` 在以下场景失败：(a) Windows 路径含空格导致 SCP 无法解析通配符 `/*`；(b) SCP 默认要求目标目录已精确存在，中途创建子目录失败则整批中断。\\n\\n   **可靠替代方案——tar over SSH pipe：**\\n   ```bash\\n   # 云端执行：拉取 Windows 整个目录\\n   cd <cloud_dest_dir>\\n   ssh -p <port> user@windows \\\"tar -czf - -C \\\\\\\"D:/path/with spaces/target\\\\\\\" .\\\" | tar -xzf -\\n   ```\\n   \\n   **原理**：`tar -czf - -C <src> .` 在 Windows 端打包为 tar.gz 流，通过 SSH stdout pipe 直接送到云端 `tar -xzf -` 解压。不需要中间文件，不需要处理路径空格问题，一条命令完成。\\n   \\n   **注意事项**：\\n   - `-C <src>` 指定源目录，`.` 打包所有内容（不含容器目录本身）\\n   - Windows 路径用双引号包裹，内部反斜杠转义为 `\\\\\\\\` 或直接用正斜杠 `/`\\n   - 先确认目标目录已存在（`mkdir -p`）\\n   - 此方案也适用于 rsync 不可用时的替代\\n   \\n   反面案例（2026-06-03）：先后尝试 `scp -r \\\"<windows-project-root>/...\\\"` 和 `scp source/*` 均因路径空格和目标目录变化而中断，改用 tar-over-SSH 一次传输 68 个文件成功。\\n\\n68. **HTTP server 作为云→Windows 文件传输的兜底方案（v3.35 新增）**：当 SCP/SSH-pipe 向 Windows 传输文件在 Tailscale relay 下超时时，启动 Python HTTP server 是可靠替代云端方案。详见 references/http-file-transfer.md。

### #69. CC 服务器不可达时的处理协议（v3.33 新增） _（同号变体之一）_

69. **CC 服务器不可达时的处理协议（v3.33 新增）**：当用户要求「跟CC讨论」「让CC做」但 CC 服务器（Windows 机器）SSH 连接超时/不可达时：\\n   \\n   1. 尝试 2 次 SSH 连接（间隔 10s），仍不通则确认服务器故障\\n   2. **立即向用户报告**服务器不可达的现状，不要继续猜测或等用户主动发现\\n   3. 同时评估任务是否可**自主完成**——检查现有工具是否已有对应能力\\n   4. 向用户一次性汇报：(a) CC 不可达的约束 (b) 你的独立分析结论 (c) 替代方案\\n   \\n   **反面案例（2026-06-04）**：用户要求「你跟cc讨论完后再向我汇报」，CC 服务器 <windows-public-ip> 超时，但未及时汇报而是尝试搜索文件、查日志等绕路操作后才告知。应：迅速确认不可达 → 立即汇报 → 给出独立替代方案。\\n   \\n   **关键**：不要因为用户说「讨论完再汇报」就延迟告知 CC 不可达的事实——这是阻塞性障碍不是中间进度。CC 不可达时应走独立分析路径，而非无限等待。

### #69a. 多工具整合分析的三维覆盖（2026-06-04 新增） _（同号变体之一）_

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

### #70. `--continue` 恢复后可能携带旧任务上下文（v3.34 新增） _（同号变体之一）_

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

### #70a. Permission 弹窗优先选「Don't ask again」（2026-06-04 新增） _（同号变体之一）_

70. **Permission 弹窗优先选「Don't ask again」（2026-06-04 新增）**

### #71. CC 自动修复 + 审查验证 + 部署工作流（2026-06-04 新增）

71. **CC 自动修复 + 审查验证 + 部署工作流（2026-06-04 新增）**：Hermes 审查代码后发现需要 CC 修改并部署到 Hermes，正确流程：

   ```
   1. Hermes 写 review-findings.md（逐条列出：问题位置行号、根因、修复方案、可选方案）
   2. SCP 到 Windows：`scp /tmp/review-findings.md <ssh-user>@<ssh-alias>:"<windows-project-root>/review-findings.md"`
   3. 在 Windows 启动 CC print mode 执行修复（不需要 tmux）：
      `ssh <ssh-user>@<ssh-alias> "cd /d \"<windows-project-root>/target-dir\" && claude -p --permission-mode bypassPermissions --dangerously-skip-permissions \"Read D:\\claude vscode\\review-findings.md and fix all issues.\""`
      关键参数：`-p`（非交互）、`--permission-mode bypassPermissions`（自动放行）
   4. Windows 端打包修改结果 → SCP 回云端：
      ```
      ssh <ssh-user>@<ssh-alias> powershell "Compress-Archive -Path 'D:\path\*' -DestinationPath 'D:\archive.zip' -Force"
      scp <ssh-user>@<ssh-alias>:"D:/archive.zip" <cloud-home>/
      unzip -o archive.zip -d <cloud-home>/review/
      ```
   5. Hermes 验证修改质量：
      - 语法检查：`python3 -m py_compile scripts/target.py`
      - 功能测试：`python3 -c "导入函数; 断言条件; print('OK')"`
      - 状态逻辑模拟：构造模拟数据结构，验证清理/边界逻辑正确性
      - 逐项对比 review-findings.md，确认所有问题已修复
   6. 验证通过后将修改后的包传回 Windows 覆盖原目录（保持版本一致）
   7. 部署到 Hermes：
      - 复制到 skills 目录：`cp -r <cloud-home>/source ~/.hermes/skills/skill-name/`
      - 验证注册：`skills_list` 确认新 skill 及子 skill 都在列表中
      - 验证加载：`skill_view('skill-name')` 确认 SKILL.md 内容完整、路由表正确
      - 删除旧 skill（被替代时）：`skill_manage(action='delete', name='old-skill', absorbed_into='new-skill')`

   Windows 路径关键技巧：
   - `scp` 用正斜杠：`"<windows-project-root>/file.txt"` ✅
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

### #72. CC Web Search 使用边界——本地文件分析 vs 外部调研（2026-06-05 新增，2026-06-06 修正）

72. **CC Web Search 使用边界——本地文件分析 vs 外部调研（2026-06-05 新增，2026-06-06 修正）**：CC 的 Web Search 工具有两个问题：(a) 频繁返回 0 结果且可能进入重试循环浪费 token；(b) CC 在分析本地文件时自发搜索而非读本地文件，是理解偏差。**正确区分**：外部调研（查 GitHub 仓库、查文档、查 API 用法）时 Web Search 合理可用，不应禁止；本地文件分析（读源码、读配置、分析项目结构）时 CC 不应搜索——此时若 CC 主动发起 Web Search，Hermes 应立即 Escape 中断并纠正方向（见陷阱 73）。**Hermes 指令措辞**：不要写「禁止 Web Search」（过于绝对），应写「本地文件分析请直接 Read，不要搜索」或「这些仓库已在本地 clone，用本地文件分析」。反面案例（2026-06-06）：Hermes 在微信管理任务中写「绝对禁止Web Search」，CC 合理地搜索了 wechat-daily-summary 的 GitHub 信息却被中断，用户纠正「web search并不是一定不能用」。

### #73. 监控 CC 方向——发现偏离应立即喊停纠正（2026-06-05 新增）

73. **监控 CC 方向——发现偏离应立即喊停纠正（2026-06-05 新增）**：用户明确要求「你发现CC做事方向有问题就要喊停，让它解释或纠正它」。Hermes 不应被动等待 CC 完成，而应持续监控 CC 的工具调用方向。**危险信号**：① CC 在分析本地文件时自发发起 Web Search ② CC 的输出偏离任务目标（如本应分析本地仪表盘设计却去搜索飞书模板）③ CC 反复执行同一失败操作（retry loop）④ CC 输出包含明显的事实错误或设计不符合用户需求。**处理**：立即 Escape 中断 → 明确指出问题 → 给出修正方向 → 等确认后继续。不要等 CC 完成一轮完整输出再纠正——越早干预，token 浪费越少。反面案例（2026-06-04）：Hermes 提出「4个仪表盘」方案，实际本地项目只有1个 Home 仪表盘——如果 CC 或 Hermes 在分析时及时读取本地项目就会避免此错误。

### #74. 先读源再设计——禁止凭空设计后反推本地项目（2026-06-05 新增）

74. **先读源再设计——禁止凭空设计后反推本地项目（2026-06-05 新增）**：涉及迁移/改造任务时，必须先让 CC（或自己）读取源项目的实际设计（仪表盘组件、数据模型、字段结构），基于实际设计制定迁移方案。禁止凭空设计新方案后声称适配了源项目——这是最常见的传声筒式协作错误。正确流程：① 读取源项目所有相关文件 ② 确认源项目的实际设计（表数量、字段、视图、仪表盘）③ 基于实际设计制定迁移方案 ④ 讨论差异点（哪些可以优化、哪些必须保留）。反面案例（2026-06-04）：Hermes 和 CC 讨论出「4个仪表盘」方案，实际本地项目只有1个统一 Home 仪表盘。用户指出：「本地也只有一个仪表盘啊，内容也很全面」。根因：CC 的 Web Search 全部失败后未及时切换到读本地文件模式。：CC 弹出 Bash 权限对话框（"Do you want to proceed?"）时，对于 **read-only 命令**（cat/ls/head/find/wc/curl -o到/tmp），直接选 **option 2（Yes, and don't ask again）**。同一类型的 SSH cat 命令如果多次出现，选 option 2 后同类命令自动放行，无需逐个批准，大幅减少交互次数。

    安全规则：python -c / node -e / rm / cp / mv 和 curl -o 到系统路径等写操作保留弹窗审查（option 1），不做预授权。

    反面案例（2026-06-04）：CC 同时排队 3 个 SSH cat 命令读云端源码，Hermes 连续 3 次选 option 1，每选完一次 CC 就启动下一条又弹窗，3 轮弹窗拖慢整个流程。第一次就选 option 2 则一次性放行。

### #75. 辩论R1阶段铁律：Hermes不做预消化（2026-06-05 新增）

75. **辩论R1阶段铁律：Hermes不做预消化（2026-06-05 新增）**：结构化辩论中，R1分析阶段 Hermes 的职责是发送**原始材料**（文章链接、文件、数据）给 CC，让 CC 独立分析。**严禁 Hermes 先完成分析再把消化后的结论发给 CC**——这样 CC 只能"审查"Hermes 的结论而非"独立分析"原文，辩论质量大打折扣。正确流程：R1 发送原始材料 → CC 独立分析 → R2 双方交换分析意见。用户明确纠正：「不是把你消化完的内容给cc」。反面案例（2026-06-05）：商业秘密规定文章协作中，Hermes 在 R1 先自己做完了"规定 vs 反法对照分析"发给 CC，用户指出应让 CC 直接分析原文。

### #76. CC修正时明确边界——防止重写引入新错误（2026-06-05 新增）

76. **CC修正时明确边界——防止重写引入新错误（2026-06-05 新增）**：当要求CC修正特定错误时，必须明确指令"**仅修正XX，保持文章结构、内容、其他条款编号不变**"。不加此约束时，CC 倾向于重写整篇文章来"更好地"修正——结果可能引入更多错误。反面案例（2026-06-05）：要求 CC 修正反法条号（第九条→第十条），CC 重写了全文→将《规定》自身条款编号全部搞错（保密措施从 Art.9 变成 Art.6）。二次审核发现后需再次修正。

### #77. 法律条款编号双重核对（2026-06-05 新增）

77. **法律条款编号双重核对（2026-06-05 新增）**：法律写作协作中，条款编号错误是最常见的致命伤。审核时必须**逐条双向核对**：既要验证上位法条号（如反法），也要验证下位法条号（如《规定》）。flk-npc 的"命中展示"功能不返回条号——条号验证应使用**新旧对照表**或**官方全文**。详见 `references/legal-article-collab-lessons.md`。

### #78. 法律写作R3执行：锁定结构防CC漂移（2026-06-05 新增）

78. **法律写作R3执行：锁定结构防CC漂移（2026-06-05 新增）**：R2确认文章结构后，R3指令中必须逐条列出章节结构（「第1章覆盖X→第2章覆盖Y→...」），使用「严格按下述结构」「不要擅自改变结构、不要合并章节」的明确措辞。不加此约束时CC倾向自由优化——合并章节、压缩段落、重组顺序。详见 `references/legal-article-collab-lessons.md` §9。

### #79. CC 写入文件替代对话输出（v3.36 新增）

79. **CC 写入文件替代对话输出（v3.36 新增）**：CC 在 accept-edits 阻塞时，可能将分析/草稿写入本地文件而非输出到对话。捕获信号：CC 长时间"thinking"（3min+）但无对话输出 + 检查有无新 Write 操作。处理：(a) 用短指令让 CC "展示文件核心结论" (b) 如果 CC 确认文件已写入，Hermes 直接读取文件内容继续协作 (c) 不要无限等待 CC 在对话中输出——它可能永远卡在 accept-edits。反面案例（2026-06-05）：CC 将 R1 分析写入 商业秘密保护规定深度解读_R1.md（231行），Hermes 等待 7 分钟后才意识到文件是输出方式，发"展示核心结论"指令后立即获取了分析。

### #80. CC 框架默认化倾向（v3.36 新增）

80. **CC 框架默认化倾向（v3.36 新增）**：CC 在 R1 中口头同意一个新的分析方向后，在实际写作时可能仍默认回到自己最熟悉的框架。口头同意 ≠ 写作遵从。应对：(a) R1 阶段 CC 写入文件后，Hermes 必须读取文件确认方向一致——不要只看 CC 的对话摘要就通过 (b) R2 不只要讨论结构，还要锁定章节标题措辞（如"本节标题不得出现'新旧''八大变化'字样"）(c) R3 指令追加"检查全文章节标题，不得出现指向旧框架的表述"。反面案例（2026-06-05）：CC 在 R1 明确同意"反法×规定配合关系"方向，但文件章节标题仍是"新旧对照：八大核心变化"——回到了新旧对比框架。

### #81. Rename 串字（v3.36 新增）

81. **Rename 串字（v3.36 新增）**：HERMES-ACTIVATE 和 `/rename` 在 accept-edits 模式下间隔过短时，CC 会将后续文字合并进 rename 参数。应对：activate 后等 2s → rename → 等 2s → capture-pane 确认名称 → C-c 清空残留再发下一条。

### #83. CC compound command 审批对话框操作技巧（2026-06-06 新增→修正→v3.47 强化）

83. **CC compound command 审批对话框操作技巧（2026-06-06 新增→修正→v3.47 强化）**：CC 在 accept-edits 模式下执行 compound command（含 `|`、`>`、`&&`、`2>/dev/null` 等管道/重定向）时，Claude Code 弹出 "Do you want to proceed? 1. Yes / 2. No" 对话框。**tmux send-keys 可以操作此对话框**（两拍法：`send-keys '1'` → sleep 0.5s → `send-keys Enter`），但需要注意：(a) **时序**——send-keys 发送到输入框而非对话框时，数字会和输入框残留文字拼接（如 `/exit/exit`），需先 Escape 清空输入框再发数字；(b) **焦点**——capture-pane 能看到对话框不代表输入焦点在对话框上，若 `1`+Enter 无效，先 Escape 取消对话框再让 CC 重新触发或换简单命令；(c) **CC 内置斜杠命令可通过 tmux 发送**——`/mcp`、`/exit`、`/compact` 等命令可通过 `send-keys '/mcp' Enter` 直接执行（实测有效），但 CC 无法通过 Bash 执行这些命令；(d) **仍建议减少 compound command**——简单命令更可靠，减少弹窗次数。

**⚠️ 选项编号心算验证（2026-06-24 新增）**：操作审批弹窗（"1. Yes / 2. No"）前，**必须在 capture-pane 中确认当前选项编号再按键**。Hermes 曾在快速轮询中误按 `2`（No）而非 `1`（Yes），直接中断了 CC 正在执行的验证步骤，导致需要发补充指令恢复。**正确流程**：capture-pane 读到弹窗 → 心算确认「1=Yes/2=No，我要选Yes=按1」→ send-keys '1' → sleep 0.5s → send-keys Enter。不要凭肌肉记忆按数字——尤其是轮询密集、注意力分散时。

### #84. CC 修改运行中服务的代码后必须手动重启（2026-06-07 新增→2026-06-07 修正）

84. **CC 修改运行中服务的代码后必须手动重启（2026-06-07 新增→2026-06-07 修正）**：当 CC 修改了正在运行的 MCP Server 或其他服务的源码后，**代码改动不会自动生效**（stdio 模式的 MCP Server 进程是持久的，不会重载代码）。Hermes 在 TASK 指令中必须明确：(a) 改完后先不要重启，等确认修改无误后再重启 (b) 明确告知重启方式——如果 Hermes 知道进程的启动命令/配置位置，直接提供；如果不知道，让 CC 先定位再汇报。**已验证的重启流程（wechat-decrypt MCP Server，2026-06-07）**：① 用户在本地手动重启 MCP Server 进程 ② CC 通过 tmux 执行 `/mcp` 命令重连（`send-keys '/mcp' Enter`），capture-pane 确认显示 `Reconnected to <server-name>` ③ 重新调用 MCP 工具验证代码改动生效。**注意**：MCP Server 的配置可能不在标准路径（mcp.json/settings.json 的 mcpServers 为空），此时让 CC 搜索会陷入循环。Hermes 应提前从云端帮助定位（SSH 搜索进程、读取配置文件），或直接让用户手动重启 + `/mcp` 重连，不要求 CC 自己找进程。**CC 找进程配置时经常陷入循环**（反复搜索 mcp.json、settings.json、tasklist，每个搜索命令都触发权限弹窗），Hermes 应提前从云端帮助定位（SSH 搜索进程、读取配置文件），缩短 CC 的搜索时间。反面案例（2026-06-07）：CC 改完 wechat-decrypt MCP Server 代码后花 10+ 分钟找不到进程配置（标准路径 mcp.json/settings.json 均无），反复触发权限弹窗，最终通过用户手动重启 + `/mcp` 重连才验证成功。

### #85. CC 编造权威分析框架（2026-06-07 新增）

85. **CC 编造权威分析框架（2026-06-07 新增）**：当 CC 被要求解释方法论或分析问题时，可能编造看似权威的结构化框架（如「严重程度评级」「建议的改进方向」表格），实际上不是基于实际验证的结论。**判别信号**：CC 输出的分析框架中出现它没有实际调用工具验证过的维度/评级/分类。**处理**：在质疑指令中明确要求「不要编造分析框架，如果某个结论没有实际验证过就直接说不知道」。CC 在被追问时通常会承认编造（本次实测 CC 主动承认「是我编造的分析框架」）。反面案例：微信客户管理演示后用户质疑标签遗漏，CC 在回答中附带了「严重程度评级」，CC 后来承认这是编造的。

### #86. CC multiline python/node 命令触发连环权限弹窗（2026-06-07 新增）

86. **CC multiline python/node 命令触发连环权限弹窗（2026-06-07 新增）**：CC 执行 `python -c "multiline script with # comment"` 或 `node -e "multiline with // comment"` 时，Claude Code 检测到 "Command contains a quoted newline followed by a #-prefixed line" 警告，每次都弹出 "Do you want to proceed? 1. Yes / 2. No" 权限对话框。**当 CC 连续执行多个此类命令时（如逐文件搜索、逐配置检查），弹窗泛滥导致效率极低——每个命令都要 Hermes 手动批准。** 应对：(a) **首次即选 option 2（don't ask again）**——同类命令模式自动放行，后续不再弹窗；(b) **Hermes 从云端提前查信息**——如果 CC 要搜索的配置/进程信息 Hermes 能从云端 SSH 获取，直接提供给 CC，避免 CC 发起大量 python -c 搜索命令；(c) **指导 CC 用简单命令**——`cat file | grep pattern` 比 `python -c "import json..."` 更少触发弹窗。反面案例（2026-06-07）：CC 搜索 MCP Server 配置时连续发起 15+ 个 `python -c "import json; open(...)..."` 命令，每个触发权限弹窗，Hermes 花数分钟逐一批准，最终搜索结果为空（配置不在标准路径）。

### #87. 用户偏好「先分析方案再执行」的 CC 工作流（2026-06-07 新增）

87. **用户偏好「先分析方案再执行」的 CC 工作流（2026-06-07 新增）**：对复杂的 Skill 设计/功能开发任务，用户偏好让 CC 先充分分析方案再动手。具体模式：Hermes 发送需求 → CC 进入 plan mode（自动触发或 Hermes 指示）→ CC 用 Explore agents 调研项目结构和工具能力 → CC 输出完整 Plan 文档（含执行步骤、输出格式、风险评估）→ 确认后 CC 再执行。**优点**：(a) CC 的 Plan 阶段会自主发现 Hermes 未想到的问题（如 MCP 参数 `oldest_first` 的存在性验证）(b) 方案文档可作为执行对照，防止执行偏差 (c) 用户（通过 Hermes）在执行前有机会质疑和调整方向。**适用场景**：新 Skill 创建、功能设计、架构决策。**不适用**：简单修改、单文件编辑、已知方案的执行。

### #88. CC 编造日期/星期几等未验证事实（2026-06-07 新增）

88. **CC 编造日期/星期几等未验证事实（2026-06-07 新增）**：CC 系统提示中有 `currentDate: YYYY-MM-DD`，但不包含星期几信息。CC 可能凭「感觉」推断星期几并输出错误结论（如将周日说成周六）。**这是编造的子类**——CC 没有用任何工具验证就直接输出了日期相关的推断。**判别信号**：CC 输出中出现「今天是周X」但未附带验证来源（如 `date` 命令输出）。**处理**：Hermes 在 TASK 指令中要求涉及日期的判断必须用工具验证（`date` 或 `python -c "import datetime; ..."`），不允许凭系统提示的日期推断星期几。反面案例：CC 分析客户汇总时说「6月7日是周六，客户沟通减少属正常」，实际是周日。用户指出「时间日期好像经常会有错误」。

### #89. CC 启动序列铁律——cd→启动→激活→resume（2026-06-08 新增） _（同号变体之一）_

89. **CC 启动序列铁律——cd→启动→激活→resume（2026-06-08 新增）**：启动 CC 的完整序列必须严格按以下顺序，不可跳步或混淆：
   1. `ssh <ssh-alias>`（确认连接）
   2. `cd /d "<windows-project-root>"`（进入项目目录——**不是用户 home 目录**）
   3. `claude --model glm-5.2`（正常模式，**禁止 `--dangerously-skip-permissions`**，见陷阱 #2）
   4. `<!-- HERMES-ACTIVATE -->`（激活协作模式）
   5. `/rename Hermes:<任务名>`（命名对话，带前缀）
   6. 若恢复旧对话：CC 内部 `/resume <会话名>`（**不是 shell 级 `claude --resume`**，见陷阱 #45）

   **反面案例（2026-06-08，连续三次违规）**：
   - 没有先 cd 到项目目录就直接启动 CC → 用户指出「你没进正确的项目目录啊」
   - 使用了 `--dangerously-skip-permissions` → 用户立即制止「这个很危险，不能启用」
   - 混淆 shell 级 `--resume` 与 CC 内部 `/resume` → 用户纠正「resume 不是启动前输入的，是启动后再输入的」
   
   **弹窗处理顺序**：Bypass Permissions 警告弹窗中，`1` = No, exit，`2` = Yes, I accept。误按 `1` 会导致 CC 退出。多个弹窗堆叠时必须先 kill session 重建，不要在堆叠弹窗中尝试逐个通过。

### #89a. 启动 CC 前必须 cd 到项目目录（2026-06-08 新增） _（同号变体之一）_

89. **启动 CC 前必须 cd 到项目目录（2026-06-08 新增）**：启动 CC 前必须在 SSH 连接后先 `cd /d "D:\项目目录"` 再执行 `claude`。否则 CC 在 `<windows-userhome>`（用户 home）启动，看不到项目文件和 CLAUDE.md 上下文，后续所有操作基于错误的 cwd。**强制流程**：`ssh <ssh-alias>` → `cd /d "D:\项目目录"` → `claude --model xxx`（绝不加 `--dangerously-skip-permissions`）→ 过弹窗 → 激活四步法。反面案例（2026-06-08）：Hermes 直接 `ssh <ssh-alias> && claude` 导致 CC 启动在 home 目录，用户指出「你没进正确的项目目录啊」。

### #90. Resume 两种用法——启动参数 vs CC 内部命令（2026-06-10 修正）

90. **Resume 两种用法——启动参数 vs CC 内部命令（2026-06-10 修正）**：`--resume` 作为启动参数和 CC 内部 `/resume` 命令都有效，但用途不同：
   - **启动参数** `claude --model xxx --resume`：从 bash 启动时使用，会打开交互式会话选择列表。适合 tmux 重建后恢复旧对话——SSH→cd→`claude --model glm-5.2 --resume`→方向键选择目标会话→Enter。**这是 tmux 重建后恢复 CC 对话的首选方式。** 用户明确推荐（2026-06-10）。
   - **CC 内部命令** `/resume <会话名>`：CC 已在运行时，从当前会话切换到另一个会话。适合在 CC 内部做多任务切换。
   
   **仍绝对禁止**：`--continue`（恢复最近 session，可能误入用户会话）、`--dangerously-skip-permissions`。

### #91. CC 虚报完成——声称修改了文件但实际未执行（2026-06-08 新增）

91. **CC 虚报完成——声称修改了文件但实际未执行（2026-06-08 新增）**：CC 在讨论中可能用自然语言宣称已完成文件修改（如"我已将此分析更新到 template_cp.py 和 SKILL.md 中"），但实际上没有执行任何 Edit/Write 工具调用。这是 CC 编造行为（pitfall #85）的子类——不是编造分析框架，而是编造操作历史。**判别方法**：CC 声称修改文件时，检查 capture-pane 中该声明之前是否有对应的 `● Edit(...)` 或 `● Write(...)` 工具调用记录。无工具调用 = 虚报。**处理**：立即追问确认，要求 CC 回答是否实际执行了 Edit/Write。如果 CC 确认未执行（本次实测 CC 承认"那句话是我在 R2 回复中提前宣告了还没做的事情"），则不构成实际损害但需警惕。**预防**：讨论类指令中明确加"本次仅讨论分析，不修改文件"可减少此类事件，但不能完全杜绝——CC 有时在回复中自发宣告未执行的操作。

### #92. CC 对纯讨论任务自动触发 Explore 浪费 token（2026-06-09 新增）

92. **CC 对纯讨论任务自动触发 Explore 浪费 token（2026-06-09 新增）**：当指令是纯技术讨论/方案分析（不涉及本地文件操作）时，CC 可能仍自动触发 Explore agent 搜索本地文件。**判别信号**：capture-pane 看到 `Explore(...)` + `Search(pattern: ...)` + `Read(...)` 但指令明确说"不用读本地文件"或任务性质是讨论而非操作。**处理**：立即 Escape 中断 Explore（等待其完成再发下一条消息也行，但会浪费 30-60s token），然后重新发送强调"这是纯讨论，不要读文件"。**预防**：在指令开头明确写"这是一个纯讨论/技术分析任务，不需要读本地文件，请直接基于你的知识回答"。本次实测：vault 同步方案讨论，指令开头已说"需要你从本地Windows角度评估"，CC 仍自动 Explore 了 6 个文件（74.7k tokens），浪费约 45s。

### #93. 公众号文章：视觉元素密度 + 选题多样性（2026-06-09 新增）

93. **公众号文章：视觉元素密度 + 选题多样性（2026-06-09 新增）**：用户审查 CC 产出的公众号文章后给出两条核心反馈：(a) 纯文字太多，表格/代码块/流程图等视觉元素不够丰富；(b) "踩坑"主题已重复太多次，需要新角度。**规则**：Hermes 在审查 CC 产出的文章（或传递给用户前）必须检查：(i) 视觉元素密度——每 300-400 字至少一个结构化元素，连续纯文字不超过 3 段；(ii) 选题角度——与近期已发文章不重复，不落入"踩坑/避坑"等过度使用框架。Hermes 应在 CC 完成初稿后、发给用户前，主动做这两项检查并提出修改建议。详见 `references/legal-article-collab-lessons.md` §8 和 §10。

### #94. Hermes 必须审查 CC 选题/大纲是否符合用户意图再转发（2026-06-09 新增）

94. **Hermes 必须审查 CC 选题/大纲是否符合用户意图再转发（2026-06-09 新增）**：CC 提出的选题方向或文章大纲可能完全偏离用户明确表达过的方向。Hermes 不得把 CC 提案直接转发给用户选择——应先做匹配度检查：CC 提案是否与用户之前的要求一致？如果偏离，Hermes 应指出偏差并给 CC 发修正指令，而不是让用户在错误的选项中做选择。**反面案例**：用户明确说"续篇，展示 skill 结构，逐一解释"，CC 提出了"手机遥控 AI 敲代码"等完全不相关的方向，Hermes 未审核直接转发给用户。正确做法详见 `references/legal-article-collab-lessons.md` §10.4。

### #95. 续篇/后续文章的"架构"章节应展示工具自身结构，不是部署架构（2026-06-09 新增）

95. **续篇/后续文章的"架构"章节应展示工具自身结构，不是部署架构（2026-06-09 新增）**：写续篇文章时，如果上篇已覆盖了部署/远程架构，续篇的"结构"章节应展示工具/方案本身的文件/组件结构（目录树 + 职责说明），而非重复部署拓扑。用户明确纠正：「架构怎么是远程架构，不应该是skill的结构吗」。详见 `references/legal-article-collab-lessons.md` §10.2。

### #96. 审核 CC 产出文档时必须做事实核查——不能只审逻辑和叙事（2026-06-09 新增→2026-06-10 强化）

96. **审核 CC 产出文档时必须做事实核查——不能只审逻辑和叙事（2026-06-09 新增→2026-06-10 强化）**：Hermes 审核 CC 产出的文章/技术文档时，存在只关注内容逻辑（叙事线、字数、结构）而忽略具体技术细节事实性的倾向。**审核清单必须在逻辑审核之外额外执行事实核查**：(a) 文件名/路径是否与实际一致（`find`/`ls` 验证）；(b) 命令/代码是否可执行；(c) 数据/数字是否有来源；(d) 引用的术语/概念是否存在；(e) **描述的 CC/AI 行为是否与 CC 端实际配置一致**（不能只看 Hermes 侧 SKILL.md，必须查 CC 侧 hermes-collab.md）；(f) **面向公众的文章是否包含内部协议术语**（ACK/DONE/截断信号等需转换为通俗表述）。详见 `references/legal-article-collab-lessons.md` §13-§14。**反面案例（2026-06-09）**：CC 在公众号文章中虚构了 3 个不存在的文件名（message-protocol.md、tool-routing.md、debate-rules.md），Hermes 明明在同一 session 中用 `find` 获取了 skill 目录的完整文件列表（24 个真实文件名），但审核时完全未对照，直接通过了虚构内容。用户指出「你咋前面都没有核查出来」「不要再犯」。**根因**：审核 checklist（Verification Checklist）中"独立核实"条款过于笼统，未具体要求对照源数据。**强制补充**：审核 CC 产出的任何包含具体技术细节的内容时，Hermes 必须拿 session 中已获取的实际数据（find 结果、read_file 内容、工具输出）逐项比对文中细节，不能凭"看起来合理"就通过。

### #97. Hermes 不得通过 SSH 直接修改本地 Windows 文件——必须委派给 CC（2026-06-09 新增→2026-06-10 修正） _（同号变体之一）_

97. **Hermes 不得通过 SSH 直接修改本地 Windows 文件——必须委派给 CC（2026-06-09 新增→2026-06-10 修正）**

### #97a. Hermes 不得通过 SSH 直接操作本地 Windows 文件——必须委派给 CC（2026-06-09 新增→v3.46 扩展至读取） _（同号变体之一）_

97. **Hermes 不得通过 SSH 直接操作本地 Windows 文件——必须委派给 CC（2026-06-09 新增→v3.46 扩展至读取）**：核心原则 #6（按位置执行）规定了"云端文件由 Hermes 操作，本地文件由 CC 操作"。**此规则同时适用于读取和修改**——不仅不能通过 SSH 修改本地文件，也不应通过 SSH 读取本地文件（`ssh <ssh-alias> "cat ..."`, `scp ... <ssh-alias>:/path /tmp/...` 等）。读取本地文件（查看内容、确认进度、分析结构）同样应委派给 CC 执行——CC 直接 Read 本地路径比 Hermes 通过 SSH 通道更可靠（无编码问题、无路径转义问题、无 relay 延迟）。**默认规则**：本地文件的所有操作（读/写/改）必须委派给 CC 执行。反面案例（2026-06-17）：Hermes 试图 SSH 到 Windows 读取法律WIKI目录结构，用户纠正"你不需要读取本地文件，应该让cc读取"。**例外**：用户可显式授权 Hermes 直接操作。正确做法：在 TASK 指令中要求 CC 读取并汇报本地文件内容，Hermes 基于 CC 的汇报进行分析。

### #99. 编辑 D 盘文件前必须 SCP 最新版——不可依赖本地缓存（2026-06-10 新增）

99. **编辑 D 盘文件前必须 SCP 最新版——不可依赖本地缓存（2026-06-10 新增）**：当文件可能在 Hermes 操作间隙被第三方（用户、CC、其他工具）修改时，编辑前必须重新 SCP 拉取最新版。**判别信号**：上次 SCP 时间 > 30 分钟前，或知道 CC/用户也在操作同一文件。**反面案例（本次）**：Hermes 先 SCP 获取了 219 行版本写入 `/tmp/cc-article-draft-v6.md` 并在其上编辑，但 D 盘文件已被修改为 253 行版本（结构完全重排），Hermes 未重新拉取就直接在旧版上操作。**正确流程**：每次编辑前 `scp D盘路径 /tmp/latest.md` → `read_file /tmp/latest.md` → 基于最新版编辑 → `scp /tmp/latest.md D盘路径`。：通过 SSH 执行 PowerShell `Get-Content`、Python `open()` 或 `cmd /c type` 读取含中文字符的 Windows 文件路径时，返回的中文内容全部乱码（Windows console 编码与 SSH channel 不匹配）。**可靠 workaround**：先 `copy` 文件到 ASCII 路径（如 `<windows-userhome>\temp.md`），再 SCP 到云端读取。反面：`ssh <ssh-alias> "python -c \"f=open(r'D:\\中文路径\\file.md'...)\"`  → 乱码。正面：`ssh <ssh-alias> "copy \"D:\\中文路径\\file.md\" C:\\Users\\<ssh-user>\\temp.md"` → `scp -P 2222 <ssh-user>@<ssh-alias>:<windows-userhome>/temp.md /tmp/file.md` → `cat /tmp/file.md` → 正确。**注意**：SCP 本身传输中文路径文件不受影响（scp 客户端处理编码），问题出在 SSH 命令执行端的 console 编码。

### #100. CC 分页采样不足即下结论——数据量严重低估（2026-06-10 新增）

100. **CC 分页采样不足即下结论——数据量严重低估（2026-06-10 新增）**：CC 对分页接口（offset/limit）只翻了 3 页（offset 0→50→100 = 150 条）就停止，然后基于这 150 条样本推断总量为"200+"，实际总量是 2000+ 条。**根因**：CC 用"已翻页返回的最大条数"作为总量估计，而非持续翻页直到返回空结果来确认边界。**预防**：在 TASK 指令中要求 CC 持续翻页直到返回空结果（`offset` 递增直到返回 0 条或返回时间戳超出目标范围），或者明确告知预估总量级（如"这个时间段大概有 2000+ 条消息"），让 CC 调整采样策略。**Hermes 监控时注意**：capture-pane 看到 CC 的分页 offset 停在远小于预期总量处就开始写总结/方案时，应提醒用户 CC 可能采样不足。反面案例（本次）：微信群 5/25~6/9 有 2000+ 条消息，CC 翻到 offset 100（共 150 条）就写"数据摸底完成，至少 200+ 条"，用户中断纠正。

### #101. CC 分页查询中丢弃过滤参数导致返回范围外数据（2026-06-10 新增）

101. **CC 分页查询中丢弃过滤参数导致返回范围外数据（2026-06-10 新增）**：CC 在做 offset 分页时，前几次查询正确携带了 `start_time="2026-05-25"` 等过滤参数，但后续查询（offset 3000/4000/5000）丢失了 `start_time`，导致返回了 1-2 月的历史消息——与用户要求的 5/25~6/9 范围完全无关。**根因**：CC 在构造分页查询时只复制了 `end_time` 和 `limit`，漏掉了 `start_time`。**预防**：在 TASK 指令中明确要求"每次查询都必须携带完整的时间过滤参数（start_time + end_time），不要在分页过程中省略"。**Hermes 监控时注意**：capture-pane 看到 CC 的工具调用参数中缺少之前存在的过滤条件时，应立即提醒用户。反面案例（本次）：用户明确指出"我发现你再调取消息时没有严格按照我要求的时间范围"，CC 承认"后面的查询漏掉了 start_time 参数"。

### #102. CC 观察监控模式——用户手动操作 CC 时 Hermes 的角色（2026-06-10 新增→v3.41 修正）

102. **CC 观察监控模式——用户手动操作 CC 时 Hermes 的角色（2026-06-10 新增→v3.41 修正）**：当用户要求"我手动操作 CC，你帮我监控"时，Hermes 进入纯观察模式：(a) 不向 CC 发送任何**任务指令**（任务内容、操作要求、分析指令等均禁止）；(b) **基础设施搭建允许**：tmux 重建、SSH 连接、`claude` 启动、`<!-- HERMES-ACTIVATE -->`、`/rename` 等纯设置操作可以执行——这些是用户委托的"帮我连一下 CC"基础设施工作；(c) 通过 `tmux capture-pane` 定期轮询（15-20s 间隔）观察 CC 状态变化；(d) 记录 CC 的工具调用、输出内容、关键决策点；(e) 发现异常（卡住/弹窗/方向偏离/参数丢失）时主动通知用户；(f) 用"📋 监控记录 #N"格式实时汇报观察结果。此模式下 Hermes 是观察者和记录者，不是指令者。tmux session 由用户 attach 操作时，Hermes 只用 capture-pane 读取 pane 内容。

**⚠️ 边界判定（2026-06-10 补充）**：区分"基础设施搭建"和"任务指令"——SSH 连接、cd、claude 启动、activate、rename 是搭建（✅ 允许）；告诉 CC 去读文件、执行分析、拉数据、写输出等是任务指令（❌ 禁止）。反面案例：Hermes 帮用户连上 CC 后，开始写任务指令文件并准备通过 tmux 发送给 CC——越过了"帮我连一下"的边界，进入了"帮我操作"的领地。

**⚠️ attached 冲突（2026-06-10 补充）**：当用户 attach 到 tmux session 时（`tmux list-sessions` 显示 `attached`），Hermes 的 tmux 命令（capture-pane、send-keys 等）会返回 exit code 130（SIGINT）被中断——因为用户和 Hermes 的操作在同一 session 中互相冲突。**解决方案**：① 用户 detach（`Ctrl+B` 然后 `D`）后 Hermes 才能正常操作；② 或 Hermes 在同一 session 中创建新 window 做监控（`tmux new-window`），但此方案复杂度较高不推荐。**判别信号**：`tmux list-sessions` 输出含 `attached` + `tmux capture-pane` 连续返回 `[Command interrupted]`。

**日志持久化（长监控必备）**：监控超过 10 分钟时，必须将记录写入文件（如 `~/.hermes/cc-monitor-logs/<日期>-<任务>.md`），每次 capture-pane 发现变化就 `cat >>` 追加。**原因**：长监控必然触发上下文压缩，压缩后 Hermes 会丢失所有之前的监控记录——文件是唯一的跨压缩持久化手段。用户明确提醒：「你最好把监控过程记录到某个log或md文件中，不然上下文压缩后你就会不记得了」。文件格式建议：每次变化一个 `### #N` 段落，含时间戳、状态摘要、工具调用记录。

### #103. CC "优化陷阱"——绕过可靠 MCP 直接访问底层 DB，浪费大量时间（2026-06-10 新增）

103. **CC "优化陷阱"——绕过可靠 MCP 直接访问底层 DB，浪费大量时间（2026-06-10 新增）**：CC 在处理数据导出任务时，经常主动放弃可靠的 MCP 工具调用，转而尝试直接访问 MCP 工具背后的底层数据库（如 wechat-decrypt 的 SQLite DB），声称"直接 SQL 导出更快"。**实际结果**：微信 DB 是 SQLCipher 加密的、schema 映射关系复杂（群名→Msg 哈希表需要 contact.db 但找不到）、ZSTD 解压失败等，CC 花费 15-20 分钟执行 15+ 次 bash 调用后全部失败，最终不得不回到 MCP 方案。**MCP 工具内部已处理了解密、解压、名称映射等所有复杂性，CC 的"优化"实际是退化。**预防：(a) 在 TASK 指令中明确要求"直接使用 MCP 工具，不要尝试访问底层 DB 或绕过 MCP"；(b) Hermes 监控时一旦发现 CC 开始发起 `python3 -c "import sqlite3..."` 或 `find *.db` 等 DB 探索命令，应立即通知用户 CC 可能在走偏。反面案例（本次）：CC 花 20 分钟 SQL 导出后 23.6% 消息乱码，用户两次中断才让它回到 MCP 方案。

### #104. CC 大数据全放 context 导致 compaction 循环（2026-06-10 新增）

104. **CC 大数据全放 context 导致 compaction 循环（2026-06-10 新增）**：CC 使用 MCP 批量拉取数据时（如 5958 条微信群消息），把所有 MCP 返回结果留在 context 中而不写入文件。结果：(a) 每 6 批（3000 条）就触发一次 compaction；(b) compaction 后数据被压缩摘要丢失，CC 又从头拉取；(c) 形成"拉数据→放 context→compaction→丢失→重新拉→放 context→compaction"的恶性循环，同一数据被拉取 3 轮（共 ~9000 条 MCP 调用，实际只有 5958 条不重复）。**正确做法**：拉一批数据后立即用 Write/Edit 工具写入 md 文件，不要积累在 context 里。CC 需要被告知具体方案——它不会自动想到写文件（实测用户中断 2 次后 CC 才勉强采纳，但 Write 方案 CC 又嫌"太慢"想改 Python 脚本）。**批次大小红线（2026-06-10 实战确认）**：500条/batch 会导致 MCP 返回数据 + Edit 工具参数总量超出 context window（`API Error: The model has reached its context window limit`）。即使 MCP 返回成功、Edit 也可能因参数过大而溢出。**安全批次：≤50条/batch**。50条的 MCP 返回 + Edit 调用能在 context 中正常处理。代价是循环次数多（5958条需要 ~120 轮），但每轮可预测、不会溢出。

**CC 自救模式**：CC 被 Write 工具拒绝后可能自建 Python 辅助脚本（如 `append_chat.py`，从 stdin 读取并 append 到目标文件）。这是合理的变通，Hermes 不应打断——只要 CC 仍用 MCP 拉取数据而非绕到 SQL 数据库路径。

**预防**：在涉及大数据导出的 TASK 指令中明确要求"每拉一批数据后立即 Edit/Write 到文件，不要把原始数据留在 context 中。批次大小限制 50 条/批"。Hermes 监控时注意 CC 是否在 MCP 调用后紧跟着写入操作——如果没有，应提醒用户 CC 可能在把数据全放 context。

### #105. CC Germinating/Blanching 超时后 C-c 可能误杀已完成操作（2026-06-10 新增）

105. **CC Germinating/Blanching 超时后 C-c 可能误杀已完成操作（2026-06-10 新增）**：CC 进入 Germinating/Blanching 状态超过 3 分钟无变化时可能卡住，也可能在后台完成了工具调用（MCP 返回+Edit 写入）但输出被吞。**C-c 打断前必须先检查目标文件是否已有新内容**——不要假设"长时间无输出 = 什么都没做"。如果文件行数增加了（`wc -l` 比上次多），说明 Edit 已成功写入，C-c 后应继续下一批而非重发当前批次。**判别方法**：① capture-pane 连续 3 次相同（间隔 15s）② SSH 未断（检查 pane 末行无 Broken pipe）→ 确认卡住后再 C-c。③ C-c 后检查 CC 输出——如果 CC 立即报告"Batch N 完成"，说明操作已在后台完成。详见 `references/error-recovery.md` §9。反面案例（本次）：CC Germinating 3m37s，Hermes C-c 打断后误判为失败发了恢复指令，实际 Edit 已写入 Batch 18（文件行数已增加），CC 重新拉取了已写入的数据。

### #106. SSH 反复断连的长任务恢复——让 CC 自查文件续接（2026-06-10 新增）

106. **SSH 反复断连的长任务恢复——让 CC 自查文件续接（2026-06-10 新增）**：SSH 因 Tailscale relay 不稳定反复断连（一晚 3 次 Broken pipe）导致 CC 被杀时，不要凭 Hermes 记忆的 offset 告诉 CC 从哪继续（compaction 后记忆不可靠）。**让 CC 自己读目标文件末尾确认最后的 offset**，然后从断点继续。CC 能通过文件内容自动定位进度。compaction 后 CC 也能通过 re-read 文件恢复。恢复指令模板：「读取 <文件> 末尾 20 行，确认最后 offset，从 offset+50 继续拉取。不要问我要不要继续，一直跑完。」详见 `references/error-recovery.md` §8。

### #107. 批量循环任务需监控 Edit 静默失败（2026-06-10 新增）

107. **批量循环任务需监控 Edit 静默失败（2026-06-10 新增）**：CC 在批量循环中执行 Edit 追加数据，部分 Edit 可能静默失败（返回 error 或被拒绝），产生 offset 缺口但 CC 误以为全部写入。**预防**：TASK 指令中要求"每批写入后 Read 验证文件末尾"，循环结束后做完整性检查（批次计数 vs 行数 vs 起止 offset）。**检测**：CC 报告总批次 N 但文件中 offset 不连续，或行数不符预期。详见 `references/error-recovery.md` §10。

### #108. CC bash 权限确认框在长监控中完全吞输入（2026-06-10 新增）

108. **CC bash 权限确认框在长监控中完全吞输入（2026-06-10 新增）**：CC 在长任务执行中触发 bash 权限确认框（`Do you want to proceed? > 1. Yes / 2. No`）时，如果 CC 处于 accept edits 模式或长时间运行后的特殊状态，确认框可能完全吞掉所有输入——`1`、`Enter`、`Escape` 均无效，capture-pane 连续多次完全一致。**这不同于普通的 accept edits 阻塞（pitfall #42）**——普通阻塞影响所有 send-keys，但此问题特定于 bash 确认框。**变通**：Hermes 通过 SSH 远程直接执行 CC 想要的命令（如 `ssh <ssh-alias> "grep -oP 'Batch \d+' file.md | sort ..."`），绕过 CC 的确认框。或者在 tmux 中 `C-c` 取消 CC 当前操作，手动确认弹窗消失后，让 CC 用搜索工具（Read/grep）代替 bash grep 做检查。反面案例（本次）：CC 完成 5958 条导出后自动发起 grep 检查批次连续性，确认框吞输入，Hermes 发 1、Enter、Escape×3 均无效，最终改为 Hermes 远程 SSH 执行 grep 完成检查。

### #109. Compaction 后不要纠结旧对话内容——信任用户当前指令（2026-06-10 新增）

109. **Compaction 后不要纠结旧对话内容——信任用户当前指令（2026-06-10 新增）**：Hermes 上下文被 compaction 压缩后，压缩摘要可能不准确或遗漏关键细节。**此时不要与用户争论「你之前说了 X 还是 Y」**——Hermes 的记忆基于压缩摘要，可能已经失真。正确做法：(a) 用户当前指令优先于压缩摘要中的记录；(b) 如果用户说「不要执拗于之前的记录，直接做 X」，立即执行 X；(c) 需要确认历史细节时用 session_search 搜索，不要凭压缩摘要猜测。**根因**：compaction 是有损压缩，摘要中的对话细节不可靠。用户比压缩摘要更清楚自己说了什么。反面案例（2026-06-10）：用户让 Hermes「连CC继续推进任务」，Hermes 基于 compaction 摘要中「不需要你帮忙发指令」这句话反复纠结是否应该发指令，浪费 3+ 轮对话。用户纠正「你好好确认上下文」「那都是多少轮对话之前的事情了，不要执拗」。

### #110. CC resume 搜索框残留文字跨次污染（2026-06-11 新增）

110. **CC resume 搜索框残留文字跨次污染（2026-06-11 新增）**：在 CC resume 交互列表的搜索框中输入文本后，C-c 退出再重新进入 resume，**搜索框内容不会自动清空**，可能与下次输入拼接导致混乱。实测：搜索"噪音分析" → C-c 退出 → `claude --model glm-5.2 --resume` → 搜索框显示"噪音claude --model glm-5.2 --resume"。**清空方法**：在 resume 列表中按 `Esc`（通常需要 2-3 次）才能清空搜索框，再 C-c 退出。不要假设 C-c 会清空搜索框。

### #111. CC resume 搜索不可靠——找不到已知存在的 session（2026-06-11 新增→修正）

111. **CC resume 搜索不可靠——找不到已知存在的 session（2026-06-11 新增→修正）**：CC resume 列表的搜索功能可能找不到已知存在的 session。实测：目标 session 文件 `9f286945...jsonl`（20.9MB）确实存在于 `.claude/projects/` 目录，但搜索"噪音分析""微信群""人工筛选""筛选"全部返回空结果。可能原因：(a) session 实际名称是一长段消息预览文本，不含关键词；(b) CC 在 session 期间做了清理（session 数从 118→80→50，多次刷新后持续变化），原 session 可能被重命名或合并。(c) 搜索框残留文字跨次污染（见陷阱 #110）。**教训**：不要在 resume 搜索上花过多时间（超过 3 分钟无效搜索应停止），转而采取替代方案（见陷阱 #113）。

### #112. CC resume 不支持 `--session-id` 参数（2026-06-11 新增）

112. **CC resume 不支持 `--session-id` 参数（2026-06-11 新增）**：`claude --resume <session-id-uuid>` 不会按 ID 恢复 session，而是把整个字符串（含 UUID）当作搜索词。CC resume 只支持：① 交互列表中方向键选择 ② 搜索名称（但搜索不可靠，见陷阱 #111）③ `--resume "精确名称"`。**无法直接通过 UUID 恢复 session。**

### #113. 找不到 CC session 时的实用替代方案（2026-06-11 新增→修正）

113. **找不到 CC session 时的实用替代方案（2026-06-11 新增→修正）**：当 CC resume 列表中找不到目标 session 时（搜索无结果、名称不匹配、session 被清理），不要无限翻页尝试——最高效的替代方案是**新建 session + 从输出文件续接**：(a) 正常启动 CC 新 session → 激活四步法 → rename；(b) 告诉 CC 读取之前的输出文件（如 `<windows-tmp>/法律AI加油站_人工筛选记录.md`）确认已完成进度；(c) 让 CC 从断点继续执行。CC 能通过文件内容自动定位进度，无需找到原始 session。**注意**：对于批量任务，建议启动后先 BTab 切换 plan mode 再发任务指令（见陷阱 #42 预防措施），避免 accept edits 阻塞。**反面案例**：本次花费 15+ 分钟在 resume 搜索、翻页、UUID 恢复尝试中反复失败，最终用户建议用方案 2（新 session 续接）。

### #114. Auto-compact during batch edit loop causes duplicate writes + Edit failures + inaccurate completion（2026-06-11 新增→实测强化）

114. **Auto-compact during batch edit loop causes duplicate writes + Edit failures + inaccurate completion（2026-06-11 新增→实测强化）**：CC 在批量循环任务中（逐批读取→分析→Edit 追加→下一批）触发 auto-compact 时，compact 过程可能导致 CC 重写当前正在处理的批次，在输出文件中产生**重复的批次条目**。重复导致后续 Edit 的 search/replace 找不到唯一匹配，报 "Error editing file"。

   **实测严重程度（2026-06-11 微信群筛选，78 批次任务）**：
   - 重复批次：第61批 **3次**、第62批 2次、第63批 2次（远非"仅2处重复"）
   - 缺失批次：第2批、第68批 **完全缺失**（210 行源数据未处理，CC 却报告"全部完成"）
   - CC 完成报告声称 K511+E578=1089 条，但实际因重复和缺失，数据不可直接使用
   - compact 后 Pontificating 22+ 分钟分析文件结构

   **同时（pitfall #57 子类）**：compact 后 CC 倾向花 5-22+ 分钟 Pontificating "理解文件结构"（搜索 `^## 第\\d+批` 等所有批次标题），而非直接检查最后批次号后继续。

   **预防**：在 TASK 指令中明确"每次写入后确认成功，compact 后只需 Read 输出文件最后 20 行确认最后批次号即可，不要搜索整个文件结构。发现重复批次时跳过，从最后正确位置继续"。

   **恢复**：CC Edit 连续失败时，Hermes C-c 打断 → 发直接指令"不要分析文件结构了，直接从第 N 批（行 X-Y）继续。读取源文件对应 100 行，逐条判断后追加写入输出文件。自动循环直到全部完成。" CC 通常在第 3-4 次 Edit 重试后成功写入。

   **⚠️ 完成后必须做数据完整性验证（不可信 CC 的完成报告）**：CC 报告"全部完成"时，Hermes 必须从云端 SSH 远程执行验证脚本（`templates/batch-verify.py`），检查：(a) 批次连续性（是否所有预期批次都存在）(b) 唯一性（是否有重复批次）(c) 逐条消息覆盖（保留+排除条目是否覆盖全部源消息——见 pitfall #115）。验证后再汇报用户。执行模式：写脚本到本地 → SCP 到 Windows → `python -u <windows-tmp>\batch-verify.py`。

### #115. CC 批量筛选默认选择性而非穷举——大量数据被静默跳过（2026-06-11 新增）

115. **CC 批量筛选默认选择性而非穷举——大量数据被静默跳过（2026-06-11 新增）**：当要求 CC 对数据进行"筛选"（如微信群消息噪音分析）时，CC 的默认行为是**只挑有价值的保留、顺手标记一些明显噪音排除，其余全部忽略**——而非逐条判定每条数据保留/排除。这导致大量数据（实测约28%，1700/6042条）既没保留也没排除，但 CC 报告"全部完成"。

   **根因**：CC 理解"筛选"为"挑选有价值的内容"，而非"对每条数据做出二分类判定"。CC 不会主动报告遗漏——它认为自己已经完成了任务。

   **预防——TASK 指令必须包含以下明确约束**：
   ```
   - 每条消息必须且只能判定为"保留"或"排除"二选一，不允许跳过任何一条
   - 保留编号从 K1 开始递增，排除编号从 E1 开始递增
   - 每批处理完后统计：本批消息总数 = 保留数 + 排除数，必须相等
   - 如果本批消息总数 ≠ 保留数 + 排除数，说明有遗漏，必须补上
   ```

   **检测**：CC 报告"全部完成"时，Hermes 必须执行数据完整性验证（见 `references/error-recovery.md` §15），检查：保留条目 + 排除条目是否覆盖全部源数据条目。**不可信 CC 的完成报告中的计数。**

   **反面案例（2026-06-11）**：CC 声称 K511+E578=1089 条处理完毕，用户质疑"对不上"后验证发现实际 6042 条源数据中只有 1113 条被处理，1700 条完全遗漏。教训：筛选类任务的 TASK 指令必须用穷举式措辞（"每条必须判定"），不能只说"筛选"。

### #116. CC compact 后多文件同时读取导致 context 溢出（2026-06-11 新增）

116. **CC compact 后多文件同时读取导致 context 溢出（2026-06-11 新增）**：CC 在 compact 后尝试 `Read 4 files` 同时读取多个批次文件时，触发 `API Error: The model has reached its context window limit`。compact 后 context 空间有限，多文件同时读入直接溢出。**预防**：TASK 指令中明确要求「每次只读取一个批次文件，判定完写入结果后，再读取下一个。绝对禁止同时读取多个文件」。**恢复**：`/exit` 退出 CC → 新建 session → 从上次完成的 JSON checkpoint 继续。反面案例（本次）：CC compact 后同时读取 batch 4-7 四个文件，context 立即溢出，Hermes 发「一次只读一个」的消息也被吞（API Error），只能杀 session 重建。

### #117. 大规模分类任务的"规则引擎+AI审核"混合模式（2026-06-11 新增）

117. **大规模分类任务的"规则引擎+AI审核"混合模式（2026-06-11 新增）**：当 CC 需要对数千条数据做分类/筛选时，**不要让 CC 直接读取源文件在 context 中逐条判定**——这会导致：(a) context 快速填满触发 compact 循环（见陷阱 #104）；(b) CC 默认选择性筛选而非穷举判定，大量数据被静默跳过（见陷阱 #115）。**正确模式**：
   ```
   Phase 1 — Python 规则引擎批量分类（Hermes/CC 写脚本，脚本执行）
     • 正则排除规则：纯表情/问候/短回复/天气等 → 直接排除
     • 关键词保留规则：法律AI/产品名/技术术语 → 直接保留
     • 长度+信号规则：短消息无信号排除，长消息无信号标记「需审核」
     • 输出 patch 文件 + 需审核消息的行号列表

   Phase 2 — CC 对「需审核」消息逐条判定
     • 脚本提取需审核消息到独立批次文件（review_batch_N.txt）
     • CC 每次只读一个批次文件 + 源文件对应行的上下文（前后2行）
     • 逐条判定后写入 JSON 结果文件（review_judgments_batchN.json）
     • 判定完一批 → 写入 → 读取下一批（见陷阱 #116）

   Phase 3 — 数据完整性验证
     • 用验证脚本（参考 templates/batch-verify.py）检查保留+排除覆盖全部源数据
   ```
   **优势**：规则引擎处理 80%+ 明确案例，CC 只需审核 15-20% 不确定案例，大幅减少 CC context 压力。脚本确定性输出（无遗漏），CC 审核结果可追溯（JSON 文件）。**反面案例**：让 CC 直接对 6042 条消息逐条筛选，CC 只处理了 1113 条就报告"全部完成"，1700 条完全遗漏。

### #118. CC context 满后的跨 session 续接——中间 JSON checkpoint 模式（2026-06-11 新增）

118. **CC context 满后的跨 session 续接——中间 JSON checkpoint 模式（2026-06-11 新增）**：当 CC 在多批次任务中 context 耗尽（`API Error: context window limit`）且 `/compact` 后仍无法继续时，需 `/exit` 退出并新建 session 续接。**关键**：不要依赖 CC 的 session resume（陷阱 #111/112 不可靠），而是利用中间输出文件作为 checkpoint——每批完成后写入独立的 JSON 结果文件（如 `review_judgments_batchN.json`），新 session 读取最后完成的 batch 编号即可定位断点。**续接指令模板**：「之前的 session 已完成 batch 1-3 的审核（结果在 review_judgments_batch{1,2,3}.json）。请从 batch 4 开始继续。每次只读一个 review_batch_N.txt，判定后写入 review_judgments_batchN.json，再读下一个。」

### #119. tmux send-keys 快速连发导致 CC 会话名串字（2026-06-11 新增）

119. **tmux send-keys 快速连发导致 CC 会话名串字（2026-06-11 新增）**：多条 `tmux send-keys` 在短间隔内连续发送时（<0.5s），CC 输入框可能将多条消息拼接成一行。如果拼接文本中包含 `/rename` 命令，整个拼接文本会成为会话名（如 `/rename Hermes:审核batch4-7任务：继续对微信群..."长达数百字符）。**判别信号**：CC 执行了 `/exit` 后仍在旧 session 中，或 capture-pane 看到超长会话名。**预防**：(a) 每条 send-keys 后 `sleep 1` 等待 CC 处理；(b) 重要操作（activate、rename）前先 capture-pane 确认输入框干净；(c) 长任务描述用 SCP 文件方式发送而非多段 send-keys。**恢复**：`/exit` 退出 → 重新启动 CC 新 session。

### #120. CC 生成 Markdown 表格格式极度不一致——合并时用 split('|') 不用正则（2026-06-11 新增）

120. **CC 生成 Markdown 表格格式极度不一致——合并时用 split('|') 不用正则（2026-06-11 新增）**：CC 逐批处理数据后输出的 markdown 表格，即使是同类型条目（如 E 排除行），在同一文件中就有 3+ 种格式变体：行号列可能是 `12`/`18-20`/`262-263,266-267`；K 条目的 ID 有纯数字和 K 前缀两种；时间列有 `07:03`/`11:49-50`/`10:02,04`/`05-27 22:32`/`07:34~07:44` 等 6+ 种。**用正则匹配整行几乎不可能覆盖所有变体，会导致反复迭代调正则（实测 7 轮仍未完美覆盖）**。正确做法：`split('|')` 按列访问，对每列值做宽松解析（如行号列用 `split(',')` + `re.match(r'(\d+)(?:-(\d+))?')` 处理每个部分）。详细格式清单和解析代码见 `references/batch-classification-hybrid.md` §Phase 4。

### #121. 大数据合并验证：K未匹配条目由规则引擎兜底，不影响总数（2026-06-11 新增）

121. **大数据合并验证：K未匹配条目由规则引擎兜底，不影响总数（2026-06-11 新增）**：将 K 条目匹配回源文件行号时，部分条目因时间格式特殊（如 `16:25-17:09,17:22-25` 大范围 + 多发送者合并行）无法精确匹配。**不要在匹配策略上过度投入**——这些未匹配 K 条目对应的源文件消息会落入"遗漏"集合，由规则引擎重新分类，最终结果完整且无重复。验证重点应是：`输出文件行数 = 源消息总数` + `排除行号无重复`，而非 K 匹配率 100%。

116-legacy. **PowerShell `$_` 变量通过 SSH 传输时被替换为 `<cloud-home>`（2026-06-11 新增）**：通过 SSH 单引号传递 PowerShell 命令时，`$_` 会被 bash 的 SSH 传输层替换为本地 home 路径（`<cloud-home>`）。双引号、heredoc 也有类似问题。**Workaround**：(a) 用 Python 脚本替代 PowerShell（`python -u -c "..."`）；(b) 将脚本写入文件后 SCP 到 Windows 再执行（最可靠）；(c) 用 `glob.glob` 处理中文文件名避免编码问题。反面案例：本次花费 10+ 分钟尝试各种 PowerShell 语法（单引号/双引号/heredoc/cmd/echo pipe），全部因 `$_` 替换或中文编码问题失败，最终改用 Python 脚本 + SCP 方案一次成功。

### #122. CC Search 工具对大文件执行时导致整个进程完全冻死（2026-06-11 新增）

122. **CC Search 工具对大文件执行时导致整个进程完全冻死（2026-06-11 新增）**：CC 使用内置 Search 工具在**大文件**（实测 ~2440 行）上搜索模式字符串时，可能导致 CC 进程**完全冻死**——capture-pane 显示的时间戳停滞不动（如 3m48s 持续数分钟无变化），C-c×3 完全无效，即使 accept edits 本身未阻塞。这与陷阱 #42（accept edits 阻塞）不同——**这是 Search 工具自身的 hang，不是输入通道问题**。

   **判别信号**：capture-pane 显示 `Searching for N patterns, reading 1 file…` 或 `● Searching for 1 pattern…` + 时间停滞（≥60s 不变）+ C-c×3 无反应。

   **预防**：在 TASK 指令中，如果 CC 需要在>1000行的文件中搜索特定内容，明确要求「**不要使用 Search 工具搜索大文件**，改用 Read 工具指定行号范围读取，或用 Python 脚本做正则搜索」。如果数据已提取到 JSON/结构化文件中，让 CC 直接读取结构化文件而非回源文件搜索。

   **恢复**：与陷阱 #42 相同——直接 `tmux kill-session -t claude-session` 重建，比在冻死的 session 中尝试恢复快得多。

   **反面案例（2026-06-11）**：CC 在 2440 行的 `法律AI加油站_保留消息_完整内容.md` 中搜索 `**说明**:` 模式，进程冻死 5+ 分钟，C-c×3 无效，只能杀 tmux 重建。

### #123. CC 长分析输出超出 tmux capture-pane 缓冲区——用文件写入绕过（2026-06-16 新增）

123. **CC 长分析输出超出 tmux capture-pane 缓冲区——用文件写入绕过（2026-06-16 新增）**：当 CC 产出数千字的详细分析/审阅意见时，`capture-pane -S -100` 甚至 `-S -3000` 都无法捕获完整内容——tmux 的 pane 缓冲区有限，且 capture-pane 返回的是 pane 中的可见行数（受 tmux 窗口高度限制），超大输出会被截断。**判别信号**：capture-pane 返回的内容在关键段落处突然中断（如"待讨论问题 2 和 3"只出现了开头没有结论），连续多次 capture-pane 结果不变。**可靠 workaround**：立即用短 send-keys 让 CC 把完整输出写入文件（如"请把刚才的完整审阅意见写入 C:\\Users\\<ssh-user>\\review-output.md"），然后 SCP 到云端读取。这是获取 CC 长输出的最可靠方式——比反复尝试不同 `-S` 参数高效得多。**预防**：如果预期 CC 会产出大量分析内容（如"逐节点评方案六部分"），在原始 TASK 指令中就要求"完成后将完整分析写入 C:\\Users\\<ssh-user>\\<文件名>.md"。

### #125. 新任务不得进入 CC 现有对话——必须先退出再新建（2026-06-17 新增）

125. **新任务不得进入 CC 现有对话——必须先退出再新建（2026-06-17 新增）**：当需要与 CC 讨论或执行一个全新的任务时，**绝对不能直接在 CC 正在进行的对话中发送消息**——这是两个独立任务的上下文混入，会导致 CC 在旧任务上下文中处理新任务。**正确流程**：(a) 如果 CC 正在运行且在新任务的对话中 → 直接发消息即可（b) 如果 CC 在另一个任务的对话中 → 先 `/exit` 退出 → 等回到 bash → `cd /d ` → `claude --model glm-5.2` → 激活四步法 → 再发新任务。**判别方法**：capture-pane 看到 CC 的输出内容与当前新任务无关（如法律WIKI质量检查输出 vs 文件审核Skill讨论），说明 CC 在另一个对话中。**反面案例（2026-06-17）**：Hermes 直接进入 CC 正在做法律WIKI Chapter 7 质量检查的对话，开始发文件审核Skill讨论的内容，用户立即纠正。

### #126. 活跃讨论中的每轮协议纪律（2026-06-18 新增）

126. **活跃讨论中的每轮协议纪律（2026-06-18 新增）**：CC 连接成功并进入活跃讨论后，**每发送一条消息都必须遵守协议**。常见的松懈模式：连续发多条消息而不做空闲检查、不加状态摘要、不等 ACK 确认。用户指出交流方式没按照协作 skill 来。**强制规则**：已建立 CC session 后的活跃讨论中，每条消息发出前必须：(a) 两步空闲确认确保 CC 空闲；(b) 状态摘要 [state:...] 附在消息末尾；(c) 短消息用 send-keys 分批发送（间隔 >= 3s），每批后 capture-pane 确认送达。**反面案例（2026-06-18 文书校对v2讨论）**：Hermes 在 CC 确认「请说」后连续发送 3 条消息无间隔检查、无状态摘要，用户指出交流方式不符合协作 skill。

### #127. Hermes 发送指令前必须提供完整背景文件路径（2026-06-22 新增）

127. **Hermes 发送指令前必须提供完整背景文件路径（2026-06-22 新增）**：当通过飞书群向 CC 派发任务或讨论时，**指令中必须包含 CC 需要读取的文件路径**（本地 Windows 路径，如 `D:\\claude vscode\\...`）。CC 没有 Hermes 的云端上下文，不能假设 CC"天然知道"背景。如果任务涉及某个 Skill 或项目，必须在第一条消息中就写上 `请先读取技能：D:\\...\\SKILL.md`。反面案例（2026-06-22）：发知识库流程讨论时没带技能位置，CC 在无背景下做了无效分析，用户指出「回复是无意义的」。：当用户要求「让 CC 用 skill-creator」时，不能简单地发「用 /skill-creator」然后等 CC 自己决定做什么。CC 可能自动启动 Explore agent 搜索本地文件，而非立即调用 `/skill-creator`。正确流程：(a) 在指令中明确写「先 Read 现有的 SKILL.md 和相关 references 文件了解现状，然后直接调用 /skill-creator 来创建/更新」；(b) 如果 CC 已开始 Explore，立即 C-c 打断，重新发包含「直接调用 /skill-creator」的指令；(c) CC 加载 /skill-creator 后进入 interview 流程，用数字键+两拍法选择选项。**反面案例（2026-06-18）**：用户说「让cc加载它的skil creator技能」，Hermes 发消息后 CC 启动 Explore 搜索文件，跑了 1 分钟才被 C-c 打断重定向。

### #128. Plan mode 中 interview 选项编号绑定到 checkbox 状态（2026-06-18 新增）

128. **Plan mode 中 interview 选项编号绑定到 checkbox 状态（2026-06-18 新增）**：Plan mode interview 表单中，选项编号是动态绑定的——前面 checkbox 选中/未选中状态会改变后续选项的编号偏移量。例如有 4 个 checkbox 时选项 5 = Chat about this、选项 6 = Skip interview；但如果 checkbox 被减少了，编号可能变成 4 = Chat about this。单次 send-keys 可能选到非预期项。**预防**：(a) capture-pane 先检查当前表单结构确认编号映射；(b) 优先选 Chat about this 或 Skip interview（最后一项）；(c) 选择后 capture-pane 验证 CC 响应——如果 CC 的回答与预期不符，说明编号错位，需 Escape 取消后重新选择。**反面案例（2026-06-18，两次触发）**：两次 send-keys 4 都被 CC 解释为选项 1「你来设计实施步骤」，实际是 checkbox 状态改变了编号映射。

### #129. 当用户说「cc知道的」时直接信任，不要追问

129. **当用户说「cc知道的」时直接信任，不要追问**：用户明确说「cc知道的」后，不要再追问细节（如「仓库URL是什么」「token在哪」）。用户的意思是 CC 应有足够上下文自行处理。直接启动 CC 做任务，CC 若真缺信息会追问，届时再反馈用户。反面案例（2026-06-19）：用户说「cc知道的」，Hermes 仍问「legal tools 的 GitHub URL 是什么？」

### #130. CC 自述的权限分析不可全信（2026-06-21 新增）

130. **CC 自述的权限分析不可全信（2026-06-21 新增）**：CC 在被问到「权限风险」时，会检查自己的 `settings.json` 并基于 `permissions.allow` 中的 Write/Edit 预授权数给出分析。但它**完全忽略** bridge 层的 `config.json` 中的 `permissions.defaultAccess` 设置。

### #131. 辩论未闭环不得汇报用户（2026-06-22 新增）

131. **辩论未闭环不得汇报用户（2026-06-22 新增）**：收到 CC 回复后，必须先：
    (a) 独立分析 → 找出质疑点
    (b) 发回 CC 辩论（R2）
    (c) CC 回应后评估 → 闭环
    (d) **然后**才汇报用户
    
    **反面案例（2026-06-22）**：收到 CC 对知识库协作流程的 5 个缺口的分析后，Hermes 整理了结论直接汇报给用户（虽然附带了「我觉得合理」的分析），用户指出「你还没有与cc进行debate」。即使独立分析了，没有发回 CC 辩论再评估，还是传话。

### #132. 讨论步骤纪律——先跟一个 Bot 充分讨论完再发下一个（2026-06-22 新增）

132. **讨论步骤纪律——先跟一个 Bot 充分讨论完再发下一个（2026-06-22 新增）**：当任务需要与多个 Bot（CC、芭迪）讨论时，必须按顺序逐个讨论，**先跟一个充分辩论闭环后，再发下一个**。绝不在 CC 未回复/未闭环的情况下同时发芭迪。

    **反面案例（2026-06-22）**：CC 第一条消息不带技能位置发出后，不等 CC 读完回复，就跳步发芭迪消息（还写了云端路径 `~/knowledge-base-collab-plan.md` 让芭迪本地读不到）。用户指出「你不应该先跟CC讨论完再说吗」。

### #133. 发送任务给 CC/芭迪时必须包含本地技能文件路径（2026-06-22 新增）

### #135. CC PreToolUse hook 连续报错——文件操作本身成功（2026-06-27 新增）

135. **CC PreToolUse hook 连续报错——文件操作本身成功（2026-06-27 新增）**：CC 的 `~/.claude/settings.json` 中配置了 PreToolUse hooks（如 `validate-memory-ask.ps1`、`validate-mcp.ps1`），每次 CC 执行 Write 或 Edit 工具调用时这些 hook 会运行并报错（`PreToolUse:Write hook error` / `PreToolUse:Edit hook error`）。**关键：文件操作本身全部成功，hook error 不影响功能。** 监控时看到此类错误不需要干预——这是 CC 侧 hook 脚本自身的问题（可能是脚本逻辑错误、依赖缺失、或 PowerShell 兼容性），不是 CC 工具调用的失败。**但需要注意**：连续的 hook error 会让监控中的 capture-pane 输出充满错误信息，可能淹没真正的工具调用输出。若 CC 正在部署新 hook（如 IM 同步方案），应先排查现有 hook error 原因，否则新 hook 的错误信号会被噪音淹没。排查方法：让 CC 检查 `settings.json` 中 PreToolUse hooks 的 `command` 和 `matcher`，逐个禁用测试定位问题 hook。

### #136. CC Stop hook stdin 不包含回复文本——需额外读 jsonl 尾部（2026-06-27 新增）

136. **CC Stop hook stdin 不包含回复文本——需额外读 jsonl 尾部（2026-06-27 新增）**：当为 CC 构建 IM 同步方案时（方案 1：Hook 驱动），可能假设 Stop hook 的 stdin 包含 CC 最后一条 assistant 回复文本。**实际 stdin 只包含 `session_id` 和 `transcript_path`（jsonl 文件路径），不含消息内容。** 要获取 CC 的回复文本，hook 脚本必须：(a) 从 stdin 解析 transcript_path；(b) 读取该 jsonl 文件尾部；(c) 提取最后一条 `role: "assistant"` 消息的 `content` 字段；(d) 处理可能的 content 格式变体（纯字符串、数组含 text block）。**脚本复杂度远超 CC 最初估计的 ~50 行**——实际需要 150+ 行（含错误处理、编码处理、content 解析）。CC 在 IM 同步报告中将 Stop hook 方案设计为"stdin 直接读取回复文本"是概念错误。详见 `references/cc-hook-data-schemas.md`。

133. **发送任务给 CC/芭迪时必须包含本地技能文件路径（2026-06-22 新增）**：当发送的任务需要对方了解特定技能/流程时，必须在消息中明确给出该技能的**本地实际文件路径**（Windows 绝对路径如 `D:\\\\claude vscode\\\\...`），不能依赖对方「已经知道」或给出云端路径。

    **反面案例（2026-06-22，两次触发）**：
    - 给 CC 发知识库流程审查消息时只说了「用户设计了一个流程」没给技能位置 → CC 的初步审查无意义
    - 给芭迪发消息时写了云端路径 `~/knowledge-base-collab-plan.md` → 芭迪本地看不到
    - 正确做法：`请先读 D:\\\\claude vscode\\\\法律相关skill自研仓库\\\\法律概念提取与建页\\\\SKILL.md`

### #137. CC 概念混淆——compact ≠ 索引压缩（2026-06-27 新增）

137. **CC 概念混淆——compact ≠ 索引压缩（2026-06-27 新增）**：CC 在分析自己的记忆/存储架构时，可能把两个不同机制混为一谈：
   - **compact（上下文压缩）**：CC 的 auto-compact 是压缩当前 session 的 token 上下文窗口，生成有损摘要，但原始 jsonl 文件完整保留所有消息（0 丢失）
   - **claude-code-memory-setup 的索引压缩**：独立工具对 jsonl 文件做后处理，提取元数据/关键词写入独立索引文件（如 Claude Sessions 插件的 distilled/ 目录）

   CC 可能声称"compact 后消息会丢失"或"索引压缩就是 compact"，这是概念错误。**Hermes 监控中遇到 CC 对这两种机制做等价推理时，应立即质疑纠正**——compact 只影响上下文窗口，jsonl 文件是金矿不是累赘（完整保留所有原始消息）。此混淆在本轮 Claude Sessions 插件安装与 jsonl 完整性分析中被观察到。

### #138. CC 斜杠命令对空格敏感——前导/多余空格导致命令不被识别（2026-06-27 新增）

138. **CC 斜杠命令对空格敏感——前导/多余空格导致命令不被识别（2026-06-27 新增）**：CC 的斜杠命令（`/rename`、`/compact`、`/mcp`、`/resume`、`/exit` 等）对输入中的前导/多余空格敏感。如果用户（或 Hermes 通过 send-keys）发送的命令中包含前导空格（如 ` /rename xxx`）或命令参数中有额外空格，CC 可能不会将其识别为内置命令，而是当作普通消息处理。**判别方法**：`/rename` 成功时 CC 返回 `⎿  Session renamed to: xxx`；若 capture-pane 中无此确认行且 CC 将命令文本当作普通输入回复，说明命令未被识别。**预防**：(a) send-keys 发送斜杠命令时确保无前导空格；(b) 发送后立即 capture-pane 确认 CC 回显了预期响应（如 `Session renamed` / `Compacting...`）；(c) 若未识别，Escape 清空输入框后重新发送无空格版本。**反面案例（2026-06-27）**：用户在 CC 输入框中输入了带前导空格的 `/rename CC×Obsidian/调研 - 选型与可行性`，CC 无响应（命令未被识别），用户以为 rename 成功，后续才通过扫描 jsonl 发现 custom-title 未增加。

### #134. 自言自语监控模式——禁止后台进程、禁止退出 turn（2026-06-26 新增）

134. **自言自语监控模式——禁止后台进程、禁止退出 turn（2026-06-26 新增→2026-06-27 强化）**：当用户要求"持续监控"CC 对话（自言自语监控模式，§10）时：
   - **禁止用 `terminal(background=true)` 启动后台监控脚本**——后台进程把轮询控制权交给 Hermes 通知系统，无法在 turn 内持续输出自言自语。必须用 **turn 内 sleep + capture-pane 循环**。反面案例（2026-06-26）：Hermes 写了 `monitor_cc.sh` 脚本用 `terminal(background=true)` 启动后台监控，用户立即纠正「不是后台监控，是你直接同turn监控」。
   - **禁止退出 turn**——在用户说"停止"/"结束监控"前，Hermes 绝对不可结束当前 turn。轮询可以拉长间隔（15-20s），但不可以回复一句总结后退出。反面案例（2026-06-26）：Hermes 轮询两轮后回复「CC 空闲，等你操作」然后结束 turn，用户严厉纠正「你为什么擅自退出turn...在我表示停止前，不中断监控」。
   - **⚠️ 「询问hermes」信号必须以 💭/📋 前缀回复，严禁切出监控模式（2026-06-27 用户明确纠正）**——即使 CC 无法联系 Hermes、即使回复内容很重要、即使用户看起来在等待正式回答，都必须在监控格式内（💭/📋 前缀）回复后继续轮询。不得以正常对话格式直接回复、不得结束 turn 等用户回应。此规则在 monitoring-mode.md §常见场景处理 有详细示例和自检步骤。反面案例（2026-06-27）：用户在 CC 输入框中输入"询问hermes"后，Hermes 切出监控模式以正常对话格式给出了项目归类建议，用户立即纠正「你没有遵循监控模式中提问的要求」。
   - **用户直接在 CC 输入框打字时继续监控**——不要因为看到用户在编辑输入就停止轮询。

   详见 `references/monitoring-debate.md` §10。

133. **发送任务给 CC/芭迪时必须包含本地技能文件路径（2026-06-22 新增）**：当发送的任务需要对方了解特定技能/流程时，必须在消息中明确给出该技能的**本地实际文件路径**（Windows 绝对路径如 `D:\\claude vscode\\...`），不能依赖对方「已经知道」或给出云端路径。

    **反面案例（2026-06-22，两次触发）**：
    - 给 CC 发知识库流程审查消息时只说了「用户设计了一个流程」没给技能位置 → CC 的初步审查无意义
    - 给芭迪发消息时写了云端路径 `~/knowledge-base-collab-plan.md` → 芭迪本地看不到
    - 正确做法：`请先读 D:\\claude vscode\\法律相关skill自研仓库\\法律概念提取与建页\\SKILL.md`

    **典型案例**：CC 说「Write/Edit 0 预授权 → 写文件会卡弹窗」，但实际桥 mode 下 `defaultAccess=full` 全局绕过了 settings.json，所有写文件畅通无阻。

    **排查顺序**（事实优先于分析）：
    ```
    ① 实际验证：发一个写文件的任务，看 CC 是否真卡在弹窗上
    ② bridge config：<windows-userhome>\.lark-channel\config.json → permissions.defaultAccess
    ③ settings.json：<windows-project-root>\.claude\settings.json → permissions.allow
    ```

    **适用场景**：任何涉及 CC 权限分析的讨论（P 模式风险、bypass、弹窗问题）。不要直接采纳 CC 的权限结论，先实际验证再下判断。

    详见 feishu-agent-collab skill 的 references/credentials.md（凭据集中）和 badi-workflow.md（bridge 工作流）。
