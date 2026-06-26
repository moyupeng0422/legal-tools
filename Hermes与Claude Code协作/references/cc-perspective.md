# CC 视角：协作问题诊断与建议

> 来源：2026-05-31 Hermes × CC 协作诊断讨论（Session: "CC协作Skill检修"）
> Claude Code v2.1.72 / glm-5-turbo

## 一、CC 确认的六大问题（与 Hermes 一致）

CC 逐条回应 Hermes 总结的六类问题，全部认同，并补充了根因分析：

| # | Hermes 问题 | CC 确认 | CC 补充的根因 |
|---|------------|---------|--------------|
| 1 | 传声筒 | ✅ | Hermes 缺乏明确的「不一致信号列表」，不知道什么情况该触发辩论 |
| 2 | 监控不合格 | ✅ | 轮询间隔太长，建议 30s 检查 + 60s 无输出超时 |
| 3 | 弹窗阻塞 | ✅ | paste-buffer 截断是老大难，本次讨论中再次验证 |
| 4 | Session 乱 | ✅ | --resume 后上下文可能被压缩，但 Skill 假定 CC 还记得 |
| 5 | 辩论虚设 | ✅ | **CC 完全不知道辩论协议存在**（SKILL.md 只对 Hermes 可见） |
| 6 | 校验假 | ✅ | Checklist 是"建议"不是"强制"，未嵌入每步操作 |

## 二、CC 发现的 Hermes 盲区（6 个新问题）

### 7. 过度规划
Hermes 倾向在一次交互中给 CC 很长的多步指令，但 CC 的上下文窗口在处理长指令时可能丢失中间步骤的细节。**单次不超过 5 步。**

### 8. paste-buffer 假象
Hermes 认为已 paste 成功，实际传输中内容被截断或格式错乱（特别是中文内容、长 JSON），导致 CC 基于不完整信息做了错误操作。**Paste 后必须 verify 内容完整性。**

### 9. 沉默执行
CC 执行中发现异常（工具调用失败、文件不存在、命令错误）并输出了响应，但 Hermes 的 capture-pane 没有捕获到，Hermes 误判任务完成，继续下一步。根因是 **轮询间隔太长** + **停止信号不全**。

### 10. 工具结果误读
CC 返回的表格、列表经 SSH 传输后格式变化（Markdown 表格在 capture-pane 中对齐错乱），Hermes 的解析器可能读错。

### 11. 并发冲突
Hermes 在 CC 仍处理上一个任务（● 标记进行中）时发来新指令，导致 session 冲突或操作覆盖。**必须等 ❯ 出现才能发新指令。**

### 12. 恢复不对等
Skill 里 CC 崩溃有恢复流程，但 Hermes 自身卡住/超时时没有对等机制。CC 那边等半天没收到 Hermes 指令，只能被动等待。**双方都需要超时恢复机制。**

## 三、四个结构性缺陷

CC 将六类问题提升到架构层面，指出根本原因不是执行失误，而是协作模型设计缺陷：

```
┌────────────────────────┬───────────────────────────────────────────────────┐
│       结构缺陷          │                       表现                        │
├────────────────────────┼───────────────────────────────────────────────────┤
│ 单向模型               │ Hermes→CC→Hermes 是单向的，缺双向心跳和状态同步   │
│ Skill 只管 Hermes      │ 所有协议（监控、辩论、校验）都定义在 Hermes 侧，   │
│                        │ CC 侧没有对应约束。CC 说："我不知道辩论协议存在"   │
│ 状态不持久化           │ 任务进度只存在 Hermes 记忆和 CC 上下文里，断开就丢 │
│ 验证是"建议"不是"强制" │ Verification Checklist 可跳过，未嵌入执行流程     │
└────────────────────────┴───────────────────────────────────────────────────┘
```

## 四、CC 的具体改进建议

### 4.1 双向心跳协议
```
Hermes 发指令 → CC 回 ACK:step_N → CC 执行 → CC 发 DONE:step_N, NEXT:step_N+1
    ↓ 超时未收到 ACK                                        ↓ 超时未收到新指令
    重发指令                                                CC 主动问状态
```

### 4.2 每步交互状态摘要
每次 paste-buffer 末尾附不超过 3 行的状态摘要：
```
[state: task_id=xxx step=3/5 done=2 next=fix_encoding ctx=已修复2个文件]
```

### 4.3 共享状态文件
在服务器维护 `cc-task-state.json`，Hermes 写入最新指令，CC 写入最新进度。任何一方恢复后先读此文件。

### 4.4 CC 防御性复述
CC 收到指令后，必须用自己的话复述任务目标（1-2 行），等 Hermes 确认后再执行。拦截上下文断裂问题。

### 4.5 Chunk Size 限制
单次 paste-buffer 指令不超过 5 个步骤，超过必须拆分。

### 4.6 Paste 后强制 Verify
Paste-buffer 发送后，Hermes 必须通过 capture-pane 确认消息内容完整未被截断。

### 4.7 强制 Edit 后 Read
每完成一批 Edit 操作，CC 必须 Read 修改点前后 10 行确认内容正确性。Hermes 在 Checklist 中强制检查此项。

### 4.8 辩论模式开关
在状态摘要中添加 `dispute: true/false` 字段。Hermes 设为 true 时 CC 进入辩论模式（遵循 R1/R2/R3 协议），双方用统一框架对话。

### 4.9 事后双向 Review
任务完成后，Hermes 做一次反向验证（capture-pane + diff），CC 也主动做一次 self-review。双方结论不一致时标注「需人工确认」。

## 五、本次讨论中验证的问题

- **Pitfall #12（Plan mode paste-buffer 不可靠）再次实锤**：~600 字消息在 plan mode 下 paste-buffer 严重截断，CC 只收到末尾几行，需分两次发送完整内容。
- **Pitfall #18（CC 对 Skill 无感知）首次确认**：CC 明确表示"我不知道辩论协议存在，因为 SKILL.md 只对 Hermes 可见"。
- **Interview 表单两拍法**：`send-keys '3' Enter` 单次发送被 CC 忽略不生效（本轮实测）。必须分两拍：`send-keys '3'` → sleep 0.5s → `send-keys Enter`。选择后 capture-pane 验证生效。
- **假发送问题**：Hermes 认为 paste-buffer 已成功（返回值正常），但 capture-pane 显示内容截断。**必须每次 paste 后 verify，不能依赖 paste-buffer 返回值。**

## 六、v3.0 解决方案（2026-06-01 确立）

### 核心创新：CC 侧上下文文件 + 激活门控

> **关键转折**：用户指出不需要每次 scp 文件——一次性部署 + 标记激活即可。

| 旧方案（v2.x） | 新方案（v3.0） |
|---------------|---------------|
| Hermes 每次 scp 写入 context 文件 | 一次性部署到 `.claude/rules/` |
| 断开时删除文件 | 文件常驻，零运维 |
| 文件存在 = 协作模式 | 通过 `<!-- HERMES-ACTIVATE -->` 标记按需激活 |
| 人类操作时需删除文件避免干扰 | 激活门控自动静默，人类无感 |

### P0 交付物

1. **CC 侧 context 文件**：`<windows-project-root>\.claude\rules\hermes-collab.md`（143行，含行为守则、结构化格式、降级规则）
2. **SOUL.md 4 条常驻规则**：强制加载 skill / 发送确认 / 先质疑后汇报 / 发现违规要指出
3. **SKILL.md v3.0.0**：前置检查、5步循环、激活流程、发送策略、新 pitfalls
4. **完整整合方案**：`~/.hermes/cc-integrated-plan.md`（311行，含优先级 P0-P3、降级规则、冲突点）
