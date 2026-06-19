# WorkBuddy Memory — Hermes 协作规则

> **Name for Assistant**: WorkBuddy  
> **详细协议见**: `{PROJECT_DIR}/hermes_collab/PROTOCOL.md`

---

## 核心原则

**所有答复同步写入 conv，卡片与 conv 内容一致。**

- conv 文件是 Hermes 通过 SSH 读取的内容通道
- 卡片保持详细内容——用户需要实时看到讨论过程
- 卡片末尾附 `[详见: conv_xxx.md]` 引用

## 通信架构

```
飞书群聊（通信）              SSH（读文件）
你 ──→ @WorkBuddy ──→ WorkBuddy GUI
           ↑                    │
           │                    │ 写 conv + status.json（本地文件）
           │                    │ 发卡片（用户可见）
           └────────────────────┘
           Hermes SSH cat 直接读取文件内容
           Hermes SSH cat status.json 获取状态
```

**飞书仅用于通信（发消息），SSH 仅用于读文件（读内容）。两端职责清晰分离。**

---

## 目录

```
{PROJECT_DIR}/hermes_collab/
{PROJECT_DIR}/hermes_collab/done/ — 已完成任务归档
```

## 文件命名

| 文件 | 格式 | 说明 |
|------|------|------|
| 沟通记录 | `conv_<任务简写>_YYYYMMDD.md` | 简写用小写英文+连字符 |
| 交付物 | `out_<简写>_YYYYMMDD_v{N}.md` | 纯成品，不含辩论记录 |
| 输入文件 | `task_IN_YYYYMMDD_HHMMSS.md` | Hermes 文件传递 |

例：`conv_protocol-v2.1_20260619.md`

## conv 文件追加策略

- 同一主题、同一天、连续回合 → **追加到同一 conv**，不新建
- 新主题 → 新建 conv
- 跨日续接 → 新建 conv
- **追加约束：仅追加新内容到文件末尾，禁止覆盖已发布内容**

完结后移入 `done/` 归档。

---

## 消息前缀

| 前缀 | 含义 | 写 conv |
|------|------|:------:|
| `[任务]` | 需要执行并记录的任务 | ✅ |
| `[讨论]` | 非执行型讨论 | ✅ |
| `[辩论]` | 质疑与回应，走 R1→R2→R3 | ✅ 强制 |
| `[协议调整]` | 更新协作规则 | ✅ |

前缀是什么活，就按什么流程走。不用推理。

---

## 执行流程

**核心规则：先写文件 → 再更新状态 → 最后发卡片。**

```
收到任何 [任务]/[讨论]/[协议调整]/[辩论] →
  ① 立即创建/打开 conv 文件，写入框架  ← 此步不可跳过
  ② 分析任务 → 调用工具执行 → 自校验
  ③ 填充/追加 conv 内容
  ④ Read 回读确认 [state: ...] 尾行存在
  ⑤ 更新 status.json → completed
  ⑥ 发卡片（正文引用 conv 结论，末尾附文件路径引用）

Hermes 通过 {SSH_ALIAS} SSH cat 直接读取 conv 和 status.json，
不需要WorkBuddy推送。
```

### 辩论流程

```
收到 [辩论] conv_<简写>_YYYYMMDD.md:
  ├── 1. 读指定 conv 文件（含 Hermes 追加的 R2）
  ├── 2. 追加 R3 到同一文件
  ├── 3. 更新 status.json
  ├── 4. 发卡片
  └── 5. 辩论 resolved → 文件移至 done/
```

---

## 状态灯（status.json）

```
writing   → 正在写，别碰
waiting   → 阶段性完成，等 Hermes 审阅
completed → 写完了，可以读了
failed    → 执行失败，看 conv 里的 [升级] 标记
```

### waiting 触发

WorkBuddy完成阶段性工作需 Hermes 审阅时：`status → waiting` → 发卡片「请审阅」→ Hermes SSH 发现 → cat conv → 审阅 → 发 [继续]

---

## 禁止清单

```
禁一：先回卡片再补 conv
禁二：只回卡片不写 conv
禁三：写完 conv 不更新 status
禁四：追加 conv 后状态不跟进
```

---

## 斜杠命令

| 命令 | 功能 |
|------|------|
| `/hermes:status` | 一键生成状态报告写入 conv |
| `/hermes:stop` | 记录中断点，status→failed |
| `/hermes:priority` | 保存旧任务，插队执行新任务 |

命令文件位置：`.codebuddy/commands/hermes/*.md`

---

> **完整协议规范见**: `{PROJECT_DIR}/hermes_collab/PROTOCOL.md`  
> **Hermes 侧配置见**: `hermes/SKILL.md`
