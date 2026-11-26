# 脚本资产对照清单（v1.8 终版，2026-11-23）

> CC 审查确认（R9）：复用 3 / 改造 3 / 新建 2 / 退役 7。缺的不是脚本，是醒后环节聚合入口。
> 2026-11-23 晚更新：芭迪侧 ps1 v2.0 已交付+skill 化完成（见底部两节）。

## 按流程环节

### 派发侧（Hermes 发起）
| 环节 | 执行者 | 脚本 | 状态 |
|---|---|---|---|
| 任务起草/产出路径约定 | Hermes LLM | 对话直接写 | 不变 |
| 发任务卡+看板登记+账本 | 脚本 | `agent-send.sh`（hook 自动登记） | ✅ 复用 |
| 阻塞等待 | 脚本 | `badi-wait.py` v2.0 单信号（群消息 30s） | 🔧 已改造 |

### 芭迪侧
| 环节 | 执行者 | 脚本/形态 | 状态 |
|---|---|---|---|
| 收卡干活+产出落约定位置 | 芭迪 LLM | 纯自然行为 | 不变 |
| 写 conv（讨论/执行同一流程） | 芭迪 LLM | 直接写本地 markdown | 不变（用户裁定保留） |
| 推送 conv+账本 | 脚本 | `badi_finish.ps1` v2.0：四分类+退避+IDEMPOTENT_SKIP+DryRun | ✅ 已交付验收 |
| 发群完成卡片 | 芭迪框架 | 回合边界自然行为 | 不变 |

### 接收侧（Hermes 醒后）
| 环节 | 执行者 | 脚本 | 状态 |
|---|---|---|---|
| 检测群消息→退出等待 | 脚本 | badi-wait（内嵌 ListMessage 轮询） | 🔧 已改造 |
| 醒后状态快照 | 脚本 | brief（hermes-post-task.sh brief） | 🆕 已建 |
| 拉产出+机械校验 | 脚本 | `hermes-post-task.sh verify`（两段式第一段） | 🆕 已建 |
| 验收判断 | Hermes LLM | 读 verify 材料——判断闸门 | 不变 |
| 看板闭环/conv 归档 | 脚本 | `hermes-post-task.sh close`（两段式第二段） | 🆕 已建 |
| 用户沟通/升级 | Hermes LLM | agent-send.sh | 不变 |

## 资产处置

| 处置 | 脚本 | 说明 |
|---|---|---|
| ✅ 复用 | agent-send.sh / agent-conv.sh / collab_board.py / cc-send.sh / cc-wait.sh | 路径硬编码多处，物理留全局 |
| 🔧 改造完成 | badi-wait.py v2.0（单信号）/ collab_board.py（unverified 转换） | |
| ✅ 芭迪侧已交付 | badi_finish.ps1 v2.0（四分类/退避2-4-8s/IDEMPOTENT_SKIP/DryRun/纯文本告警） | 芭迪自行实施，Hermes 七项实质核查全过 |
| 🆕 已建 | hermes-post-task.sh（verify/close/brief 三段）/ brief 生成器 | |
| ⚰️ 退役归档 | board-listener.py / board_watch.sh / board_derive.py / board_sentinel.sh / badi_watch.sh / agent-wait.sh / a2a_wake_watch.py | `scripts/_retired_v18/` |

## 实测锚点

- badi-wait v2.0：查板快路径✅ / 群卡片检出✅（真实卡片 <message-id>）/ 超时路径✅
- hermes-post-task：brief✅ / verify（conv 就位+产出可达）✅ / close unverified✅ / close pass✅
- 端到端联测（v18-e2e-test，历史记录——当时仍是三路信号版）：派发→等待45s→audit信号→reported→confirmed→closed 全链路✅（单信号版联测=v18-badi-side 讨论任务，group_card 信号触发✅）
- 新机制实战两连：badi-side-v18-impl（11s 信号触发→ps1 v2.0 验收闭环）/ badi-skillify（~6min 信号→skill 化验收闭环），均走完整「发卡→sleep→醒后原子序列→closed」
- ListMessage：1.15s 返回，sender 白名单可区分 Hermes(cli_aa9325...) 与芭迪(cli_aa9408...)

## 文档同步纪律（2026-11-23 定稿）

- 协议/指令三副本：云端 skill references/ ↔ 芭迪 pair 根（`D:\<workbuddy-root>\collab\hermes-badi\`）↔ 芭迪 skill references（`C:\Users\<windows-username>\.workbuddy\skills\feishu-collab-protocol\references\`）；改动后 scp 推送+拉回 md5 验证；协议源头=云端 skill references，推送链=云端→pair根→芭迪skill
- credentials.md 是**内部版含真实 ID**，分发/上传前必须脱敏
- 禁 @ 铁律范围（用户终裁）：禁 @ Hermes、法律助手、家庭助手（三者同源 gateway profile，法律/家庭为同源推断未实测保守禁）；@ CC 不受限（CC bridge bot 在群内，群信息 API bot_count=5 实证）

## 芭迪侧 skill 化（2026-11-23 完成）

- feishu-collab-protocol：`C:\Users\<windows-username>\.workbuddy\skills\feishu-collab-protocol\`（SKILL.md+references/协议+指令，hash 同步✅）
- **work-management（wm-skill-build 补建，2026-11-23 深夜）**：`C:\Users\<windows-username>\.workbuddy\skills\work-management\`（SKILL.md 10208B 五块：五工具查询规范/tr 提案手册/字段精简对照/已知陷阱/边界指回 agent.md；references/data-model-buddy.md 5107B 字段精简版）——从 CC 侧 354 行精简为查询+提案最小集，实测 wm_stats 通过。wm 协作资产全部在她域内：reports 骨架（inbox/done/returned/tools）+ 密钥（reports/tools/push_key ACL 收紧 + D:\<workbuddy-root>\.ssh\reports_push_buddy）+ lint/submit 适配（evidence 本地路径分支/密钥副本 ACL）
- 三层结构两侧同构最终形态：云端 work-management（写操作正本）↔ 芭迪 work-management（查询+提案精简版）↔ CC work-management 项目；CC rules↔agent.md（已落盘 C:\Users\<windows-username>\.workbuddy\agent.md）；脚本各自物理保留（ps1 留 hermes-badi/，skill 只写调用约定）
- 硬纪律不进 skill：每轮必守条款属 agent.md 层，芭迪 SKILL.md 已声明分层
- 退役脚本入 `_quarantine/`（v18_a2a_post.py 含 Bearer 明文安全隐患+wm_e2e_stdio_test.py）
- 权限 pending 机制定稿（用户拍板）：芭迪 pending 自行绕开不等待审批；Hermes 连续计数容忍 ≤2 次第 3 次问询（badi-wait 已自动化 --card-no-conv/--reset-card-count）；未预告权限请求一律 high/转用户
- ⚠️ 排程教训：联动任务（如"agent.md 定稿后建 wm skill"）要在当次一并派发，拆到"以后再建"会被后续任务挤掉——本次 wm skill 遗漏即此因，用户发现后补建

## 已知 bug 待修（不紧急）

- **agent-send.sh hook rebuild 覆盖已 close 任务**：发任务卡时 hook 会 rebuild 看板，把已 closed 任务重新派生成 dispatched（2026-11-23 实测复发 7 任务，与历史 board_derive bug 同源）。临时对策：close 后再发新任务前，先用 collab_board.py update 补核状态；根治=hook rebuild 跳过 closed 状态任务
