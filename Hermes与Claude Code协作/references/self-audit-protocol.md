# Reference: 自查审计协议

> 来源：2026-06-01 Hermes 自查 CC 协作合规性，发现 5 项违规，经与 CC 辩论后双边修正。

## 何时触发

- 每完成一轮密集 CC 协作后（≥3 次交互）
- 用户要求"自查有没有不符合要求的地方"
- 怀疑协作质量下降时（频繁截断、漏记、跳过验证）

## 审计流程

```
1. 对照 Verification Checklist 逐条反查近 N 次 CC 交互
2. 每条标注：✅ 遵守 / ⚠️ 可疑 / ❌ 违规
3. 对 ❌/⚠️ 项归类为可操作问题
4. 与 CC 进入辩论 R1→R2→R3 讨论改进
5. 输出修正方案，双方同步更新规则文件
6. 本次审计发现写入 skill 的 pitfall 列表（反面教材）
```

## 审计维度

| 维度 | 检查来源 | 要点 |
|------|---------|------|
| 前置检查 | SKILL.md 前置强制检查表 | tmux session、CC 空闲、状态摘要、步骤数 |
| Checklist | SKILL.md Verification Checklist | 9 项逐一反查 |
| 任务映射 | `claude_task_map.json` | 近期任务是否全部记录 |
| 状态持久化 | `cc-task-state.json` | 是否维护（Hermes 职责） |
| Paste 可靠性 | capture-pane 记录 | 是否有截断未检测到 |

## 审计输出格式

```
## 自查报告

### 🔴 明确违规
1. xxx → 违反：SKILL.md XXX

### 🟡 疑似违规
2. xxx

### 📋 自查清单（对照 Verification Checklist 逐条）
| # | 要求 | 本次 | 
|---|------|------|
```

## 审计后行动

1. **P0**：CC 侧规则缺口 → 补充 hermes-collab.md
2. **P1**：Hermes 侧流程缺口 → 更新 SKILL.md
3. **P2**：skill 措辞修正、pitfall 补充例外
4. **记录**：审计结果写入 v3-protocol-test-results.md 或新 reference
5. **任务映射**：补录漏记的任务到 claude_task_map.json

## 反面教材

本 skill 的 Pitfall #17（task_map 漏记）来自 2026-06-01 自查——v3.0 测试中连续漏记 5+ 条 CC 任务，自查后才补录。skill 自身的 checker 没有遵守 skill 自己的规则，是典型的"医生不自医"。
