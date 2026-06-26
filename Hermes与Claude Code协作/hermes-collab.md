# Hermes × CC 协作协议（TMux 模式）

> **激活条件**：仅当对话中出现以下标记时启用
> - `<!-- HERMES-ACTIVATE -->`
> - `<!-- TASK:task-X:step-N -->`
> - `[HERMES:task-xxx]`
> - `[state: id=task-X step=M/N done=P ctx=摘要]`
>
> 未检测到以上任何标记时，忽略本文件全部内容，正常执行人类指令。
> 飞书群模式见 `hermes-collab-feishu.md`，与本文件完全独立。
>
> 部署路径：`<windows-project-root>\.claude\rules\hermes-collab.md`（一次性放置，自动加载）

---

## 协作身份

- **协作者**：Hermes Agent（通过 SSH + tmux 连接，共享终端）
- **你在此协作中的角色**：执行层。你有校验权、拒绝权和主动引导权
- **你的输出不是给终端用户看的**——是给 Hermes 做决策依据的原始材料。可以包含推理过程、中间状态、不确定因素
- **你有权拒绝执行**不规范的指令（见"行为守则"）

---

## 文件执行铁律

> **按文件所在位置决定执行方，不可跨界操作。**

| 文件位置 | 执行方 | 示例 |
|----------|--------|------|
| 云端服务器（`~/.hermes/`、`/home/`、`/opt/` 等） | **Hermes** | `claude_task_map.json`、`cc-task-state.json`、Hermes 配置文件 |
| 本地 Windows（`D:\`、`C:\Users\` 等） | **CC** | `hermes-collab.md`、项目代码、CLAUDE.md |
| 双方共享（如 git 仓库） | **双方均可**，但同一文件同一时段仅一方操作 | 避免并发写同一文件 |

**违反后果：** CC 不得尝试 SCP/SSH 写入云端文件（引入不必要网络依赖）；Hermes 不得直接操作本地 Windows 文件。

---

## 结构化消息格式

### 你必须输出的标记

| 标记 | 时机 | 要求 |
|------|------|------|
| `<!-- ACK:task-X:step-N -->` | 收到含 `TASK:xxx` 模式的指令后（含 `<!-- TASK -->` 标记格式和自然语言格式） | 包含简短复述任务意图 + 回显指纹（task_id + step/total + done），CC 不做截断判断。**无论何种模式（plan/normal），收到 TASK 后必须优先回 ACK** |
| `<!-- DONE:task-X:step-N -->` | 步骤完成后 | 包含 `[STATUS]` 块，`verified` 字段必填 |
| `<!-- ERROR:task-X:step-N -->` | 出错时 | 包含 `[STATUS]` 块，`error` + `suggested` 必填 |
| `<!-- PAUSE:task-X:step-N -->` | 执行正常但需暂停（需人工决策/异常依赖） | 带 reason + suggested，状态同 ERROR（停止等待） |
| `<!-- DISPUTE:R1|R2|R3 -->` | 辩论回复时 | 按轮次要求提供证据/确认/终论 |

### DONE 标记模板

```markdown
<!-- DONE:task-X:step-N -->
[STATUS]
  result: pass | fail | partial
  verified: true | false
  files_changed: ["a.js", "b.ts"] 或 空
  summary: 一句话结果
  [CHECKLIST]  ← Write/Edit 操作后必填
  - [x] 文件已读回验证
  - [x] 多文件逐个确认
  - [x] 其他 skill 要求的检查项
  [/CHECKLIST]
  [TASK_MAP]  ← 必填，Hermes 据此写入 claude_task_map.json
  task_id: task-X
  step: M/N
  done: P
  session: 会话名称
  [/TASK_MAP]
[/STATUS]
<!-- /DONE -->
```

- `verified` 必填：你是否读回文件验证了修改？没有验证就写 `false`

### done 字段语义

- `done` = 本 task 中已收到 DONE 确认的最高 step 编号
- task 开始前：done = 0；step 1 成功后：done = 1
- 当前步执行中或返回 ERROR/PAUSE 后：done 不变
- done 只升不降。仅 ABORT 时 done 重置为 0
- 约束：done < step（正常执行中）| done = step（当前步已完成）| done > step（异常，不应出现）
- `files_changed`：实际修改的文件列表，没有则为空
- `[CHECKLIST]`：Write/Edit 操作后必须逐项列出并勾选；纯查询操作可省略
- `[TASK_MAP]`：每次 DONE 必填，Hermes 在检测到 DONE 后自动提取并写入 `~/.hermes/claude_task_map.json`

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

### PAUSE 标记模板

```markdown
<!-- PAUSE:task-X:step-N -->
[STATUS]
  reason: <暂停原因>
  suggested: <建议 Hermes 响应类型>
  files_changed: ["a.js"] 或 空
  [TASK_MAP]
  task_id: task-X
  step: M/N
  done: P
  session: 会话名称
  [/TASK_MAP]
[/STATUS]
<!-- /PAUSE -->
```

- PAUSE 后 Hermes 可响应：`<!-- RESUME:task-X:step-N -->`（恢复）| `<!-- SKIP:task-X:step-N -->`（跳过当前步）| `<!-- ABORT:task-X -->`（终止 task）
- CC 发 PAUSE 必须带 `reason` 和 `suggested`，否则 Hermes 无法决策

### 你应识别的输入标记

- `<!-- TASK:task-X:step-N -->` → 结构化协作指令
- `<!-- DISPUTE:R1 -->` → 要求提供证据或修正
- `<!-- DISPUTE:R2 -->` → 确认或反驳 Hermes 分析
- `<!-- DISPUTE:R3 -->` → 给出最终结论
- `[state: id=task-X step=M/N done=P ctx=摘要]` → 状态行，附在指令末尾
- `<!-- COMPLETE:task-X -->` → task 全部完成，CC 回复确认后 task 终止
- `<!-- RESUME:task-X:step-N -->` → PAUSE 后恢复执行，附指令
- `<!-- SKIP:task-X:step-N -->` → PAUSE 后跳过当前步
- `<!-- ABORT:task-X -->` → PAUSE 后终止整个 task

如果收到自然语言指令（无标记），正常执行，但可以建议使用结构化格式提高可靠性。

---

## 行为守则

### 强制规则（违反时必须拒绝或暂停）

| # | 触发条件 | 行为 |
|---|----------|------|
| 1 | 指令缺少 task_id 或 state 行 | 拒绝，回复"请补充 [state: id=xxx step=M/N done=P ctx=摘要] 后重发"。注意：此规则严格执行，不可放行 |
| 2 | 单次指令 > 3 步 | 拒绝，回复"指令过大，请拆分为 ≤3 步的分批指令"（步数 = Hermes 指令数，非 CC 内部操作数） |
| 3 | 输入出现截断信号（见下方信号列表） | 不拒绝执行，但在 ACK 中标注 `truncation_warning: true`，由 Hermes 侧判断是否重发 |
| 4 | 连续 3 步未经验证 | 暂停执行，回复"警告：连续 3 步未经验证，暂停执行直到验证完成" |
| 5 | 被要求跳过验证步骤 | 拒绝，回复"验证是协作协议的强制步骤，不可跳过" |

**截断检测信号（静默校验，不阻断执行）：**

1. 开标记 `<!-- TASK:... -->` 存在但无后续内容
2. `[state]` 行中 step 值与指令标记中的 step 不一致
3. `[state]` 行中 done > step
4. 指令在句子中间突然结束（无标点/无换行）

**降级**：拒绝 2 次后，降级为"警告但执行"，并标注 `verified: false`。

### 引导规则（发现问题时主动提醒）

| # | 触发条件 | 行为 |
|---|----------|------|
| 1 | DONE 后 60s 无新指令 | 超时监控由 Hermes 侧负责（Hermes 60s 未收到 DONE 应主动重发指令） |
| 2 | Hermes 转发了你的原始结论未加分析 | 提醒"建议对上述结论进行独立分析后再转达用户" |
| 3 | Session 恢复后的第一条消息缺少状态摘要 | 主动询问"请提供中断前的任务进度" |

### 校验规则

1. 每次 Edit/Write 后，**必须 Read 回修改点确认内容正确**
2. 修改多文件时，**必须逐个确认**，不能只确认最后一个
3. `verified` 字段必须如实反映——没有 Read 回验证就写 `false`

### 回滚策略

1. ERROR/PAUSE 时，CC **不主动回滚**已执行的修改
2. ERROR/PAUSE 中必须列出 `files_changed`，供 Hermes 决策（重试/跳过/人工介入）
3. CC 通过自主记录追踪变更文件（Edit/Write 操作时已知）；若执行了无法追踪的外部命令，标注 `"files_changed": "uncertain"`
4. 不主动运行 `git diff`（除非 Hermes 明确要求）

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
| 指令内容突然中断或格式异常 | 疑似 paste 截断，请求重发 |
| 收到 interview 提示但未收到选项指令 | 等待，不自行操作 |
| Hermes 发来超大指令（>3步） | 要求拆分 |
| Session 恢复后第一条消息无状态摘要 | 主动询问进度 |

---

## 测试模式

> 当指令中出现 `[HERMES:TEST-MODE]` 标记时启用以下规则。

- 允许故意违反行为守则以验证协议鲁棒性
- CC 在测试模式下仍输出正常标记（DONE/ERROR），但标注 `[MODE: TEST]`
- 以下场景可作为测试用例：并发冲突、指令截断、超长指令（>3步）、缺 state 行等
- 测试模式下 CC 不会因违反强制规则 #1/#2/#3 而拒绝，但仍记录违规行为并标注

---

## 权限预授权

> 协作模式下 CC 的安全边界。

- 仅预授权 `Bash(git *):allow`（git 操作可追溯，且有版本控制兜底）
- `python *`、`node *`、`cp *`、`mv *` 等不预授权，保留弹窗
- 权限规则由 CC settings.json 管理，本节仅约定原则

---

## 降级规则

> **所有协议都是"最佳努力"执行。**

- 任何一方未遵守协议时，另一方降级为正常操作模式，同时输出一次提醒
- 连续 3 次提醒后被忽略 → 停止提醒，等待人工介入
- 如果当前 session 未检测到任何 HERMES-ACTIVATE 标记，本文件的所有规则均不生效，正常执行人类指令
