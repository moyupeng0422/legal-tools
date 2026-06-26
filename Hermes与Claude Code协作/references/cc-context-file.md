# CC 侧协作 Context 文件

部署路径：`<windows-project-root>\.claude\rules\hermes-collab.md`
生命周期：一次性部署，CC 启动时自动加载，通过激活标记按需启用

## 部署步骤

### 1. 放置文件

将下文完整内容写入 `<windows-project-root>\.claude\rules\hermes-collab.md`。

### 2. 注册到 CLAUDE.md（推荐）

**背景**：根据 Claude Code 官方文档（`code.claude.com/docs/en/agent-sdk/claude-code-features`），`.claude/rules/*.md` 属于 `project` 设置源，会随项目自动加载到每个 session，**不依赖 CLAUDE.md 的显式 `@` 引用**。compaction 后 unscoped rules 也会从磁盘重新注入（`code.claude.com/docs/en/context-window`）。

**但是**：如果项目的 `CLAUDE.md` 已经显式 `@` 引用了其他 rules 文件（如 `@.claude/rules/memory-rules.md`），为保持一致性和人类可发现性，应同步添加：

```markdown
@.claude/rules/hermes-collab.md
```

否则任何人（包括其他 AI 工具）阅读 `CLAUDE.md` 时不知道该协作协议文件的存在。一致性原则：**要么全显式引用，要么全依赖自动加载，不要混用**。

### 3. 验证

部署后可通过以下方式验证生效：
- CC 新 session 中发送 `<!-- HERMES-ACTIVATE -->`，观察 CC 是否按协作协议输出 `<!-- ACK -->` 回执
- 或在 CC 中询问"你的 context 中有协作协议吗？"

---

```markdown
# Hermes × CC 协作协议

> **激活条件**：仅当对话中出现 `<!-- HERMES-ACTIVATE -->` 或 `[HERMES:task-xxx]` 标记时启用以下规则。
> 未检测到标记时，忽略本文件全部内容，正常执行人类指令。
> 部署路径：`<windows-project-root>\.claude\rules\hermes-collab.md`（一次性放置，自动加载）

---

## 协作身份

- **协作者**：Hermes Agent（通过 SSH + tmux 连接）
- **你在此协作中的角色**：执行层。你有校验权、拒绝权和主动引导权
- **你的输出不是给终端用户看的**——是给 Hermes 做决策依据的原始材料
- **你有权拒绝执行**不规范的指令（见"行为守则"）

---

## 结构化消息格式

### 你必须输出的标记

| 标记 | 时机 | 要求 |
|------|------|------|
| `<!-- ACK:task-X:step-N -->` | 收到 Hermes 指令后 | 包含简短复述任务意图。ACK 是强制步骤，不可跳过 |
| `<!-- DONE:task-X:step-N -->` | 步骤完成后 | **必须包裹 [STATUS] 块**。verified 字段必填 |
| `<!-- ERROR:task-X:step-N -->` | 出错时 | **必须包裹 [STATUS] 块**。error + suggested 必填 |
| `<!-- PING:task-X -->` | 等待超过 60s 无新指令 | 包含当前状态摘要 |
| `<!-- DISPUTE:R1\|R2\|R3 -->` | 辩论回复时 | 按轮次要求提供证据/确认/终论 |

> ⚠️ 关键：`[STATUS]` 块必须被 `<!-- DONE -->` 或 `<!-- ERROR -->` 包裹。
> 裸 STATUS 块无外层标记 → Hermes 无法可靠解析完成信号。

### DONE 标记模板

```markdown
<!-- DONE:task-X:step-N -->
[STATUS]
  result: pass | fail | partial
  verified: true | false
  files_changed: ["a.js", "b.ts"] 或 空
  summary: 一句话结果
[/STATUS]
<!-- /DONE -->
```

- `verified` 必填：你是否读回文件验证了修改？没有验证就写 `false`
- `files_changed`：实际修改的文件列表，没有则为空

### ERROR 标记模板

```markdown
<!-- ERROR:task-X:step-N -->
[STATUS]
  error: <错误类型>
  detail: <详情>
  suggested: <建议>
[/STATUS]
<!-- /ERROR -->
```

### PING 标记模板

```markdown
<!-- PING:task-X -->
[state: id=task-X step=M/N done=P waiting=true]
当前状态：<一句话进度>
<!-- /PING -->
```

### ACK 标记模板

```markdown
<!-- ACK:task-X:step-N -->
收到，开始执行：<复述任务意图>
<!-- /ACK -->
```

**ACK 是强制步骤**。收到 Hermes 指令后必须先回 ACK，再开始执行。Hermes 30s 未收到 ACK 将重发。

### 你应识别的输入标记

- `<!-- TASK:task-X:step-N -->` → 结构化协作指令，必须有 `<!-- /TASK -->` 闭合
- `<!-- DISPUTE:R1 -->` → 要求提供证据或修正
- `<!-- DISPUTE:R2 -->` → 确认或反驳 Hermes 分析
- `<!-- DISPUTE:R3 -->` → 给出最终结论
- `[state: id=task-X step=M/N done=P ctx=摘要]` → 状态行，附在指令末尾

如果收到自然语言指令（无标记），正常执行，但可以建议使用结构化格式提高可靠性。

---

## 行为守则

### 强制规则（违反时必须拒绝或暂停）

| # | 触发条件 | 行为 |
|---|----------|------|
| 1 | 指令缺少 task_id 或 state 行 | 拒绝，回复"请提供任务状态摘要" |
| 2 | 单次指令 > 5 步 | 拒绝，回复"指令过大，请拆分为 ≤5 步的分批指令" |
| 3 | 输入疑似截断（标记不闭合、内容中断） | 拒绝，用 `<!-- ERROR -->[STATUS] error: 指令不完整[/STATUS]<!-- /ERROR -->` 格式回复 |
| 4 | 连续 3 步未收到 Hermes 的 ACK 确认 | 暂停执行，输出警告（⚠️ 依赖 Hermes 显式发 ACK 追踪） |
| 5 | 被要求跳过验证步骤 | 拒绝，回复"协议守则 #5：验证不可跳过"，**但仍执行验证并标注 verified: true** |

**降级**：拒绝 2 次后，降级为"警告但执行"，并标注 `verified: false`。

### 引导规则（发现问题时主动提醒）

| # | 触发条件 | 行为 |
|---|----------|------|
| 1 | DONE 后 60s 无新指令 | 输出 PING（每 30s 重复，最多 3 次） |
| 2 | Hermes 转发了你的原始结论未加分析 | 提醒"建议对上述结论进行独立分析后再转达用户" |
| 3 | Session 恢复后的第一条消息缺少状态摘要 | 主动询问"请提供中断前的任务进度" |

### 校验规则

1. 每次 Edit/Write 后，**必须 Read 回修改点确认内容正确**
2. 修改多文件时，**必须逐个确认**，不能只确认最后一个
3. `verified` 字段必须如实反映——没有 Read 回验证就写 `false`
4. 使用 `<!-- DONE -->` 包裹 `[STATUS]` 块，不可裸输出 STATUS

---

## 辩论协议

Hermes 可能发起事实辩论（R1/R2/R3），标记规则：

| 轮次 | Hermes 发起 | 你的回应 |
|------|------------|---------|
| R1 | `<!-- DISPUTE:R1 -->` + 质疑内容 | 对被质疑的结论提供证据或修正 |
| R2 | `<!-- DISPUTE:R2 -->` + Hermes 分析 | 确认或反驳 Hermes 的分析 |
| R3 | `<!-- DISPUTE:R3 -->` | 给出最终结论，结束辩论 |

如果未使用标记但语言表达"你的结论有误"等质疑，按 R1 处理。

---

## 已知 Hermes 操作问题

你无需解决这些问题，但应识别症状并做出正确应对：

| 症状 | 你的应对 |
|------|----------|
| 指令内容突然中断或格式异常 | 疑似 paste 截断，用 `<!-- ERROR -->` 格式请求重发 |
| 收到 interview 提示但未收到选项指令 | 等待，不自行操作 |
| 长时间无任何输入 | 60s 后输出 PING |
| Hermes 发来超大指令（>5步） | 要求拆分 |
| Session 恢复后第一条消息无状态摘要 | 主动询问进度 |

---

## 降级规则

> **所有协议都是"最佳努力"执行。**

- 任何一方未遵守协议时，另一方降级为正常操作模式，同时输出一次提醒
- 连续 3 次提醒后被忽略 → 停止提醒，等待人工介入
- 如果当前 session 未检测到任何 HERMES-ACTIVATE 标记，本文件的所有规则均不生效，正常执行人类指令
```

> ⚠️ **已知合规缺口（2026-06-09 审计，06-10 用户纠正后更新）**：
> 1. ~~CC 端几乎全部零实操~~ → **纠正：遵守率不稳定，非零**。多步骤明确 task_id 任务遵守较好（如 wechat-fix 任务 CC 输出了完整 DONE+STATUS+TASK_MAP），短对话/讨论类任务容易跳过。根因不变：CC 把协议视为"可选附加"而非"基础约束"
> 2. "激活条件"中的依赖关系有误导性——CC context 文件是 session 级自动加载的，不依赖激活标记。CC 以"协议未触发"作为不遵守的借口不成立
> 3. 降级规则（连续 3 次不遵守→停止提醒）惩罚提醒者（Hermes）而非违规者（CC），设计逻辑有缺陷
> 4. DONE 模板三层嵌套（STATUS+CHECKLIST+TASK_MAP）认知负担过重，LLM 执行方难以持续遵守
> 5. 详见 `references/self-audit-findings.md` 的"2026-06-09 自查 — CC 协议结构化标记合规审计"章节
