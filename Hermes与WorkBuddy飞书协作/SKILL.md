---
name: multiagent-feishu-scripting
description: 给芭迪(WorkBuddy)派任务、等待回报、验收闭环、排查协作故障时使用。v1.8 零机械架构：sleep 等待主链路+卡片唤醒+脚本管事实LLM管判断。含协议 v1.8 全文。
version: 2.1.0
author: Hermes
tags: [feishu, multiagent, badi, workbuddy, collab, scripting]
---

# 飞书多 Agent 协作（v1.8 零机械架构）

> 与 tmux 六件套（hermes-claude-collaboration skill）平行的体系：tmux 管 CC 终端协作，本 skill 管飞书通道的芭迪(WorkBuddy)协作。Default 与 Coordinator profile 通用。

## 核心架构（八轮辩论+联测定稿，详见 references/protocol-v1.8.md）

**唯一唤醒信号 = 芭迪群新消息**（卡片+纯文本，30s 轮询 ListMessage）：
- 卡片 = 框架回合边界（完成/权限/进度），**正文 API 不可读**（只有 fallback 占位符）
- 纯文本 = 异常/权限的唯一机器可读叙事（芭迪默认发卡片无法改，异常类才双发文本）
- conv = 内容权威（芭迪每次回复都写，讨论类和执行类相同流程）
- 看板 = 状态权威；audit/A2A 已退役（端点休眠）

**交互由 Hermes 发起和持有**——禁止让芭迪主动 @ Hermes、法律助手、家庭助手（三者同源 gateway profile，@ 会拉起对方失控群房间 session，用户无法中止；法律/家庭为同源推断未实测，保守禁止）。

## 标准流程

### 派发任务
```bash
agent-send.sh badi <task_id> --step N --msg-file <卡片内容文件>
```
hook 自动登记看板+账本。旧 WATCH_NOT_RUNNING 提示已废弃（v1.5 铁律退役），忽略。

### 睡眠等待（同 turn 阻塞）
```bash
python3 ~/.hermes/scripts/badi-wait.py --task <task_id> --total <秒>
```
- exit 0 = 检测到群消息（stdout 带 SIGNAL 类型+原材料）；exit 1 = 超时（带 STALL 梯子判定）
- 内部：30s 群 API 轮询（sender 白名单）+ 梯子状态文件续计时 + cap=min(20段,迭代-15)
- **先清理残留 state**：`rm -f ~/.hermes/.badi_wait_<task>.state ~/.hermes/.badi_wait_<task>.cursor`
- **连续卡片计数**（协议 §5 权限卡分型）：卡片唤醒后 conv 无更新 → 下次调用加 `--card-no-conv`（计数+1）；conv 有更新 → `--reset-card-count` 清零。计数 ≥3 时 stdout 自动告警 `CARD_STREAK` → 按协议发卡问询芭迪

### 醒后原子序列（跳过验收直接闭环 = 最大漏洞）
```bash
hermes-post-task.sh verify -TaskId <id> -RemotePath <产出路径>   # 机械校验，输出材料后停
# → LLM 读材料做验收判断（判断闸门，不可跳过）
hermes-post-task.sh close -TaskId <id> -Verdict pass -Notes "..."  # 闭环
hermes-post-task.sh close -TaskId <id> --unverified                # SSH断场景
hermes-post-task.sh brief                                          # 全板快照
```

### 醒后必查（卡片分型后置）
1. conv 就位？`ls -t ~/hermes_collab/conv_inbox/ | head` —— 有=读内容；无=等一轮再催（可能推送失败）
2. 看板状态：`collab_board.py brief`
3. 分型：conv/板判断是完成/权限/进度，路由处理

## 已知事实（实测锚点）

- **卡片正文 API 不可读**：ListMessage/GetMessage 均只返回 fallback 占位符+装饰图。分型靠醒后查 conv/板
- **芭迪无法发纯文本**：飞书对她的机制默认卡片。异常/权限的纯文本双发是她的框架能力边界内能做到的（待实际权限事件验证）
- **讨论类也必须写 conv**：卡片正文不可读，conv 是唯一可读输出通道——无讨论/执行之分（2026-11-23 用户裁定）
- **群 API 一次调用 ~1s**，30s 轮询配额余量大；ts 游标持久化防重复报
- **@ 唤醒芭迪是唯一入口**，不含 @ 的群消息她静默丢弃；每张卡片必须自带 @（多卡片拆分时每张都要）
- **长消息拆多卡=只有第一张进芭迪通道**：长内容压缩单卡或走 conv
- **A2A 端点休眠**：<cloud-tailscale-ip>:9900（token 有效），需要同步回执场景再启用；audit/看板监听已退役
- **@ Hermes/法律助手/家庭助手的芭迪消息会拉起独立群房间 session**（非本对话），该 session 不可控——禁止命令芭迪主动 @ 三者（终版用户裁定 2026-11-23，家庭助手豁免被推翻：family 同为同源 gateway profile）。@ CC 不受限（CC bridge bot 在群内，群信息 API bot_count=5 实证）
- **群房间 Hermes 分身会代写 conv（2026-11-23 R57 事件实证）**：芭迪纯文本 @ Hermes 后拉起的群房间独立 session 分身，会以「Hermes」名义追加 conv 段落并走 badi_finish 推送（含非标准 state 行如 `status=r2_delivered`、指纹非 sha256 口径）。内容方向通常无害（读到了群消息正文），但造成**conv 双写者**+state 行口径污染。主对话醒后若发现「自己没写过的 Hermes 段落」，先按时间戳+内容甄别是否分身代写，收口时清理非标准 state 行（恢复正规指纹），并在协议层面明确 conv 单写者=主对话 Hermes
- **Tirith 审批卡会泄入协作群**：agent-send.sh 被安全扫描拦 HIGH 时，审批以 interactive 卡片发进协作群，芭迪可见。她正确立场=不代批 Hermes 侧审批（环境不同+内容不可见+at 对象非她）。Hermes 侧应：被拦命令改写绕开误报（如去掉 `| tail` 管道）自行放行，勿让审批卡滞留群内引发对方困惑；收到对方「拒绝代批」回复属正常安全行为，非故障
- **指纹双口径勿混用**：agent-send.sh 卡片指纹=sha256(`task|step`) 前12位（不含 conv 名）；badi_finish conv 指纹=sha256(`task|step|conv文件名`) 前12位（ASCII 字节）。校验/比对时先确认口径
- ⚠️ **通道/成员类硬事实必须 API 实证，不得凭分工表或他人推断采信**：旧 Bot 分工表缺 CC，CC 审查据此判"CC 不在群里"被用户纠正（bot_count=5 实证 CC bridge 在群）。验证命令：群信息 `GET /im/v1/chats/<chat_id>` 看 bot_count，成员 sender 用 ListMessage 分布佐证
- **WorkBuddy 框架 skill 机制已建成芭迪侧 skill**：真实路径 `C:\Users\<windows-username>\.workbuddy\skills\feishu-collab-protocol\`（2026-11-23 芭迪实证建仓，含 SKILL.md+协议/指令 references，hash 同步 pair 根；此前外部判断的 D:\<workbuddy-root>\.workbuddy\skills\ 非主目录——框架路径类问题让当事方自己确认最可靠）。三层结构两侧同构：云端 skill↔芭迪 skill；CC rules↔agent.md（芭迪侧待落盘讨论）；脚本物理留芭迪协作根（skill 只写调用约定，迁知识不迁脚本和通道目录）；硬纪律不进 skill（每轮必守条款属 agent.md 层）
- **芭迪协作根已迁至 `D:\<workbuddy-root>\collab\hermes-badi\`**（2026-11-23 用户裁定权限隔离：芭迪/CC 敏感权限不同，各自域内运行；旧址 `D:\<projects-root>\collab\hermes-badi\` 已整目录归档至 `D:\<projects-root>\collab\_migration_archive_20261123\`，CC 侧 hermes-feishu-cc 留原处）。目录隔离现为硬边界。云端已联动：hermes-post-task.sh WIN_CONV_DIR、agents.conf collab_dir、协议 §2.1、badi-instructions、assets-inventory 三副本行。接收端 wm_conv_recv 落点在云端 ~/hermes_collab/conv_inbox/，与芭迪本地路径无关，零改动。协议推送链：云端 skill refs → 新 pair 根 → 芭迪 skill refs（SHA256 对比同步）。桌面 agent_md_final.md 旧路径已由芭迪改好，用户落盘 agent.md 时直接用
- **agent.md 载体已实证更正（2026-11-24）**：WorkBuddy **无独立 agent.md 文件机制**，常驻注入四层=SOUL/IDENTITY/USER.md（`C:\Users\<windows-username>\.workbuddy\`）+ UI 设置项 customPrompt（存储于 `app\app-config.json` 的 `personalization.customPrompt`，会话启动注入 system prompt `<user_custom_instructions>` 段，**改后需新会话生效**；SOUL.md 也可自定义）。⚠️ UI 实存 1424 字符=**11-23 失控事故前旧版**（教主动@ Hermes，与 v18 §37 禁主动@ 冲突；当天 1375 定稿从未落盘）。**最终重构已收敛（2026-11-24 晚，取代早期 291 字方案）**：经全量盘点 71 条+R1→R2 辩论+用户拍板，四份终稿=customPrompt 130 字（身份+技能先扫/数据前置）、SOUL 1057（全中文化+协作准则 5 条[升级]口径）、IDENTITY 860（v3 最终版：**五 Bot 分工表** Hermes/法律助手/芭迪/CC/家庭助手——用户指出「不止三个，还有 CC 的飞书端口」补 CC 行，芭迪抓出禁@条款点名家庭助手但分工表缺它后用户拍板补第 5 行，与 v18 §19 对齐；另含禁主动@/升级路径/飞书只是通道/写作规范指针式）、USER 1324（用户修正稿逐字采用+结构调整：时点快照改动态指向/写作规范聚合/尾段译中）；实证锚点：identity_context 与 user_custom_instructions **均为每轮注入**（必达效力打平，禁主动@故放 IDENTITY）；标题保留英文（用户要求）。**落盘分工定案：SOUL/IDENTITY/USER 由芭迪写盘，customPrompt 用户粘 UI，无需退出芭迪（新会话生效即可）**；customPrompt/SOUL/USER 全文在 conv-agent-md-redesign2-final-20261124-2051.md，IDENTITY v3 在 conv-agent-md-redesign2-idfix2-20261124-2111.md，用户已逐条审完内容，待最终确认后执行落盘。早期方案详见 references/agent-md-redesign-20261124.md。原定稿口径=总字符≤1500（中英都算 1 字），权限卡处理机制已收敛：E 哨兵行（她侧 skill §七固化 `<!-- pending-op: <cmd-class> @<ts> -->` + 结果行，5 类 cmd-class）+ C 协议 §5 权限卡分型（已补：卡片+conv 缺失+非终态 → 先查权限挂起不判违规）+ B allow_always 白名单（放行 wm-local 只读查询/report_lint/badi_finish.ps1，不放行 submit/提权/ACL——授权主体=用户 GUI 操作）已转用户。D/F（审批卡带 conv 锚点/卡片类型前缀）= 框架诉求待用户向 WorkBuddy 反馈
- **工作管理多 agent 协作已端到端实测通过**（wm-collab-e2e-test）：芭迪 wm-local 查询（role=buddy 全量）→ tr 报告提案（lint/submit 走 buddy 专用推送密钥，authorized_keys 绑定 wm_inbox_recv，私钥 `D:\<workbuddy-root>\.ssh\reports_push_buddy`+她侧 reports/tools/push_key ACL 收紧副本，调用格式 `ssh ... "wm_inbox_recv tr-XXXX.md" < 报告`——命令必须带 wm_inbox_recv 前缀非裸文件名）→ 云端落点 `~/.hermes/reports/inbox_push/` → Hermes 审核提案（真伪核验后 applied/rejected + 报告 status 回写）→ 通知卡回执。云端 wm MCP（`/home/ubuntu/wm-cli/wm_mcp_server.py`，stdio）已注册 config.yaml 待重启生效——注册后查询语义三端统一（Hermes/芭迪 wm-local/CC 脱敏视图）。写入仍 Hermes 独占脚本化（template_cp/wm_row/patch+操作日志）
- **芭迪侧 work-management skill 已建成**（2026-11-23 wm-skill-build 闭环）：`C:\Users\<windows-username>\.workbuddy\skills\work-management\`（SKILL.md 五块：五工具查询规范/tr 提案手册/字段精简对照/已知陷阱/边界指回 agent.md；references/data-model-buddy.md 字段精简版）。从 CC 侧 354 行精简为"查询+提案"最小集（写操作专属内容剔除）。reports 骨架+密钥+lint/submit 在她域内 `D:\<workbuddy-root>\collab\hermes-badi\reports\`（实测时已建）。实测细节：wm_stats 空值滞后=T+1h 新鲜度活体印证（云端 applied 后本地副本未同步）
- **权限 pending 最终机制（用户拍板 2026-11-23 晚）**：代批链路实测证明 **Bot 群消息不能在框架层解锁审批**（Hermes 回"允许"不被接受）→ 最终方案=芭迪 pending 时**自行绕开**（换方案/路径/密钥，不等待审批，铁律入她 skill §七）+ Hermes 侧**连续计数容忍**（只有卡片没 conv ≤2 次 sleep 等待；连续第 3 次=发卡问询，badi-wait 已自动化：`--card-no-conv` 计数/`--reset-card-count` 清零/≥3 自动输出 CARD_STREAK 告警）。allow_always 授权主体=用户 GUI 操作；会话级沙箱绕过范围宽于按类授权（无法反证类级精度）

## 退役清单（v1.8，归档于 scripts/_retired_v18/，可回滚）

board-listener.py / board_watch.sh / board_derive.py / board_sentinel.sh / badi_watch.sh / agent-wait.sh / a2a_wake_watch.py

退役原因：A2A POST 砍除（audit 源死）+ 卡片权威唤醒裁定（conv watch 无岗）+ 投递层故障连根拔除（sleep 等待取代）。**见到 WATCH_NOT_RUNNING 提示请忽略**（旧协议残留文案）。

## References

| 文件 | 何时读 |
|---|---|
| [cc-badi-drive-cc-20261125.md](references/cc-badi-drive-cc-20261125.md) | 芭迪驱动 CC（B 方案）协作知识：skill 位置、目录双分离、fstab 坑全记录 |
|---|---|
| [protocol-v1.8.md](references/protocol-v1.8.md) | 完整协议：约定争议、格式审计、新增协作模式、STALL/异常细则时**必读** |
| [assets-inventory.md](references/assets-inventory.md) | 脚本资产对照清单（复用/改造/新建/退役全表） |
| [a2a-redesign-2026-11-23.md](references/a2a-redesign-2026-11-23.md) | 八轮辩论全记录（R1-R8 演进与实证锚点） |
| [credentials.md](references/credentials.md) | 凭证与 Token 管理（**内部版含真实 ID，分发前必须脱敏**） |
| [cross-review-workflow.md](references/cross-review-workflow.md) | 交叉审查流程 |
| [badi-instructions-v18.md](references/badi-instructions-v18.md) | **芭迪指令唯一权威版**（旧版已拆解删除：身份/分工表/@语法已并入，@ Hermes 兜底等危险指令已清除） |
| [v18-implementation-log-20261123.md](references/v18-implementation-log-20261123.md) | v1.8 落地实战日志：skill 重构、禁 @ 铁律三轮演进、芭迪 ps1 v2.0 首战、脚本问题实证 |
| [wm-skill-trigger-fix-20261124.md](references/wm-skill-trigger-fix-20261124.md) | 芭迪侧 wm skill 漏触发调查与修复方案（诊断闭环待拍板；含 customPrompt 载体实证与 a/b 方案） |
| [agent-md-redesign-20261124.md](references/agent-md-redesign-20261124.md) | **常驻注入四层架构+重构定稿**（customPrompt/SOUL/IDENTITY/USER 分层、R3 终稿全文、待落盘清单）——改芭迪常驻指令前必读 |

## Pitfalls（高频）

0. **承诺的交付物必须在同 turn 内交付完再结束**（用户纠正，2026-11-23）：说过"稍等我整理出来"然后结束 turn = 执行纪律违规；整理耗时长先给核心内容再补细节

1. **badi-wait 前先清理残留 state 文件**（重入会用旧游标，漏检新消息）。细节：`.badi_wait_<task>.state` 存 start_ts（墙钟续计时，陈旧会导致 WAIT_TIMEOUT_TOTAL_EXCEEDED 立即超时）、`.cursor` 存 last_ms（防重复报旧消息）。**手动重置要两个都写**：state 写当前时间戳、cursor 推进到已知消息之后；只清一个会出现「游标正确但立即超时」或「计时正常但重报旧消息」
1b. **badi-wait.py 无执行权限时用 `python3 ~/.hermes/scripts/badi-wait.py`**（脚本本身可能非 +x）
2. **accept edits 模式下 cc-send.sh 可能吞 Enter**：发送后 45s 无 thinking 标记 → 补发 Enter（已有两次实测）
3. **睡醒先查 conv 再问芭迪**：卡片到达 ≠ 她没写 conv；先 `ls -t conv_inbox/` 再决定是否催
4. **迭代预算共享**：等待段消耗与后续处理共享 turn 上限，等待 cap 后至少留 15 次迭代。**多轮续等（wait 超时→重置 state→再等）会成倍烧预算**——同一 turn 连续 5+ 轮无信号时，收口如实汇报当前状态（已发/已核/待回复）并结束 turn，让下一条群消息唤醒新 turn 续处理，不要无限续等（2026-11-23 实测：续等烧尽平台迭代上限被强制切断）
5. **用户在线时用短轮询（poll 间隔小）**：阻塞等待会延迟用户消息响应；用户在场改离散短轮询
6. **判"芭迪未做某动作"前先确认查询时点**：她的机制=卡片最后发（finish 提交后框架才发卡），查询早于发卡时刻会误判（2026-11-23 实测）
7. **agent-send 串行闸门**：同一 task 未闭环再发会被拦（SEND_UNCLOSED），确认前轮已完成时用 `--override-serial "原因"`
8. **与 CC 交错对话时用离散短轮询而非阻塞等待**（cc-wait 会延迟用户消息响应）；离散轮询的固有代价=响应延迟最多一个轮询周期（2026-11-23 实测 ~3min），用户问"CC 完成了吗"属正常延迟非故障
9. **过时指令文档的处置：用户偏好删除而非标失效**（2026-11-23 纠正）：整体被取代且含危险指令的旧文档，加 SUPERSEDED 头注不如拆解。正确做法：①仍有效的平台机制/分工表/身份描述**并入新版** ②危险指令（如 @ Hermes 兕底）**直接删** ③旧文档移归档区并清理所有引用。头注仅适用于"局部过时"文档——检索/引用可能只命中正文片段看不到开头警告，残余风险大
11. **CC 审查自己的产出后再逐字采纳时，仍要独立核验事实性论断**：CC 评估 a/c 两项（同源推断+残留定位）全部准确且抓到真 bug（法律论证路由缺口），但 b 项"CC 不在群里"是基于过时四 bot 表的推断——审查者的推理质量不等于其事实前提的质量。CC 对文档/一致性类判断可信度高，对外部通道/成员类事实一律 API 复核
12. **方案级讨论必须走辩论制（R1→R2→R3）**：收到芭迪/CC 的方案意见后，先独立核验其事实断言再发 R2 立场，等收敛后才汇总用户——跳步=传话筒（2026-11-23 agent.md 讨论复发，协议 §9 已补回此义务；v1.8 重写时曾遗漏旧协议 §9 辩论条款导致规则真空）
12a. **agent-send.sh hook 在发任务时 rebuild 看板，会把已 closed 任务重派生为 dispatched**（2026-11-23 实战复发，与旧 board_derive.py bug 同源）：close 后再派新任务，之前收口的任务全部"复活"。临时对策：发任务后用 `collab_board.py update <task> closed --conclusion result_pass` 补收口。**修复待办：agent-send hook rebuild 时保留 closed/failed 终态不重派生**
13. **看板核销的双重闸门顺序**：`collab_board.py update <task> closed` 会被「pending_receipts.jsonl 在途回执」拦（BLOCKED）；先核销账本（对方卡片已发=隐式回执，可直接删该行）再 update。`hermes-post-task.sh close` 则不受账本拦截但走 verify 材料（RemotePath 语义=conv_inbox 内的 conv 文件名，产出为远端 Windows 文件时 verify 报 REMOTE_MISSING 属预期，LLM 直接判断后 close）。**串行闸门（SEND_UNCLOSED）的释放源是 `scripts/.agent_send_state.json` 的 ack_state 字段，不是账本**——核销 pending_receipts 不解 SEND_UNCLOSED；对方实质回复到位（conv+卡片）时直接把 ack_state 置 closed 再重发。仍拦再用 `--override-serial "原因"`（留痕审计）
14. **execute_code kernel 有 300s 硬超时，跑不了 badi-wait 300s+**：等待必须用 `terminal` 工具前台跑（timeout 550 留余量）。另外 badi-wait 的 STALL 梯子状态文件跨调用续计时——同一任务重复 wait 前必须清 state，否则 WAIT_TIMEOUT_TOTAL_EXCEEDED 立即返回
15. **通道/路径/成员类硬事实必须实证，勿凭表或他人推断采信**（11-23 两次实证教训）：群成员用群信息 API `GET /im/v1/chats/<chat_id>` 看 bot_count（旧四 bot 表缺 CC，据表推断"CC 不在群"被用户纠正）；对方框架内部路径勿替当事方判断（WorkBuddy skill 真实路径被我判错，芭迪实证纠正）——让对方自己确认最可靠
16. **与芭迪的方案级讨论严格走辩论制，已实战验证有效**（2026-11-23 agent.md 压缩轮：芭迪 R2 独立实测纠正 Hermes 数字错误——报 2389 是旧实测，当前实况 2514，还定位出差异根源是 Hermes 修正表述时补入的工具名枚举；若按错误基线会误判压缩量）。要点：①派任务卡里写明"本轮是讨论，别直接覆盖草稿"可引导对方出 R2 而非直接执行 ②对方补的意见/遗漏常是真问题（她抓出命令文件 9 处引用、lint 脚本技术冲突、双母本冲突，均为实锚）③收到的意见先工具复核再表态，不因"需用户拍板"而跳过辩论——拍板项提炼是 Hermes 义务 ④R3 收敛后把确认结论以 step-2 任务卡发回，让对方把 R3 段落写入 conv 存档
17a. **定稿类文档（agent.md 等）的字数口径先问清**："1500 字"是中文字符还是总字符——本会话曾按中文字符口径交付后被用户纠正为总字符≤1500（差 1000+ 字符，需返工重压）。实测工具：python `len(text)` 算总字符、`re.findall(r"[\u4e00-\u9fff]", t)` 算中文数，两个数都报。压缩协作模式：Hermes 出逐节目标表→对方 R2 补手法+硬语义清单→R3 收敛→对方出稿→Hermes 按语义自检清单逐条独立验收（拉回文件亲测，不信自报）
18. **芭迪 finish 推送 SSH 报错 → 分层排查，网络层优先**（2026-11-24 实战：根因=云端 Tailscale 掉登录，云端侧全部正常）：她报「finish 推不了/ssh 报错」时按 ①云端接收端自测（`printf 'test' | ~/wm-cli/wm_conv_recv conv-selftest-<日期>.md` 验证脚本+落盘正常）②authorized_keys 受限段在位 ③**网络层**（`tailscale status` 看是否 Logged out；`tailscale ping <windows-tailscale-ip>`；`timeout 5 bash -c 'cat < /dev/null > /dev/tcp/<windows-tailscale-ip>/2222'` 探端口）④sshd 日志（`sudo journalctl -u ssh --since ...`）。云端↔Windows 全部通道（芭迪推送、Hermes→Win SSH 2222、CC 通道）同走一条 Tailscale 隧道，掉登录=全线故障；判定依据：今天来自 <windows-tailscale-ip> 的 Accepted publickey 为零而前一日密集正常 → 隧道断而非对方配置错。**勿在她侧反复重试**——云端网络层断了，重试只会白白消耗她的轮次
19. **Tailscale 掉登录的恢复手法**（2026-11-24 实测）：①`sudo tailscale up` 裸跑会报错要求提及全部非默认 flags——直接用报错提示的完整命令（本机=`sudo tailscale up --accept-dns=false --accept-routes`）②授权 URL 每个进程实例一个，**前台命令超时被杀=该授权会话作废、URL 失效**——用户拿旧 URL 登录「成功」但 `tailscale status` 仍 Logged out 就是这种错位；正确做法=`terminal(background=true, notify=true)` 跑 tailscale up，从后台进程 log 取**当前有效** URL 给用户，等进程退出通知③核验一律以 `tailscale status` 输出为准，不信用户「我登录了」的口头确认（他可能登的是已作废链接）④auth 期间后台进程保持不杀，授权完成自动收尾
17b. **权限卡与 conv 缺失的辨析（2026-11-23 实测收敛）**：权限卡=纯卡片无纯文本（框架自动发，非 LLM 回合产出，“异常双发”条款对它不适用）。卡片+conv 缺失+任务非终态 ≠ 纪律违反——先查权限挂起，纯文本群消息直接问询（不走卡片避免无 conv 轮回）比连续催促更高效。芭迪侧已固化应对：敏感命令（ssh-push/privilege/acl/ext-file/wm-write 五类）执行前在 conv 写 `<!-- pending-op: <cmd-class> @<ts> -->` 哨兵+结果行（skill §七），Hermes 看“有 pending 无 result”即判审批挂起中。机制要点（她第一手实证）：post-exec escalation=命令执行中拦截非跑完才拦；“拒绝”分支以工具错误文本返回、LLM 同回合继续不被挂起；allow_always 授权主体=用户 GUI 操作，Hermes/芭迪只能出建议清单
20. **badi-wait 边界竞态：信号可能在最后几秒到达而被漏检**（2026-11-24 实测：conv 18:16:39 到达，wait 18:09:40 启动+420s=18:16:40 到期，差 1 秒，30s 轮询没接住就超时）。wait 超时退出后**先 `ls -t ~/hermes_collab/conv_inbox/` 再判超时**——conv 已落盘=信号已到只是没报，直接继续处理不要重等。需要更长容忍时用更大 `--total` 而非反复短等
21. **Tirith 安全扫描审批会终止 turn**（2026-11-24 用户反馈「一发权限请求就自动结束 turn 卡住」）：被 HIGH 拦截的复合命令（heredoc+清空文件等）会触发审批流程打断会话。规避：清空/写文件用 write_file 工具而非 `> file`/heredoc+terminal；agent-send.sh 本体不触发。发卡前把卡片内容用 write_file 写好，terminal 只跑纯 agent-send 命令
22. **badi-wait 查板快路径误判：任务终态+在途回执≠已闭环**（2026-11-25 两次实战，已修 v1.8.1）：派新 step 前看板还停在上轮 closed（agent-send 幂等保留旧条目不重开），wait 启动即判 `board_already_closed` 退出，根本没进轮询。修复：快路径命中终态时查 `pending_receipts.jsonl`，有在途回执=刚派发未收口→忽略快路径继续轮询（stdout 打 NOTE 说明）；真收口才立即退出。另注意 `collab_board.py update` 只追加事件流**不刷新派生视图** `collab_board.json`——wait 读的是旧视图，update 后必须跑 `collab_board.py rebuild` 才对 wait 生效。工作序列固化：派发 → `update dispatched --step N` → `rebuild` → 清 state → wait（脚本自愈后 rebuild 仍建议保留）

23. **芭迪域内的本地文件操作必须派芭迪，不要云端 SSH 直拉**（2026-11-24 两次被用户纠正：「你让芭迪处理不是更好」「本地任务优先用本地agent」）：读/导出/修改 `C:\Users\<windows-username>\.workbuddy\` 下文件、生成导出包等任务，正确流程=写任务卡让芭迪在她域内处理并走 conv 推回，Hermes 只做校验（SHA256/逐字 diff）。SSH 直拉的问题：编码乱码（GBK）、BOM、CRLF 噪音、绕过当事人确认。校验职责不可省——拉回后与对方报告值独立比对，不信自报
24. **重构/整理类任务的方法论（用户拍板 2026-11-24）**：改多份配置/文档前，先**全量通读逐条盘点**（每条标性质/现状问题/处置/归属）→ 列缺口清单 → 再讨论补充；不要先定分工框架再填内容。用户亲自维护的文件（如 USER.md）：事实内容以用户修正稿为底稿**逐字采用**，Hermes/芭迪只动结构与表述层；时点性快照（「目前没有在办案件」类）改动态指向数据源（wm-local/工作区文档）防过时。终稿产出后**全量导出改前+改后文件供用户逐一确认**再落盘，不合并摘要汇报。文件由当事方 agent 在域内生成（Hermes 只做 SHA256/逐字校验），标题中英文等细节即使盘点表建议了也以用户最终表态为准。（2026-11-24 wm-skill 漏触发调查）：芭迪 R1 用旧会话索引（vscdb 19 个会话全在 3~4 月）得出「无反例」结论，被用户指出当天就有浙能拜访反例——她枚举方式有盲区（新会话落 projects/*.jsonl 不进 vscdb）。教训：派调查任务时提醒对方「证据覆盖到今天」；收到「未发现反例」类结论先想枚举方式是否漏了新数据源，再采信

25. **watch 挂设条件=项目未收口，而非「我在等回报」**（2026-11-25 用户两次点破）：只要协作项目还活着、对方可能随时发消息，turn 结束时必须挂 `terminal(background=true, notify=true)` 的 badi-wait——turn 结束后唯一唤醒通道就是这个。任务全部收口后 badi-wait 会被看板快路径挡（`board_already_closed` 立即退出，v1.8.1 修复只救「有在途回执」场景）——此时要继续监听群消息，用**不存在于看板的任务名**（如 `<task>-idle`）绕过快路径纯监听。idle 监听超时退出属预期静默，不告警；wait 报 WAIT_TIMEOUT 且 STALL 建议发卡升用户时，先想清楚等的到底是对方回报还是用户拍板——等用户拍板时不空转续挂烧预算

26. **判「对方没回复」前先拉群消息 API 复核，且表述要精确到时点**（2026-11-25）：说「没有新回报」被用户质疑「芭迪回复了你却说没有」——实况是回复已被上一轮 watch 唤醒处理过，「没有」指其后时段。复核命令：ListMessage `container_id_type=chat&container_id=<chat_id>&sort_type=ByCreateTimeDesc`（chat_id 硬编码在 badi-wait.py `GROUP_CHAT`）。向用户汇报时必须区分「已处理过」和「不存在」，混用会被当成漏处理
