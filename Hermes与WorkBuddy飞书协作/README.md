# Hermes与WorkBuddy飞书协作

> **版本 v2.1.0**（协议 v1.8「零机械架构」）| 云端 Hermes Agent 通过飞书群聊编排 WorkBuddy（芭迪）执行任务的多 Agent 协作规范

## 这是什么

Hermes（云端）→ 飞书群卡片 → WorkBuddy（本地 Windows）的**单向下发 + conv 文件回传**协作协议。核心形态：

- **卡片下发任务**（agent-send.sh，串行闸门保证同任务不重发）
- **conv 文件承载内容**（芭迪把工作过程与结论写入 conv 文件，SSH 推回云端；卡片只做"醒了"的信号）
- **睡眠等待主链路**（badi-wait.py，30s 群轮询 + 卡片唤醒）

## 版本演进（为什么是彻底重写）

本目录此前发布的是 v3.0（watch/audit/A2A 三件套 + WorkBuddy 侧斜杠命令架构）。此后本地实际演进经历了 v3.x 多轮迭代、v1.5-v1.7 中间协议，最终在 v1.8 完成架构级重构（零机械架构）并更名为 multiagent-feishu-scripting，本次发布以 v2.1.0（协议 v1.8）整体替换旧版。

**v3.0 → v1.8 的核心架构变化**：

| v3.0 旧机制 | 问题（实证） | v1.8 替代 |
|--------|------|----------|
| watch 文件监听（board_watch/badi_watch 等 7 个脚本） | 投递层故障（飞书 bot 间消息不投递），watch 无岗可守 | **sleep 等待主链路**：`badi-wait.py` 同 turn 阻塞轮询群消息 + 卡片唤醒 |
| A2A POST 直连 | audit 源死，砍除 | 群消息 API 复核 |
| 卡片即内容 | 卡片被 8000 字符拆分、正文 API 不可读 | **conv 内容权威**：conv 文件是唯一事实源，卡片只是唤醒信号 |
| 看板自动派生状态 | rebuild 重派生已收口任务 | **看板状态权威**：collab_board.py 显式 update + rebuild |
| @ 对方 Bot 兜底 | bot 间消息不投递的平台实证 | **禁 @ 铁律**：跨 Bot 通道设计先判死互@、走文件落盘 |
| WorkBuddy 侧斜杠命令（/status /stop /priority） | 随 v3 架构退役 | 芭迪侧 skill 承载（见 workbuddy-side/） |

### 核心铁律

1. **单卡片铁律**：一个任务一张卡片，内容全在 conv，卡片不承载实质信息
2. **禁 @ 铁律**：飞书平台 bot 间 @ 消息不投递（实证），跨 Bot 通道设计先判死互@、走文件
3. **醒后原子序列**：睡醒后 `读 conv → 校验 → 验收判断（LLM 闸门，不可跳过）→ 看板核销`，跳过验收直接闭环 = 最大漏洞
4. **pending-op 权限卡分型**：纯卡片无文本 = 框架权限审批挂起（非 LLM 产出），配合芭迪侧 `<!-- pending-op -->` 哨兵行辨析，不误判为纪律违规

## 文件结构

```
Hermes与WorkBuddy飞书协作/
├── SKILL.md                  # 主规范（v2.1.0，131 行，v1.8 零机械架构）
├── references/               # 15 篇
│   ├── protocol-v1.8.md      # 完整协议（改协议必读）
│   ├── badi-instructions-v18.md      # 芭迪指令唯一权威版
│   ├── assets-inventory.md           # 脚本资产对照清单
│   ├── credentials.md                # 凭据占位符版（所有 ID 均为占位符，使用时替换）
│   ├── agent-md-redesign-20261124.md # 芭迪常驻注入四层架构定稿
│   ├── a2a-redesign-2026-11-23.md    # 八轮辩论全记录
│   └── ...
├── scripts/                  # 5 个协议承载脚本
│   ├── badi-wait.py          # sleep 等待主链路（30s 群轮询 + STALL 梯子）
│   ├── agent-send.sh         # 卡片下发（串行闸门 SEND_UNCLOSED）
│   ├── hermes-post-task.sh   # 任务验收闭环（verify 材料 + close）
│   ├── collab_board.py       # 看板（事件流 + 派生视图 rebuild）
│   └── agent-conv.sh         # conv 文件收发
└── workbuddy-side/           # WorkBuddy 端（芭迪侧 skill + badi_finish.ps1 + 协议副本）
```

## 双端发布

与「Hermes与Claude Code协作」（Hermes 端 SKILL + CC 端 hermes-collab.md）同构，本目录发布协作双方的材料：

- **Hermes 端**（本目录主体）：SKILL.md + references/ + scripts/
- **WorkBuddy 端**（`workbuddy-side/`）：芭迪侧 skill（SKILL.md）、`badi_finish.ps1`（conv 推送脚本，v2.0）、协议/指令正本副本（references/）

芭迪侧部署方式：`SKILL.md` + `references/` 复制到 WorkBuddy 的 skills 目录（如 `~\.workbuddy\skills\feishu-collab-protocol\`），`badi_finish.ps1` 放入协作工作目录。所有 ID、路径、密钥位置均为占位符，部署时替换为你自己环境的值。

## 快速开始

```bash
# 1. 派发任务（串行闸门：同任务未闭环会被 SEND_UNCLOSED 拦截）
bash scripts/agent-send.sh <task-id> --step 1 "任务描述"

# 2. 睡眠等待（同 turn 阻塞，30s 轮询群消息，卡片唤醒退出）
python3 scripts/badi-wait.py <task-id> --total 420

# 3. 醒后：读 conv → 校验 → 验收 → 看板核销
python3 scripts/collab_board.py update <task-id> closed --conclusion result_pass
python3 scripts/collab_board.py rebuild   # update 后必须 rebuild 才对 wait 生效
```

> 脚本内的群 chat_id、App ID 等均为占位符（见 `references/credentials.md`），使用前替换为你自己环境的真实值。发布版脚本为参数化模板，未经外部环境实测。芭迪（WorkBuddy）侧的部署材料见 `workbuddy-side/`。

## 使用条件

- 云端：Hermes Agent 环境 + 飞书自建 App（群消息收发权限）
- 本地：WorkBuddy（或自行实现的芭迪侧 counterpart）+ Tailscale + SSH
- 相关仓库：[legal-tools](https://github.com/moyupeng0422/legal-tools)

## 许可证

MIT — 见仓库根 [LICENSE](../LICENSE)
