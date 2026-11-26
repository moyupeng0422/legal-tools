# 飞书多 Agent 协作协议 v1.8（2026-11-23 定稿）

> 八轮辩论（R1-R8）+ 端到端联测 + CC 审查的最终产物。
> 本文件是 Hermes 与芭迪（WorkBuddy）的**双方共同契约**：云端副本在
> `multiagent-feishu-scripting/references/protocol-v1.8.md`，芭迪侧副本由 Hermes 推送同步，
> 内容以本文为准，修改须经双方确认。

## §0 核心原则

1. **交互由 Hermes 发起和持有**：所有 Hermes↔芭迪交互由 Hermes 派任务并持有（派任务→sleep 等待→处理）。芭迪永远是响应方，**禁止主动 @ Hermes、法律助手、家庭助手**（三者同为 Hermes gateway 同源 profile，@ 会拉起对方失控的群房间 session，用户无法介入中止；家庭助手同源实证 credentials L13，风险相同）。@ CC 不受限（CC bridge bot 在群内，互 @ 无失控风险）。
2. **零机械原则**：芭迪侧不出现多步技术操作——写 conv 用自然语言、推送用单命令 ps1、发卡是框架行为。LLM 的 token 只花在真正的工作和叙事上。
3. **脚本管事实，LLM 管判断**：机械操作全脚本承载；验收/分型/升级等判断永远由 LLM 做，脚本永不越权。
4. **水平触发全量对账**：Hermes 每次醒来处理起点=全量扫描（看板+conv+群消息），永不依赖单条触发事件。
5. **对账是唯一裁判**：等待/轮询脚本只是加速器，加速器死了不改变裁判结果。

## §1 通道与信号

| 通道 | 性质 | 说明 |
|---|---|---|
| 群卡片（interactive） | **唯一唤醒信号** + 回合边界 | 芭迪发完卡片=本轮彻底完成。**卡片正文 API 不可读**（实测：只有 fallback 占位符），仅元信息可用（sender/msg_type/ts） |
| 群纯文本 | 异常叙事唯一可读通道 | 芭迪框架默认发卡片无法改；**异常/权限/失败事件必须附带纯文本双发**（格式：`[权限]`/`[异常]`/`[失败]` + 一句话摘要）。干净完成文本可选 |
| conv 文件 | 内容权威（叙事细节） | 芭迪每次回复（**无论讨论还是执行**）都写 conv；`badi_finish.ps1` 推送到云端 `conv_inbox/` |
| 看板 JSON | 状态权威 | 登记（agent-send hook 自动）/ 闭环（Hermes 验收后） |
| A2A 端点（<cloud-tailscale-ip>:9900） | **休眠** | 端点保留（token 有效性不变），芭迪不强制调用；未来需要同步回执场景再启用 |

### 信号时序不变量

- **完成卡 ⇒ 回合完成、产出全部就位、conv 已推送**（框架语义保证）
- **权限卡/进度卡 ⇒ 回合仍在进行**（回合中段产物）
- 芭迪 finish 序列锁定：**写 conv → ps1 推送 → 发卡片（最后）**——卡片出现 ⇒ conv 必然已就位
- 卡片信号触发 Hermes 唤醒 → 醒后查 conv/板**后置分型**（完成/权限/进度），root_id 仅作先验

## §2 芭迪侧职责（零机械操作）

1. **产出落到任务指令约定的位置**（Hermes 派任务时写明路径）
2. **每次回复写 conv**（讨论类和执行类**相同流程**，无例外——卡片正文不可读，conv 是唯一可读输出通道）
3. **调 `badi_finish.ps1` 推送 conv**（含校验重试，见 §4）
4. **发群完成卡片**（框架回合边界，最后一步）
5. **异常/权限/失败**：卡片 + 纯文本双发（`[权限] 卡住原因一句话`）
6. **ps1 非零 exit 必须重调脚本**，不得继续结束回合

### §2.1 conv 落盘路径与 ps1 调用（芭迪侧操作细节）

- conv 本地落盘路径：`D:\<workbuddy-root>\collab\hermes-badi\conv\`（2026-11-23 迁移自 CC 工作空间；文件名 `conv_<task>_<YYYYMMDD>.md`，追加用同文件）
- ps1 调用示例：`powershell badi_finish.ps1 -TaskId <id> -Step <n> -ConvPath <conv路径>`
- DryRun 模式：`-DryRun` 只生成/校验不真推不发（测试期用）

## §3 Hermes 侧职责

### 派发
1. 任务起草（写明产出约定路径）
2. `agent-send.sh` 发卡（hook 自动登记看板+账本）
3. `badi-wait.py --task <id>` 进入 sleep 等待（30s 群消息轮询）

### 醒后原子序列（跳过验收直接闭环 = 最大漏洞）
1. `hermes-post-task.sh verify -TaskId <id> -RemotePath <产出路径>` —— 机械校验（conv 就位/产出存在/清单核对），输出结构化材料
2. **LLM 读材料做验收判断**（判断闸门）
3. `hermes-post-task.sh close -TaskId <id> -Verdict pass|fail` —— 闭环或转异常
4. conv 归档确认 + 需要时汇报用户

### 闲置期（无 badi-wait 运行时）
唤醒源只有用户消息/定时任务。STALL 退化为时间戳补判：下次唤醒时发现任务派发已超时 → 催办/升级。

## §4 badi_finish.ps1 规格（芭迪侧改造）

- **删**：状态文件（status.json）更新逻辑（下游读者已全部退役）
- **留**：SSH 推 conv + 账本更新
- **加**：推送校验（远端存在性检查）+ 瞬时故障 3 次退避重试（2/4/8s）；确定性拒绝（文件名非法/超限/**同名已存在=幂等成功**）立即定性不重试
- **不变量**：卡出现 ⇒ conv 已在校验过的远端就位
- 推送彻底失败：发纯文本 `[推送失败] <task-id>`（可读告警，替代沉默）+ exit 非零

## §5 异常处理

| 场景 | 处理 |
|---|---|
| 权限卡 | 即时介入（非 STALL，不进梯子计时） |
| STALL 10min | badi-wait 内梯子触发 → turn 内催办芭迪 |
| STALL 30min | 发卡升级用户 |
| 等待超时（cap=min(20段，迭代-15)） | 全量对账 → 板标 dispatched-no-report → 撤单重派或告知用户 |
| SSH 断 | 板标 `completed-unverified`（不闭环）→ 验收入队 → 下次唤醒重试 |
| 卡发但 conv 缺席（真孤儿） | 等一轮轮询 → 群文本催芭迪重推 → 板标 exception；累计 ≥3 次 → 协议健康告警 |
| 卡片不匹配任何在飞任务 | 记日志继续等待（非致命） |
| **权限卡**（卡片+conv 缺失+任务非终态） | **不判纪律违反**：芭迪 pending 时自行绕开权限阻塞继续任务（2026-11-23 实测：换密钥副本+-F config），Hermes 重新 sleep 等下次卡片唤醒。**连续计数纪律：同样情况（只有卡片没有 conv）≤2 次容忍；连续第 3 次 = 发卡片问询情况**。pending 分支她侧无信号（回合冻结无 conv 无文本），"拒绝"分支她有错误文本可继续；"始终允许"后沙箱会话级整体绕过（escalation-approved，范围宽于按类授权）。权限卡由框架自动发（非 LLM 回合产出），无纯文本可附——"权限=卡片+纯文本双发"条款对此类不适用 |

## §6 看板状态机

- 登记：`dispatched`（agent-send hook 自动）
- 验收通过：`closed`（Hermes 单动作，唯一写入者）
- 验收失败：`exception`
- SSH 断：`completed-unverified` →（补验收）→ `closed`
- 未回报超时：`dispatched-no-report`

## §7 工具链清单

| 工具 | 侧 | 用途 |
|---|---|---|
| `agent-send.sh` | 云端 | 发卡引擎（登记 hook + 账本 + 串行闸门） |
| `badi-wait.py` | 云端 | 同 turn 阻塞等待（单信号：群消息 30s + 梯子 + cap） |
| `hermes-post-task.sh` | 云端 | 醒后两段式（verify 机械校验 / close 判断后闭环 / brief 快照） |
| `collab_board.py` | 云端 | 看板 CLI（含 unverified 两转换） |
| `badi_finish.ps1` | 芭迪 | conv 推送 + 账本（校验重试版） |

## §8 历史裁定索引

- A2A POST 移除（R7）：端点休眠，结构化信号迁入 conv 模板
- 卡片只触发永不核销（R6）：卡片零内容，物理上无核销资格
- 禁止芭迪主动 @ Hermes、法律助手、家庭助手（2026-11-23 事故；三者同源 gateway profile，法律/家庭为同源推断保守禁止）：群房间 session 用户无法中止
- 心跳/守护进程禁令（R1-R4）：无常驻进程承担正确性职责
- 已退役脚本：board-listener/board_watch/board_derive/board_sentinel/badi_watch/agent-wait/a2a_wake_watch（`_retired_v18/` 归档，可回滚）
- 协作目录迁移（2026-11-23 用户裁定）：芭迪协作根迁至 `D:\<workbuddy-root>\collab\hermes-badi\`（权限隔离硬边界），旧址归档于 `D:\<projects-root>\collab\_migration_archive_20261123\`；云端 WIN_CONV_DIR/agents.conf 已联动
- desens_check 语义重定义（用户拍板）：buddy 报告仍填 true＝按 buddy 权限边界自查（全开放视图免脱敏）；evidence≥1 强制不变
- 定稿类文档字数口径先问清："N 字"是中文字符还是总字符（2026-11-23 agent.md 曾按中文字符口径交付后被纠正为总字符≤1500，返工重压；终稿总字符 1375 达标）
- 权限卡=纯卡片无纯文本（wm-collab-e2e-test 实测 2026-11-23）：WorkBuddy 框架自动发权限卡（非 LLM 回合产出），无法附纯文本——与 §1 "权限事件双发"预期不符；由此产生「卡片⇒conv 缺席」误判（Hermes 两次催促后用户澄清是权限卡住）。分型规则补充：**卡片到达但 conv 缺席 ≠ 纪律违反，先排除权限卡**（连续多卡无 conv 更指向权限/进度卡）；待讨论改进：权限卡发出前先 conv 提示的可行性（框架弹窗时机 LLM 能否插入动作待芭迪确认）
- 工作管理三端查询 MCP 化定式（2026-11-23 实测闭环）：查询=三端同一套 MCP 接口（Hermes 云端 wm_mcp_server.py 已注册 config.yaml mcp_servers、芭迪 wm-local role=buddy 全量、CC 脱敏视图）；写入=Hermes 独占脚本链（template_cp/wm_row/patch+操作日志铁律），MCP 纯只读无写工具。buddy tr 报告提案制端到端已验证（真实查询发现泰陌案字段列表残留→提案→lint→submit→Hermes applied→MCP 复验），buddy 推送密钥=authorized_keys 绑 wm_inbox_recv + 私钥 D:\<workbuddy-root>\.ssh\reports_push_buddy，调用格式 `ssh ... "wm_inbox_recv tr-XXXX.md" < 文件`（裸文件名会被格式校验拒），云端落点 ~/.hermes/reports/inbox_push/
- 权限弹窗处理机制收敛（2026-11-23 permission-card-discuss，用户提供弹窗原始样式）：post-exec escalation=命令执行中拦截非跑完才拦（实证：lint/inbox 已推进，ssh 触碰受保护路径时升级上报）；"拒绝"分支以工具错误文本返回、LLM 同回合继续不被挂起；allow_always 授权主体=用户 GUI 操作。落地三项：①芭迪侧 skill §七固化 pending-op 哨兵纪律（ssh-push/privilege/acl/ext-file/wm-write 五类，"可能敏感即写、覆盖优先于精度"）②协议本节权限卡分型（Hermes 已补）③allow_always 白名单建议已转用户（放 wm-local 只读/lint/ps1，不放 submit/提权/ACL）。D/F 归框架诉求（审批卡带 conv 锚点/卡片类型前缀）待用户向 WorkBuddy 反馈；agent.md 落盘已由用户完成（C:\Users\<windows-username>\.workbuddy\agent.md，唯一实证注入位置）
- 权限 pending 最终机制（2026-11-23 晚用户拍板，代批链路实测后收敛）：代批链路实测证明 **Bot 群消息不能在框架层解锁审批**（Hermes 回"允许"不被接受）——代批方案技术不成立。最终分工：**芭迪 pending 时自行绕开**（换方案/路径/密钥，不等待审批，铁律入她 skill §七含 approval-plan 语义重定义：self 绕开为主，hermes/user 仅作风险标注/事后通报）；**Hermes 连续计数容忍**：只有卡片没 conv ≤2 次 sleep 等待不催不误判，**连续第 3 次=发卡片问询情况**（badi-wait 已自动化：`--card-no-conv` 计数/`--reset-card-count` 清零，≥3 自动输出 CARD_STREAK 告警）。未预告的权限请求一律按 high/转用户处理（兜底原则）
- wm skill 三端齐备（2026-11-23 深夜）：芭迪侧 work-management skill 已建成（`C:\Users\<windows-username>\.workbuddy\skills\work-management\`，SKILL.md 五块+data-model-buddy.md，从 CC 侧精简为查询+提案最小集，实测 wm_stats 通过）；此前遗漏根因=agent.md 讨论时定"位置定稿后一起建"被后续任务挤掉排程——**联动任务要在当次任务卡内一并派发，不得拆到"以后再建"**。协议 refs 同步时序：Hermes 推 pair 根后芭迪按 skill 流程 SHA256 对齐（中间版本会出现，以最终对齐为准）

## §9 辩论制（持续义务，承自 v1.6b/v1.7.1 §9，2026-11-23 复发事故后补回）

**背景**：v1.8 重写时本节遗漏，导致 2026-11-23 agent.md 讨论 Hermes 收芭迪 R1 后跳过 R2 直接汇总用户（传话筒违规复发）。补回并永久生效。

1. **方案级交换必辩论**：任何方案/协议/架构类讨论，收到对方意见后必须先独立核验（不轻信其事实断言）→ 发 R2（确认/质疑+立场）→ 等 R3 收敛 → 才汇总用户。跳步=传话筒违规。
2. **采纳必须带独立验证**：采纳对方结论前，对其中的事实性断言用工具复核（路径/成员/配置类硬事实一律 API/实证核验，不可凭对方转述）。
3. **修改告知必须发回确认**：修改对方提出的方案细节后，发回对方确认再实施。
4. **豁免**：纯执行回报（任务完成通报）不触发辩论——但结果类回报仍须验收动作（hermes-post-task verify+LLM 判断）。
5. **辩论强制写 conv 段落**，禁止仅卡片口头；R 编号沿用 `### R1/R2/R3 (方): 内容` 格式。
6. **需用户拍板的项**：提炼是我的义务，不是跳过辩论的理由——先辩论收敛分歧，拍板项单列提请用户。
