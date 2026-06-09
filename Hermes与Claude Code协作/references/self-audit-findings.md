# 协作纪律自查 — 2026-06-01

> 自查触发：v3.0 协议压力测试完成后，对照 SKILL.md 逐条审计发现 5 类问题。

---

## 自查方法论

**审计标准**：SKILL.md 的 Verification Checklist（9 项）+ 前置强制检查（4 项）+ 24 条 Pitfalls + 结构性缺陷与改进方向。

**审计范围**：2026-05-31 至 2026-06-01 全部 CC 协作会话，包括 v3.0 协议修订、14 问题压力测试、CC context 文件部署、激活门控测试、并发/恢复测试。

---

## 发现问题

### 🔴 明确违规

**1. claude_task_map.json 严重滞后**

skill 要求每次 CC 操作后必须记录。实际文件只有 5 月 29-30 两条旧记录。以下任务全部漏记：
- v3.0 协议修订与压力测试（14 问题验证）
- hermes-collab.md context 文件部署（P0）
- 激活门控测试、ACK/DONE 模式匹配验证
- 辩论协议 R1/R2/R3 完整测试
- #11 并发冲突测试、#12 恢复不对等测试

违反：Verification Checklist 第 7 条 + Pitfall #17

**2. cc-task-state.json 从未创建**

skill 在「结构性缺陷」中承认状态不持久化是核心缺陷，建议维护共享状态文件——文件不存在。

违反：skill 自身的改进建议从未落地

**3. 前置检查 #3（状态摘要）未遵守**

skill 要求每次指令末尾必须附带 `[state: id=X step=M/N done=P ctx=摘要]`。
部分测试指令缺失此行（如 test-003 补充删除指令、test-004、test-005 首条指令）。

违反：前置强制检查表 #3 + 每步交互状态摘要（强制）

### 🟡 疑似违规

**4. 前置检查 #2（CC 空闲确认）在 #11 测试中被故意违反**

#11 并发冲突测试中，第一个慢任务发出后立即追发第二个——此时 CC 正在 ● 执行。
测试目的合法，但 pitfall #16 措辞绝对化，未区分测试场景。

**5. Verification Checklist 未完整走完**

测试结束后直接输出结论表格，未逐项展示 9 项 checklist 执行过程。
违反：Checklist 标题「**每次 CC 操作完成后强制执行，不可跳过**」

---

## 与 CC 讨论的修正方案

| 问题 | 最终方案 | 负责方 | 优先级 |
|------|---------|--------|--------|
| Q1 task_map 漏记 | CC 在 DONE 块嵌入 [TASK_MAP]；Hermes 监控闭环解析后写文件 | CC 输出 + Hermes 写 | P1 |
| Q2 task-state 缺失 | Hermes 创建维护 cc-task-state.json；从 skill 删除 CC 维护职责 | Hermes | P2 |
| Q3 state 缺位 | CC 严格执行规则 #1（缺 state 行拒绝）；Hermes 发送前自检 | 双方 | P0 |
| Q4 checklist | CC DONE 块嵌入 [CHECKLIST]；区分自证项 vs 核实项 | CC 输出 | P0 |
| Q5 pitfall #16 | hermes-collab.md 新增 TEST-MODE 段落；skill 已补例外说明 | CC 写 | P2 |

---

## DONE [TASK_MAP] 块格式

```
<!-- DONE:task-X:step-N -->
[STATUS]
  result: pass
  verified: true
  ...
[TASK_MAP]
  task_id: test-003
  step: 3/3
  session: v3协议压力测试与14问题验证
  timestamp: 2026-06-01T14:30:00+08:00
[/TASK_MAP]
[/STATUS]
<!-- /DONE -->
```

Hermes 解析：`\[TASK_MAP\](.*?)\[/TASK_MAP\]` 正则提取 → 键值对解析 → 写入 `claude_task_map.json`。

---

## 关键教训

1. **/rename 后立即写 task_map**，不等任务完成——上下文被压缩后记录必然丢失。
2. **Paste-buffer 截断是真实风险**：本次讨论中 Q1-Q3 就被截断，CC 只收到 Q4-Q5。
3. **状态摘要不写就不能发**：Hermes 侧发送前自检是最后一道防线。
4. **Checklist 不是建议是纪律**：标题「强制执行，不可跳过」要当真。
5. **CC 无法直写云端文件**：所有云端持久化由 Hermes 侧完成，CC 只输出结构化数据。

---

## 2026-06-09 自查 — vault 同步方案协作

> 自查触发：用户要求"看看最近关于 cc 协作是不是又发现很多老毛病"。

### 发现问题

#### 🔴 高频复犯（老毛病）

| # | 问题 | Pitfall | 上次违规 |
|---|------|---------|---------|
| 1 | **连 CC 前不加载协作 skill** | #63 #0 | 6/7, 6/8, 6/9（连续三次） |
| 2 | **启动序列"三连错"**：不 cd 项目目录 / rename 不带前缀 / resume 用启动参数 | #89 #90 #48 | 6/8 连续三次，6/9 再犯 |
| 3 | **跳过前置检查（两步确认、状态摘要、消息格式）** | #0 #43 | 持续 |
| 4 | **CC 纯讨论任务自动 Explore 浪费 token** | #72 #92 | 6/6, 6/9 |

#### 🟡 本次新增/复现

| # | 问题 | 说明 |
|---|------|------|
| 5 | Accept edits 消息排队合并/间隔错乱 | 多条消息 send-keys 后内容被异常拆分 |
| 6 | CC 响应队列停滞 | CC 回完一条后不自动处理排队消息 |

### 改进行动

| 行动 | 状态 |
|------|------|
| 启动序列六步法写入 skill 最醒目位置（CC Pane 后第一段） | ✅ |
| 前置检查加 check #-1（skill 加载优先） | ✅ |
| tmux vs Print Mode 决策树（默认倾向 Print Mode） | ✅ |
| 本次审计记录写入 self-audit-findings.md | ✅ |

### 关键教训

6. **加载 skill 是第一步不是最后一步**：3 次连续违规说明仅靠"记住"不够，必须流程强制——检查 #-1 就是强制手段。
7. **启动序列要当"咒语"背**：cd→启动→激活→rename 是固定序列，每次操作前默念一遍再执行。
8. **默认走 Print Mode 减少 tmux 接触面**：tmux 的结构性缺陷（截断、轮询、弹窗）无法根治，减少使用频率就是减少出错概率。
