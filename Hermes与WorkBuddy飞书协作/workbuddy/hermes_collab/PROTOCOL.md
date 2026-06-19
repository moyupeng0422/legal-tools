# Hermes 协作协议 v3.0

## 核心原则 (v3.0 纠正)

**所有答复同步写入 conv，卡片与 conv 内容一致。**

- Hermes 通过 SSH 直接读取本地文件（`ssh {SSH_ALIAS} "powershell Get-Content ..."`）
- conv 文件是 Hermes 通过 SSH 读取的内容通道
- 卡片保持详细内容——用户需要实时看到讨论过程
- 卡片末尾附 `[详见: conv_xxx.md]` 引用

## 通信架构

```
飞书群聊（通信）              SSH（读文件）
你 ──→ @Workbuddy ──→ WorkBuddy GUI
           ↑                    │
           │                    │ 写 conv + status.json
           │                    │ 发卡片（用户可见）
           └────────────────────┘
           Hermes SSH cat 直接读取
           Hermes SSH cat status.json 获取状态
```

## 目录
`{PROJECT_DIR}/hermes_collab\`
`{PROJECT_DIR}/hermes_collab\done\` — 已完成任务归档

## 文件命名

| 文件类型 | 命名格式 | 用途 | 写入者 |
|----------|----------|------|--------|
| 沟通记录 | `conv_<简写>_YYYYMMDD.md` | 完整工作记录+辩论 | Workbuddy |
| 输出交付 | `out_<简写>_YYYYMMDD_v{N}.md` | 纯成品（文章/报告/代码） | Workbuddy |
| 输入文件 | `task_IN_YYYYMMDD_HHMMSS.md` | Hermes 文件传递（仅文件内容任务时用） | Hermes |
| 输出交付(旧) | `task_OUT_YYYYMMDD_HHMMSS.md` | 实质交付物（v1.0 遗留） | Workbuddy |
| 状态追踪 | `status.json` | 任务状态追踪 | Workbuddy |

简写规则：小写英文 + 连字符（例：`protocol-v2.1`、`debate-test`）

## out_ 交付物规则 (v3.0 补充)

**out_ 文件存放纯成品，不含辩论/思考过程。与 conv_ 分离管理。**

### 命名与版本

```
out_<简写>_YYYYMMDD_v{N}.md

版本规则（手动管理）：
  新建  → v1
  大改（重写/结构调整）→ v2, v3, ...
  微调（错别字/格式修正）→ 原地覆盖，不升版本

示例：
  out_公众号文章_20260619_v1.md
```

### 关联与引用

```
conv 末尾标注交付引用：
  [state: task=xxx status=done output=out_xxx_v1 files=[...] upgrade=false]

有 in_ 文件时加 input= 字段：
  [state: task=xxx status=done input=task_IN_xxx output=out_xxx_v1 ...]

Hermes 侧 in_ 文件可加 expects_output:true 字段标记期待产出。
```

### presented 联动

```
创建 out_ 时 → status.json out_files: { "presented": false }
Hermes 验收通过 → Workbuddy present_files 上传群 → 改 { "presented": true }
```

- 有 out_ 时，写完应 present_files 给用户（交付通道）
- 无 out_ 时，present_files 可选

### 何时分离

| 情况 | 写 out_ |
|------|:---:|
| 产出是可交付成品（文章、报告、代码） | ✅ |
| 沟通本身就是产出（协议讨论、复盘） | ❌ conv 足够 |
| 任务执行失败 | ❌ 无交付物 |

## conv 文件策略：追加 vs 新建

**同一主题同一天连续回合 → 追加；新主题 → 新建。**

| 情况 | 操作 | 说明 |
|------|------|------|
| 首个回合 | 新建 | 创建 `conv_<简写>_YYYYMMDD.md` |
| 同主题后续回合 | 追加 | 追加 `R{N}: ...` 到已有 conv |
| 新主题 | 新建 | 新的 `<简写>`，新文件 |
| 跨日续接 | 新建 | 日期不同，新文件 |

追加后覆盖更新末尾 `[state: ...]` 行。

## 通信流程 (v3.0 精简)

```
Hermes @Workbuddy [前缀] 描述
        │
        ▼
Workbuddy收到消息（WorkBuddy GUI 直接显示）
        │
        ├── 1. 分析任务
        ├── 2. 调用工具执行
        ├── 3. 关键操作自校验（Read 回读）
        ├── 4. 新建/追加 conv
        │      ├── 任务描述
        │      ├── 思考过程
        │      ├── 工具调用记录（含验证列）
        │      ├── 结论（含 [升级]）
        │      └── [state: ...] 状态摘要行
        ├── 5. 更新 status.json → completed
        └── 6. 发卡片（内容与 conv 一致）
                │
                ▼
        Hermes SSH cat conv 拉取详细内容
```

### 辩论流程

```
Hermes @Workbuddy [辩论] conv_<简写>_YYYYMMDD.md
        │
        ▼
Workbuddy收到 [辩论] 前缀
        │
        ├── 1. 读指定 conv 文件（含 Hermes 追加的 R2）
        ├── 2. 追加 R3 到同一文件
        ├── 3. 更新 status.json
        ├── 4. 发卡片
        └── 5. 辩论 resolved → 文件移至 done/
```

## conv 文件格式

### 固定章节
1. `## 任务描述`
2. `## 思考过程`
3. `## 工具调用记录`（含验证列）
4. `## 结论`（含 `[升级]`）
5. `## 质疑与回应`（[辩论] 触发时）
6. 末尾 `[state: ...]`

### 辩论/质疑机制

```
## 质疑与回应
### R1 (WorkBuddy结论): [时间戳] 结论内容
### R2 (Hermes质疑): [时间戳] 质疑内容  ← Hermes SSH 追加
### R3 (WorkBuddy回应): [时间戳] 修正/确认    ← WorkBuddy 追加
```

- Hermes 通过 SSH 追加 R2
- WorkBuddy收到 `[辩论]` 后追加 R3
- 同一任务不建新文件
- **所有辩论必须写入 conv，不允许仅发卡片**

### 真实性校验

| 步骤 | 工具 | 操作 | 验证 |
|------|------|------|------|
| 1 | Write | 写入文件 | ✅ 已验证 |

### 升级通道

```
[升级] 需 Hermes 协助：具体操作
原因：WorkBuddy无 XX 权限
已尝试：本地排查内容
```

### 状态摘要

```
常态：[state: task=<简写> status=done files=[...] upgrade=false]
写作中：[state: task=<简写> status=writing phase=2/5 desc=<描述>]
审阅中：[state: task=<简写> status=waiting phase=2/5 desc=<等Hermes审阅>]
```

## 消息前缀 (v3.0 精简)

| 前缀 | 写 conv | 说明 |
|------|---------|------|
| `[任务]` | 是 | 新建 conv |
| `[讨论]` | 是 | 追加 conv |
| `[辩论]` | **强制** | 追加 R3 |
| `[协议调整]` | 是 | 追加 conv |

## Hermes 自定义斜杠命令

| 命令 | 用途 |
|------|------|
| `/hermes:status` | 一键状态报告 → conv |
| `/hermes:stop` | 打断当前任务 → status=failed |
| `/hermes:priority` | 保存进度 + 插队新任务 |

命令文件：`.codebuddy/commands/hermes/*.md`

## 归档规则
- 辩论 resolved + status=done → `hermes_collab/done/`
- 无辩论任务 status=done + Hermes 确认 → `hermes_collab/done/`

## 错误处理
- 失败仍写 conv，status=failed
- 需协助用 `[升级]` 标记
- **实质性讨论必须写入 conv，不能仅发卡片**

## Atomic Write 保证 (v3.0 强化)

```
① Write conv_xxx.tmp（完整内容）
② mv conv_xxx.tmp → conv_xxx.md（原子重命名） ← v3.0 推荐
③ Write status.json（status=writing → completed/waiting）
④ Read 回读 status.json 确认

保证：Hermes 看到 completed/waiting 时，conv 一定完整。
      逻辑门禁（status.json）已足够，.tmp→rename 为推荐优化。
```

## 任务状态机 (v3.0)

```
writing ──成功──→ completed
       ──失败──→ failed
       ──审阅──→ waiting → → → writing（Hermes 继续）
       ──打断──→ failed   （可恢复为 writing）
```

| 状态 | 含义 | Hermes 行为 |
|------|------|-----------|
| `writing` | WorkBuddy正在执行 | 可读监控，不行动 |
| `waiting` | WorkBuddy暂停，等 Hermes 输入 | 应响应（审阅/纠正） |
| `completed` | 完成 | 可读，汇报用户，触发下游 |
| `failed` | 失败 | 可读，记录失败原因 |

## status.json 格式 (v3.0)

```json
{
  "protocol_version": "3.0",
  "current_task": {
    "id": "公众号文章_20260619",
    "status": "writing",
    "phase": "正文撰写",
    "phase_n": 3,
    "phase_of": 6,
    "conv_file": "conv_公众号文章_20260619.md",
    "since": "2026-06-19 18:47:00",
    "interruptible": true
  },
  "conv_files": {},
  "out_files": {
    "out_公众号文章_20260619_v1": {
      "task": "公众号文章",
      "created": "2026-06-19T19:15:00+08:00",
      "presented": false,
      "version": 1,
      "desc": "微信公众号文章 v3.0 终版"
    }
  },
  "debate_files": {},
  "archived": {}
}
```

## waiting 状态触发 (v3.0 新增)

WorkBuddy写完阶段性内容需要 Hermes 审阅时：

```
① 更新 status.json: status → "waiting"
② 发卡片：「[审阅] conv_xxx.md 第 N 阶段完成」
③ Hermes SSH 检测到 waiting → cat conv → 审阅
④ 审完发「[继续]」→ WorkBuddy改回 writing
⑤ 有异议 → 走 [辩论] 流程
```

## 长任务监控：SSH 轮询 (v3.0)

Hermes 侧主动轮询，WorkBuddy侧只写文件：

```
Hermes @WorkBuddy [任务]
  → WorkBuddy start: status=writing, phase=1/N
  → Hermes 轮询: 每 30-60s ssh cat status.json
  → WorkBuddy 更新 status.json（phase_n 递增）
  → Hermes 检测 phase_n 变化 → 决策
  → WorkBuddy 需审阅: status=waiting
  → Hermes 检测 waiting → cat conv → 审阅
  → 完成: status=completed → Hermes cat conv → 处理
```

## 版本历史
- v3.0 (2026-06-19): **架构重大纠正** — SSH 直读替代飞书附件通道；砍 present_files 通信角色；status 简化 writing/waiting/completed/failed；长任务 SSH 轮询监控；Atomic Write .tmp→rename 推荐；waiting 触发机制
- v2.5 (2026-06-19): conv 追加 vs 新建策略
- v2.4 (2026-06-19): 修正卡片策略、新增斜杠命令
- v2.3 (2026-06-19): [讨论] 改必须写conv
- v2.2 (2026-06-19): 辩论强制写conv、命名规范、归档
- v2.1 (2026-06-19): 辩论机制、真实性校验、升级通道
- v2.0 (2026-06-19): conv 沟通记录文件
- v1.0 (2026-06-19): 初始协议
