# v1.8 实施实战日志（2026-11-23，skill 体系落地 + 芭迪侧完善首战）

> 协议 v1.8 定稿后的落地实录。skill 主体只留规则，本文件存当次实战细节与脚本故障实证。

## 一、skill 体系重构（CC 审核通过）

- **multiagent-feishu-scripting 升 v2.0**：SKILL.md 重写 + references/protocol-v1.8.md + assets-inventory.md + a2a-redesign 记录 + scripts/ 5 个 symlink 指向全局脚本（物理单份、逻辑完整）
- **feishu-agent-collab v3.2 归档**到 `skills/_retired_v18_skills/`（有效 refs 已迁：credentials/cross-review/旧指令）
- **feishu-platform** 补 card-content-api.md（卡片正文不可读实测）；**feishu-dispatch** 补 v1.8 通道变更
- **CC 审查 result=partial → 8 条建议全部落实**：P0=芭迪指令 v18 适配版产出+旧指令拆解删除；P1=§0.2 措辞矛盾修正+协议补 conv 路径/ps1 示例/DryRun+5 个未引用 refs 归档头注+a2a-wake-chain 更名 expired；P2=Pitfalls 补查询时点+assets 计数+credentials 脱敏声明对齐实际
- **旧指令文档处置（用户偏好删除而非标失效）**：badi-custom-instructions.md 拆解——@ 语法/Bot 分工表/身份能力并入 badi-instructions-v18.md；旧 conv 六章节格式/status.json/辩论流程/@ Hermes 兜底三处全删；本体移 `_retired_v18_skills/`；全库 grep 无残留引用

## 二、禁 @ 铁律演进（三轮才定稿）

1. 初版：禁 @ 任何云端 Bot → 用户纠正：只禁 Hermes 和法律助手（CC/芭迪互 @ 无问题）
2. CC 评估：抓出法律论证路由缺口（旧指令教芭迪深度论证时 @ 法律助手，禁令切断）→ 补替代路由 conv [升级]；"@ CC 不受限"被判空集能力 → 改事实性陈述
3. 用户再纠正：**CC bridge 在群里**（群信息 API bot_count=5 实证，四 bot 表过时）；**家庭助手也是 Hermes profile 同禁**
4. 终版：禁 @ Hermes+法律助手+家庭助手（三对象，同源 gateway profile；法律/家庭为同源推断未实测保守禁止，条文注记证据等级）；@ CC 不受限（标签 `<at user_id="<open-id>">CC</at>`）

## 三、芭迪侧 ps1 改造首战（18:46 派发 → 19:05 收口）

**流程**：任务卡（规格+指向已推送的 PROTOCOL-v1.8.md/badi-instructions-v18.md）→ badi-wait sleep → 11 秒卡片信号 → 醒后原子序列（conv 拉取+ps1 七项实质核查+看板核销）→ closed result_pass

**芭迪交付 badi_finish.ps1 v2.0（243 行）七项全过**：四分类推送结果（pushed/already/TRANSIENT/DETERMINISTIC）/ 瞬时故障退避 2/4/8s 确定性失败零重试 / IDEMPOTENT_SKIP 幂等 / -DryRun（PARSE_ERRORS=0）/ Send-PushFailureText 纯文本告警禁 @ / status.json 删除 / conv 真推云端实证+卡片最后发

**亮点**：芭迪自主发现 forced-command SSH 无 ls 通道 → 远端预检不可行 → 等效实现推送后判 already，conv 里如实说明。瑕疵：conv 第六节推送输出未回填占位（功能无影响，下次提醒）。

## 四、实战暴露的脚本问题

1. **board rebuild 覆盖 bug 复发**：agent-send.sh hook 发任务时 rebuild 看板，已 closed 任务重派生 dispatched（与旧 board_derive.py bug 同源）。已用 collab_board.py update 补收口；修复待办=hook rebuild 保留 closed/failed 终态
2. **串行闸门被事故残留账本卡住**：v18-badi-side 失控事故的 4 条 pending_receipts 无回执可来（对话已被用户手动暂停），清账后重发成功。教训：事故任务收口时要同步清 pending_receipts
3. **hermes-post-task.sh verify 的 RemotePath 语义**=conv_inbox 内 conv 文件名；产出是远端 Windows 文件时 REMOTE_MISSING 属预期，LLM 直接实质核查后 close
4. **badi-wait 重入陷阱**：state 存 start_ts 跨调用续计时，不清理会 WAIT_TIMEOUT_TOTAL_EXCEEDED 立即返回；execute_code kernel 300s 超时跑不了等待，必须用 terminal 前台

## 五、剩余待办

- ~~agent.md 落盘位置~~ ✅ 已落盘（2026-11-23 用户手动，`C:\Users\<windows-username>\.workbuddy\agent.md`，v2 压缩稿总字符 1375≤1500）
- agent-send hook rebuild 覆盖 closed 状态修复（不紧急）
- ~~芭迪权限事件时是否单发纯文本卡~~ 实测结果：权限卡=纯卡片无纯文本（框架自动发非 LLM 产出，无法附带）；待讨论改进方向=权限卡前先 conv 提示
- wm skill（芭迪侧）建立 + wm MCP gateway 重启生效（时机待用户定，重启杀 tmux CC）

## 六、晚间增补：agent.md 落盘 + wm 协作端到端实测（21:00-22:00）

- **agent.md v2 压缩协作轮**：口径纠正（用户拍板总字符≤1500，非中文字符）→ Hermes 逐节目标表 → 芭迪 R2 独立实测纠正数字错误（2389→2514 实况，归因=修正表述时补入的工具名枚举）+ 3 点补充手法 → R3 收敛 → 出稿 1375 → Hermes 按 9 条语义自检清单独立验收（拉回文件亲测）全过。辩论制首次完整产生实际价值（错误基线若未纠正会误判压缩量）
- **agent.md 已落盘**（用户手动），三层结构两侧同构闭环
- **wm 协作端到端实测 PASS**：芭迪 wm-local 真实查询发现泰陌案「案件状态」列表格式残留（wm_stats 空值统计）→ tr 报告提案（未走"造测试备忘"捷径，选真实字段修正）→ lint pass → submit RECV_OK → Hermes 云端原件核验属实 → applied 执行（patch 归一单值）→ MCP 复验空值消失 → [通知]卡回执 applied
- **buddy 推送密钥链路**：authorized_keys 绑 wm_inbox_recv（pattern 已支持 buddy）+ 私钥 D:\<workbuddy-root>\.ssh\reports_push_buddy；调用格式 `ssh ... "wm_inbox_recv tr-XXXX.md" < 文件`（裸文件名缺 .md 会被格式校验拒）；云端落点 ~/.hermes/reports/inbox_push/
- **芭迪环境适配两处**：report_lint.py evidence 校验增加本地 .md 路径分支（buddy 无公网来源，编造 URL 违反防幻觉）；submit 密钥副本 icacls 收紧 ACL + ssh 加 -F config 规避沙箱
- **⚠️ 权限卡实测发现**：WorkBuddy 框架自动发权限卡=纯 interactive 卡片无纯文本伴随（非 LLM 回合产出，无法附带），与协议「权限双发」预期不符；导致 Hermes 两次误判「卡片⇒conv 缺席」为纪律违反（实际权限卡住，用户澄清后停止催促）。协议 §8 已补分型规则：**卡片到达但 conv 缺席 ≠ 纪律违反，先排除权限卡**（连续多卡无 conv 更指向权限/进度卡）。待讨论：权限卡前先 conv 提示可行性（框架弹窗时机 LLM 能否插入动作待芭迪确认）
- **云端 wm MCP 注册**：config.yaml mcp_servers 新增 wm（stdio，/home/ubuntu/wm-cli/wm_mcp_server.py，备份 bak_wm）；手动握手预验证 5 工具全注册+wm_stats 实测真实数据；待重启 gateway 生效（重启杀 tmux CC，时机待用户定）。架构定式：查询三端同一套 MCP（Hermes 云端/芭迪 wm-local/CC 脱敏视图），写入 Hermes 独占脚本链，MCP 纯只读

## 七、深夜增补：wm skill 补建 + 权限 pending 机制定稿（22:00-23:45）

- **wm skill 补建闭环（wm-skill-build）**：此前遗漏（agent.md 讨论时定"位置定稿后一起建"，被后续任务挤掉排程）。芭迪落盘 `C:\Users\<windows-username>\.workbuddy\skills\work-management\`（SKILL.md 10208B 五块 + references/data-model-buddy.md 5107B），从 CC 侧 354 行精简为查询+提案最小集。实测 wm_stats 通过，且 wm_stats 空值滞后=T+1h 新鲜度活体印证（云端 applied 后本地副本未同步）。reports 骨架/密钥/lint 在 wm 实测时已建（非本次范围）
- **权限弹窗机制讨论（permission-card-discuss，R1→R2→R3 完整辩论）**：用户提供弹窗原始样式（interceptType=file-external / approvalMode=post-exec escalation / 三选项 allow_always|allow|reject）。芭迪 R2 以第一手实测修正 Hermes 三处机制误解：①"拒绝"分支 LLM 未被挂起（工具错误文本返回同回合继续）②post-exec escalation=命令执行中拦截非跑完才拦 ③卡片与 conv 独立通道有时序差——conv 缺席≠挂起≠违规
- **方案收敛**：E=conv 哨兵行（芭迪 skill §七固化：`<!-- pending-op: <cmd-class> @<ts> -->`+结果行，5 类 cmd-class，命令预告格式 v2 含 cmd/target/risk/approval-plan）；C=协议 §5 权限卡分型（Hermes 完成）；B=allow_always 白名单建议转用户（放行 wm-local 只读查询/report_lint/badi_finish.ps1，不放行 submit/提权/ACL；授权主体=用户 GUI 操作）；D/F（审批卡带 conv 锚点/卡片类型前缀）=框架诉求转用户决定是否向 WorkBuddy 反馈
- **代批链路实测 + pending 活体样本（delegated-approval-test）**：Bot 群消息（Hermes 回"允许"）不能在框架层解锁审批→代批方案技术不成立。连续卡片无 conv 的 pending 活体样本实证：她侧无信号（回合冻结、无法写 conv、无法回复问询）。用户拍板最终机制：**芭迪 pending 时自行绕开**（换方案/路径/密钥，不等待审批，铁律入她 skill §七含 approval-plan 语义重定义 self 绕开为主）+ **Hermes 连续计数容忍**（只有卡片没 conv ≤2 次 sleep 等待；连续第 3 次=发卡问询）
- **badi-wait 计数自动化**：新增 `--card-no-conv`（计数+1）/`--reset-card-count`（清零）参数，state 持久化跨调用，计数≥3 自动输出 CARD_STREAK 告警（含协议 §5 处置提示）。功能测试 0→2→重置通过
- **"始终允许"实测**：allow_always 确认生效且稳定（两次同类原生命令免弹窗，返回标记 escalation-approved）；但范围=会话级沙箱整体绕过，宽于按命令类授权，无法反证 B 白名单类级精度。pending 分支仍无法复现（环境已授权），依赖昨日实证与机制推断补齐
