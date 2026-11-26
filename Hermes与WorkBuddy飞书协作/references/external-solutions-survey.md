> 📦 **已归档（v1.8 前历史文档）**：描述的机制已被 v1.8 架构取代，仅供历史参考。

# 外部解决方案调研（2026-11-23，应用户「飞书多agent协作问题大，难道没人研究过」）

> 结论：手搓方案≈A2A 子集的劣质重造。生态有标准答案，但受限于芭迪（CodeBuddy 框架）无法改造通信底座，落地路径是借鉴模式而非迁移系统。

## 1. A2A 协议（Google → Linux Foundation）

- 时间线：2025-04 Google 发布，2025-06 Linux Foundation 接管，2026-04 一周年 150+ 组织，2026-10 v1.0 + a2a CLI
- 核心机制（对应我们的痛点）：
  | 我们的痛点 | A2A 解法 |
  |---|---|
  | 唤醒断链（哨兵收口即死） | Webhook push：server 状态变化主动 POST client 注册的 webhook；「推送是信号不是载荷」，收到后 GetTask 拉详情 |
  | 对方自觉写 status | Task 状态机协议内建（submitted/working/completed/failed/input-required），server 权威维护，客户端 GetTask 拉取 |
  | 发出即失明 | streaming(SSE)/polling/push 三通道按场景选；push 专为「无法保持长连接」设计 |
  | 指纹口径漂移 | 标准 JSON-RPC 消息封装，无自研指纹 |
  | 通知卡/任务卡混账 | input-required vs completed 语义内建 |
- 选型口诀（社区共识）：阻塞快查=同步请求响应；中长任务=异步轮询；实时连续=SSE；超长 fire-and-forget=webhook push
- 阻碍：芭迪（CodeBuddy）和 CC 框架暂不支持 A2A server 端
- 参考：a2a-protocol.org/latest/topics/streaming-and-async；linuxfoundation.org/press（A2A 一周年公告）

## 2. HKUDS/AgentSpace

- 定位：agent 原生协作工作台——人类+数字员工一团队。Apache 2.0，2026-06 v1.0，活跃开发
- 架构：PostgreSQL 任务队列（任务/审批/通知入库，看板即真相源）+ remote daemon（agent 机器跑 daemon 被动接活）+ AgentRouter（统一 harness 层：同一 agent 身份/上下文/技能跨 runtime，支持 Claude Code/Codex/Antigravity/OpenCode/OpenClaw/**Hermes**/Gemini/NanoBot）+ 审批权限中心
- **飞书集成时间线（重要澄清）**：2026-06-27 开始做（codex/feishu-integration 分支）→ 2026-07-02 测试通过合入 main。含义=「部署 AgentSpace 工作台后，其管理的数字员工可接入飞书对话」，**不是**「现有飞书 Bot 可接入」也**不是**「飞书官方支持了此架构」
- 对我们的三个硬阻碍：①AgentRouter 无 CodeBuddy/WorkBuddy harness——芭迪进不来 ②部署重（Node 24 + PostgreSQL 16 + Docker 常驻）③目标形态是「平台托管 agent 的 CLI 执行」，飞书群里自主接活的 Bot 模式不在其设计内
- 定位：**思路参考非可迁移方案**——借鉴「事件入库、看板即唯一真相源、审批中心化」三模式
- 仓库：github.com/HKUDS/AgentSpace（README 有中文版 README_ZH.md）

## 3. 飞书官方 Bot@Bot 协作文档

- URL：open.larkoffice.com/document/mcp_open_tools/integrating-agents-with-feishu/agent-at-agent-for-complex-tasks
- 模式：@ 接力链（A 做完 @B，B 做完 @C），卖点仅「过程群里可见/人类可随时插入打断/互相校验」
- **无调度者拉取机制**：全文没有任何「总调度如何查看其它 agent 回复/成果」的设计——官方假设人类肉眼盯群即可。且其模式依赖「被 @ 继续同一对话」
- 注意：文档页是 SPA，web_extract 只能拿到部分正文；curl 拿到 7KB JS 壳。需要全文时用浏览器渲染
- 附：Hermes 侧实测（2026-11-23，见 SKILL.md「飞书群消息唤醒架构」节）：群 session 本就是长对话（key 稳定），FEISHU_ALLOW_BOTS=all 下 bot 消息免 @ 直进——「被@开新对话」从未被实测验证过，近期 bot@消息实际一条都没到达过 gateway（近期协作全走 conv+卡片，卡片发送不经接收管线）

## 4. 落地路径（从轻到重）

1. **v1.8 事件入箱最小实现**：badi_finish 推送 conv 后 POST `{task,state,conv文件名}` 到云端 gateway HTTP 端点（8642-8646 已有端口基建）——推送从「落文件等轮询」变「事件直达」，消灭「哨兵收口即死→推送无人知」整类问题。不动现有协议，纯增量
2. **看板升级为唯一真相源**：agent 产出全部经 conv→看板派生（已实现 80%，board_derive 单写者派生）
3. **A2A/AgentSpace 观望**：等芭迪框架被 AgentRouter 支持或 A2A 生态成熟再评估

## 5. 方法论沉淀

- **调研先于重建**：先查「有没有人解决过」再手搓。A2A 的 push/GetTask 模式与我们的指纹+哨兵解决同一问题，前者是协议级后者是脚本级
- **架构前提必须实测**：「Hermes 被@开新对话」从未验证就当作前提，衍生出 conv+哨兵+看板整套补偿机制；实测发现群 session 本就是长对话
- **评估外部方案看三个匹配**：①自己的 agent 能否接入（芭迪=CodeBuddy 是硬约束）②部署成本 vs 当前基建 ③它解决的是不是你的问题（AgentSpace 解决「平台托管 agent 治理」，不解决「现有 Bot 可靠协作」）