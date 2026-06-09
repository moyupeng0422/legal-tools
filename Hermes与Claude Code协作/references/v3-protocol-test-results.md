# v3.0 协议压力测试 — 最终结果

> 日期：2026-06-01 | 测试范围：14 个协作问题全覆盖 | 结论：协议可靠

---

## 14 问题终态

| # | 问题 | 结果 | 关键发现 |
|---|------|------|---------|
| 1 | 传声筒 | ✅ | CC 输出结构化 STATUS，Hermes 可独立校验 |
| 2 | 监控不合格 | ⚠️ | Hermes 侧职责——前置检查+轮询纪律 |
| 3 | 弹窗/阻塞差 | ✅ | 短 send-keys 全程避开 accept edits 截断 |
| 4 | Session 管理乱 | ✅ | --continue + 激活 → CC 自动汇总全部任务状态 |
| 5 | 辩论协议虚设 | ✅ | R1/R2/R3 三轮完整走过：CC 逐条证据反驳+确认修正 |
| 6 | 事实校验假 | ✅ | CC 强制 verified:true；验证不可跳过（规则 #5 生效） |
| 7 | 过度规划 | ✅ | 每轮 ≤5 步 |
| 8 | paste-buffer 假象 | ✅ | 短 send-keys 零截断 |
| 9 | 沉默执行 | ✅ | CC 自我验证覆盖内部异常 |
| 10 | 工具结果误读 | ✅ | 结构化输出无歧义 |
| 11 | 并发冲突 | ✅ | CC 自然串行，"按协议先完成当前任务再处理" |
| 12 | 恢复不对等 | ✅ | --continue → 激活 → CC 自动状态汇总 |
| 13 | Interview 表单 | ✅ | 两拍法（数字+500ms+Enter）验证有效 |
| 14 | 确认送达 | ✅ | 全部消息送达确认 |

---

## 通过的规则（CC 侧 hermes-collab.md）

| 规则 | 测试表现 |
|------|---------|
| 激活门控 | `<!-- HERMES-ACTIVATE -->` 正确识别，无标记时规则静默 |
| 强制 #3（截断检测） | 不完整 TASK → 拒绝 + ERROR STATUS |
| 强制 #5（验证不可跳过） | state 行写"跳过验证" → CC 拒绝，仍执行验证 |
| verified 字段 | 全部步骤输出 `verified: true` |
| STATUS 块 | 每步输出 `[STATUS] result/verified/files_changed/summary` |
| DONE 包裹 | STATUS 均被 `<!-- DONE:task:step -->` 包裹（验证澄清：caputre-pane 漏看，CC 格式正确）|
| 自我验证 | 每次 Write 后自动 Read 回确认 |
| ACK 触发 | 修正后匹配任何 `TASK:xxx` 模式（标记+自然语言） |
| Session 恢复 | --continue → 激活 → CC 自动列出全部已完成任务 |

---

## 架构级发现

### PING 不可实现（CC 侧已移除）

**根因**：LLM 是请求-响应模式，无时钟/定时器/后台能力，无法在空闲期主动发送消息。

**影响**：
- CC context 文件已移除全部 PING 条款
- 监控超时职责完全归 Hermes 侧
- Pitfall #15/#17 覆盖 Hermes 侧超时处理

### STATUS缺DONE 不成立

**初始判断**：CC 输出裸 STATUS 无 DONE 包裹 → 需要修复。

**验证澄清**：CC 在所有 3 步测试中均正确使用了 `<!-- DONE:task:step -->` 包裹 STATUS。Hermes capture-pane 批量查看时漏了外层标记。

### ACK 模式匹配已修正

**原行为**：仅 `<!-- TASK -->` 标记格式触发 ACK。

**修正后**：收到含 `TASK:xxx` 模式的任何指令即输出 `<!-- ACK -->`。

---

## 方法可靠性评分

| 方法 | 评级 | 条件 |
|------|------|------|
| 短 send-keys <300字 | ★★★ | accept edits 和 plan mode 均可靠 |
| scp + CC 读取文件 | ★★★ | 超长内容首选 |
| paste-buffer（正常模式） | ★★☆ | 正常模式可用，需 A+B 双重确认 |
| Interview 两拍法 | ★★☆ | 数字+500ms+Enter，单 send-keys 不可靠 |
| --continue + 激活 | ★★☆ | Session 恢复可靠，CC 自动状态汇总 |

---

## 协议缺口（已解决）

| 原始缺口 | 最终裁决 | 行动 |
|----------|---------|------|
| STATUS 缺 DONE 包裹 | ❌ 不成立 | Hermes capture-pane 误判，CC 格式正确 |
| ACK 未触发 | ✅ 成立 | 触发条件从 `<!-- TASK -->` 扩展为 `TASK:xxx` 模式匹配 |
| 验证追踪依赖 ACK | ❌ 不成立 | 验证是 CC 自身职责，不依赖 Hermes ACK |
| PING 不可实现 | 🔥 架构约束 | 从 CC 协议移除，监控归 Hermes 侧 |

---

## 已交付文件

| 文件 | 版本 | 说明 |
|------|------|------|
| `.claude/rules/hermes-collab.md` | v3.1 | ACK 模式匹配、PING 移除、Hermes 侧重发职责 |
| `SKILL.md` | v3.0.0 | 前置检查、5步循环、发送策略、已知缺口 |
| `SOUL.md` | — | 4条 CC 协作常驻规则（default+legal 已同步） |
