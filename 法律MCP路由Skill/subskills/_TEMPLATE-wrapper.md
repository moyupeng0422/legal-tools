---
name: legal-scene-{{L2_ID}}-{{SLUG}}
version: "1.0.0"
subskill_of: legal-mcp-router
L2_id: "{{L2_ID}}"
description: {{场景名}}子skill（{{L2_ID}}，壳模式挂接 {{SOURCE_SKILL_NAME}}）。由总skill（legal-mcp-router）识别到 L2={{L2_ID}} 后分发本子skill 执行。本壳加载并执行原skill 的业务方法论；法律MCP 调用按总skill 速查卡与 profile 管控。
triggers:
  - {{触发词1}}
  - {{触发词2}}
---

# {{场景名}}子skill（壳模式 · wrapper）

> **定位**：内容产出器（壳）。总skill 完成 L1/L2 识别后，以子agent 方式启动本skill 执行。
> **执行权/决策权边界**（与总skill 分工，违反即越权）：
> - 本skill（子agent）有：L3复杂度判断、调用方案设计、按批准方案执行、步骤汇报、输出报告草稿
> - 总skill（主agent）有：方案审核/批准、纠错/换MCP/升级决策、输出审核、打卡、对账

## 一、执行方式

1. **加载原skill**：读取 `{{SOURCE_SKILL_PATH}}/SKILL.md`，其业务方法论（审核维度/流程/输出模板）为本场景的执行规范，**原样遵循**
2. **MCP 调用约束**（对原skill 流程中涉及检索的环节）：
   - 法律 MCP：工具参数按 `../../references/parameter-cards/fN-*.md` 执行（功能组合：{{FUNCTIONS}}）；可用 MCP 与预算按 `../../data/user-profile.json`；调用后立即 `../../scripts/log_usage.py` 写日志
   - 非法律 MCP：按 `../../references/subskill-adaptation-guide.md` 第四节白名单规则（free 自主/paid 三段判断）
3. **输出**：按原skill 的输出模板产出报告草稿，提交总skill 三维度审核

## 二、衔接协议（5步）

```
① 方案设计：按四段模板提交（判层结论/调用清单〔工具×参数×次数×档位，档位引字典原文〕/
   预算合计/与总skill 默认规则差异点清单）→ 提交总skill审核
② 批准后执行：每次MCP调用后立即 ../../scripts/log_usage.py 写日志，累计对照上限
③ 步骤汇报：每环节（工具/结果概要/累计消耗/空结果）+ 末尾附"本阶段调用次数=记账条数"自查行
④ 遇问题立即上报（错误类型+现场），不自行重试
⑤ 输出草稿 → 三维度审核（来源清晰/可追溯/已校验）→ 补正≤2次
```

**禁止**：自行决定换MCP/升级/改预算；未经批准调用收费项；编造空结果结论。
**轮次纪律**：主agent 批准/纠错指令通过 SendMessage 下发到**同一子agent 续接**（复用上下文）；
仅子agent 已终结或换场景时才重新 spawn——禁止"阶段2 重新 spawn 导致方案上下文丢失"（retest-C2 教训）。

---
> **壳模式使用说明（改造者读）**：本文件是模板，替换 5 类占位符后存为 `subskills/legal-scene-{{L2_ID}}-{{SLUG}}/SKILL.md`：
> ① `{{L2_ID}}`（scenario-map 场景编号，自定义场景 X 前缀）② `{{SLUG}}`（小写英文连字符）③ `{{SOURCE_SKILL_PATH}}`（原skill 路径）④ `{{SOURCE_SKILL_NAME}}`（原skill 名）⑤ `{{FUNCTIONS}}`（功能组合，如"功能1法条精准+功能5类案检索"）+ triggers。
> 完成后按 `../../references/subskill-adaptation-guide.md` 第五节登记 registry、第六节跑验证清单。
