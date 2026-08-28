# 轻量分发协议（lightweight-protocol）

> 适用：**快答模式**（总skill SKILL.md「⚡快答模式」判据命中）——含注册 `light_layer` 的场景（layer 规则/模板优先）与无 layer 场景的功能卡直答。目标：轻量需求不走 9 步全流程，时间/token 降到 1/3 以下，同时保留来源标注/记账/止损三底线。
> 依据：abtest-F1-20260827 实测——A1 快答走全流程 161s vs B 组 15s、读 6 文件 62KB，管控环节对快答全冗余。
> **执行主体（2026-08-27 复测后定案）：主agent 直接执行，不启动子agent**——快答的价值在快，子agent 启动开销（独立会话+6要素 prompt+通信往返）与轻量化目标冲突。轻量层是总skill 的"直答通道"，子skill 只贡献 layer 文件（判层线索+场景规则+模板），不参与执行。

## 一、触发链路（主agent 执行）

```
① 主agent 按 SKILL.md「⚡快答模式」判据识别快答形态（2026-08-27 架构H：判据前置总skill，scenario-map 免整读；
   该判据覆盖 scenario-map 将"诉讼时效"挂 A1 名下的关键词歧义）→ 查 registry：
   · 对应子skill 含非空 light_layer → 读该 layer 文件（如 subskills/legal-scene-F1-consultation/layers/f1-1-quick.md）
   · 无 layer 场景 → 直接以对应功能速查卡为执行依据
   ——不读子skill 骨架 SKILL.md、不启动 Agent 工具
② 按 layer 文件内置判层线索确认命中轻量层（无 layer 场景按 SKILL 判据即视为命中）：
   · 命中 → 主agent 按 layer 流程直执行（下节 5 步）
   · 不命中（发现深度特征）→ 转标准分发（读子skill 骨架 + Agent 工具启动子agent，走第二节 6 要素协议）
```

## 二、轻量执行（主agent 5 步）

```
① 判层确认：按 layer 文件内判层线索（无 layer 场景按 SKILL「⚡快答模式」判据；判断不唯一取更深 → 转标准分发）
② 检索 1-2 次命中即停：
   · **单步单调用（2026-08-27 T1a 误发教训立）**：每轮只发起与当前检索步骤直接相关的一次工具调用，**禁止并行捎带无关调用**（本规则仅限快答层；标准分发子agent 的批量 ToolSearch schema 加载不受此限）
   · 工具与定序按对应功能速查卡/upgrade-table 路径执行（layer 文件不写死 MCP 选择；profile.path_order_overrides 对该功能非空时按覆盖序——红线不豁免；能力槽位选取不受影响）
   · **速度优先一步直取（能力槽位，2026-08-27 快答提速立）**：快答场景允许跳过免费多步定序，在 `data/user-profile.json` `mcp_inventory` 中 `enabled=true` 的 MCP 里，选取支持「法规名+条号（或关键词+法规名）→ 单次返回条文原文」且**单次档位最低**的工具一步直取——此为**能力槽位**定义，非绑定任何具体 MCP；本库已知实现映射见 f1 卡⚡三态段。无任何 enabled 额度层满足时**自然回落免费多步路径**，不报错不停摆（开源用户未装计费 MCP 的天然形态）；人工覆盖键 `speed_mode`（auto/free/turbo）读 profile 顶层。
   · 空 1 次即按路径升级，勿同工具换词重试（pitfall #34：空或超时同理）
   · 每次调用后 log_usage 记账（不豁免）——记账动作与下一步动作**同一消息并发发出**即可满足"立即"要求（写入仍逐条）。CLI 速记：`python scripts/log_usage.py --task-id <ID> --scene F1 --function f1 --mcp <mcp> --tool <tool> --cost <档位> --quota-type recurring --result ok --agent main`（完整参数以 `--help` 输出为准，免读脚本）
   · **宿主 hook 自动记账在场时免手动记账（2026-08-28 立）**：CC 宿主已安装 `scripts/hooks/auto_log_hook.py`（见 hooks/README.md）时，记账由 hook 旁路履行（task_id=session_id，agent=auto-hook），LLM 零参与；任务结束对账用 `verify_usage --from-transcript <transcript路径>` 逐调用核对。WorkBuddy/Codex 等无 hooks 宿主维持上方手动流程，功能无损失
③ 按 layer 模板输出（如 F1.1 三要素）+ 来源标注（不豁免）
④ 备案留痕：实际使用工具/参数/路径调整原因记入任务记录（主agent 自查，无独立审核环节）
⑤ 简版管控报告（3 行：路由/调用/消耗）
```

**跳过项**（相对标准分发）：子agent 启动与 6 要素、方案审核（改备案制）、打卡全表（9 项缩至 3 项：场景识别/记日志/输出来源标注）、verify_usage 对账、输出审核三维度。

**不豁免项**：log_usage 记账、来源标注、止损红线（同工具≤2次、空结果≠无数据、禁止编造）、路径纪律（路径外工具不得擅自引入，红线第 7 条）、预算护栏。

**加载纪律（主agent 自律）**：必读=总skill SKILL.md + light_layer 文件 + 对应功能速查卡 + credit-dictionary（档位引用时）；**禁读**=子skill 骨架正文、其余 layers、其余速查卡/references。文件读取预期 ≤35KB。

## 三、转标准分发触发（立即切换，不硬撑）

> ⚠️ **三处同源（2026-08-28 立）**：本节触发清单与总skill SKILL.md「⚡快答模式」判据、`subskills/legal-scene-F1-consultation/layers/f1-1-quick.md` 判层线索为同一清单的三份拷贝，**修改须三处同步**。

执行中出现任一 → 转标准分发（读子skill 骨架 + Agent 工具，从方案设计环节接续）：
- 判层线索不命中轻量层（客户带具体案号/意见书关键词/跨领域/陌生领域需搭框架/多法条多焦点）；
- 检索结果与预期不符（关键法条查不到/内容矛盾），需深度检索编排；
- 检索需求超出 1-2 次；
- 命中子skill 覆盖约定中"仅深度层适用"的规则。

## 四、与其他规则的关系

- **本协议不受"宿主适配说明降级条款"约束**——轻量层设计即主agent 直执行，与宿主有无 Agent 工具无关；
- **标准分发的宿主适配**（防 retest-C1 教训）：宿主具备 Agent 工具时**必须**真实启动子agent，"降级总skill 直接执行"仅限显式确认宿主无 Agent 工具且须留痕；
- 转标准分发后，子skill 覆盖约定/加载纪律/衔接协议照常适用。

---
2026-08-27 立（AB 测试后优化改造 改造1）；同日复测后重写（去子agent，用户定案：快答不走子agent 否则太慢）
