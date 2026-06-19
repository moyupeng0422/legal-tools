# Workbuddy协作架构 v3.0（2026-06-19）

## 前提纠正

**v2.x 的错误前提**：Hermes 不能通过 SSH 读文件，必须通过飞书 API 下载附件。\
→ 在此前提下设计了 present_files 协议（WorkBuddy写文件 → 上传附件 → Hermes API 下载）。

**实际验证结果**：SSH 全程通着。Hermes 直接用 `ssh local-win "powershell Get-Content ..."` 就能读文件。\
→ present_files 协议设了等于白设。

## v3.0 正确架构

```
飞书群聊（通信）                     SSH（读文件 + 监控）
                               ───────────────────────
用户 ──→ @WorkBuddy ──→ WorkBuddy   Hermes
              ↑                    │
              │              ① SSH cat status.json（每30-60s）
              │              ② 检测 status 变化
              │              ③ SSH cat conv（按需）
              │                    │
              └──── WorkBuddy执行 ──────┘
                   写 conv + 更新 status.json + 发卡片通知用户
```

### 职责分离

| 通道 | 用途 | 协议 |
|------|------|------|
| 飞书群聊 | 通信（发消息、@WorkBuddy、通知） | REST API + `<at>` 格式 |
| SSH | 读文件（conv、status.json） | `ssh local-win "cat ..."` |
| 飞书 API（备用） | 读文件（SSH 不通时） | ListMessage API 下载附件 |

### 状态流转

```
writing ──阶段性完成──→ waiting ──Hermes 审阅──→ writing ──...──→ completed
                          │                           ↑
                          └── 发 [继续] ───────────────┘

writing ──超过30分钟无进展──→ [纠正] 询问
```

### Workbuddy操作流程（v3.0 精简版）

旧 8 步：写 conv → present_files(上传) → 发卡片 → 等 API 下载 → (追加后重新上传...)\
新 5 步：写 conv → Write status.json → Read 回读确认 → 发卡片（用户可见）

### status.json v3.0

```json
{
  "protocol_version": "3.0",
  "current_task": {
    "id": "任务名_YYYYMMDD",
    "status": "writing",
    "phase": "当前阶段描述",
    "phase_n": 2,
    "phase_of": 5,
    "conv_file": "conv_xxx_YYYYMMDD.md",
    "since": "2026-06-19 18:47:00",
    "interruptible": true
  }
}
```

### Hermes 监控脚本

```bash
# 长任务 SSH 轮询（推荐）
python3 ~/.hermes/scripts/badi_monitor.py "任务名" 20

# 短任务/初始确认（备用）
python3 ~/.hermes/scripts/badi_poll.py <timestamp>
```

## 协议版本演进

| 版本 | 时间 | 核心架构 | 关键变更 |
|:----:|:----:|---------|---------|
| v1.0 | 14:35 | HTTP API 初测 | 消息送达验证 |
| v2.0 | 14:44 | conv 文件 + 飞书附件 | 引入沟通记录文件 |
| v2.5 | 16:52 | conv 追加 + progress | 同主题追加、分阶段更新 |
| **v3.0** | **18:57** | **SSH 直读 + 状态轮询** | **砍 present_files 通信角色、Hermes 主动监控** |

## 被砍掉的 v2.x 规则

以下规则在 v3.0 中已废弃（SSH 直读替代）：

- ~~present_files（上传附件给 Hermes 读）~~
- ~~铁律二：写完必须重新上传附件~~
- ~~追加内容后重新上传附件~~
- ~~Hermes 读取矩阵（processing/progress/review/completed）~~
- ~~飞书 API 下载 conv 文件作为主要通道~~
