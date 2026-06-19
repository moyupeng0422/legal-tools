---
name: hermes-workbuddy-feishu-collab
description: WorkBuddy 协作 Skill——飞书群云端 Hermes 与本地 WorkBuddy 通过 SSH 实现多轮自动化协作
---

# WorkBuddy 协作 Skill

让飞书群里的云端 Hermes 和本地 WorkBuddy通过 SSH 实现多轮自动化协作——发任务、写文件、辩论、审阅，全程用户无需传话。

## 前置条件

### Hermes 侧（云端 Ubuntu）
- 已部署 Hermes Agent（飞书 Bot）
- 已配置 SSH 免密登录到本地 Windows
- 飞书应用已获取 AppID / AppSecret
- 已知飞书群 chat_id 和 WorkBuddy 的 open_id

### WorkBuddy 侧（本地 Windows）
- 已安装 WorkBuddy（本地桌面版）
- 已配置 SSH Server（Hermes 可 ssh 登录）
- 协作工作目录可读写

## 通信架构

```
飞书群聊（通信）                         SSH（读文件 + 监控）
用户 ──→ @WorkBuddy ──→ WorkBuddy GUI  Hermes
              ↑                    │         │
              │             写 conv +        │ SSH cat status.json
              │             更新 status      │ SSH cat conv
              │             发卡片（用户见）  │
              └────────────────────┘         │
              WorkBuddy 写完 → 状态已更新    │
                                             ▼
                                     检测到 completed → 读 conv → 处理
```

## 文件协议

`{PROJECT_DIR}/hermes_collab/` 下：

| 文件 | 格式 | 说明 |
|------|------|------|
| 沟通记录 | `conv_<简写>_YYYYMMDD.md` | 讨论、辩论过程 |
| 交付物 | `out_<简写>_YYYYMMDD_v{N}.md` | 纯成品，不含辩论 |
| 状态灯 | `status.json` | 当前任务状态 |
| 协议 | `PROTOCOL.md` | 协作协议说明书 |

### status.json 格式

```json
{
  "protocol_version": "3.0",
  "current_task": {
    "id": "任务名_YYYYMMDD",
    "status": "writing",       // writing | waiting | completed | failed
    "phase": "当前阶段描述",
    "conv_file": "conv_xxx_YYYYMMDD.md",
    "since": "YYYY-MM-DD HH:MM:SS",
    "interruptible": true
  }
}
```

### 交付物分离（out_ 文件）

有成品产出的任务（文章终稿、报告、代码），WorkBuddy 写独立的 `out_` 文件，conv 中只放讨论过程。

| 场景 | 使用文件 |
|------|---------|
| 产出是可交付成品 | `out_<简写>_YYYYMMDD_v{N}.md` |
| 沟通本身就是产出 | conv 足够 |
| 任务执行失败 | 无交付物 |

## 操作序列

### 模式 A：后台监控（推荐）

```
用户说"去跟WorkBuddy讨论XXX"
  → 第1步：加载本 skill
  → 第2步：查 @ 格式（WorkBuddy open_id）
  → 第3步：用 REST API 发消息 @WorkBuddy
  → 第4步：启动后台轮询（notify_on_complete=true）
  → 第5步：回复用户"已发给 WorkBuddy，等回复"
```

### 模式 B：同 turn 轮询

适用于简单确认、单轮查询。

```
用户说"去跟WorkBuddy讨论XXX"
  → 不发用户 → 发消息给 WorkBuddy
  → terminal foreground 锁定等回复
  → 全部闭环 → 汇报用户
```

### @WorkBuddy 的正确格式

跨 Bot @ 必须用「发消息者视角」的 open_id。用 REST API 发送：

```python
text = '<at user_id=\"{WORKBUDDY_HERMES_OPEN_ID}\">WorkBuddy</at> 消息内容'
body = {
    'receive_id': '{FEISHU_CHAT_ID}',
    'msg_type': 'text',
    'content': json.dumps({'text': text}, ensure_ascii=False)
}
requests.post('https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id', ...)
```

> ⚠️ 不用 send_message 工具的 @ 标签，必须用 REST API。

### 回复处理

收到 WorkBuddy 回复后：

1. 确认是否有新的 conv 文件（SSH 直读）
2. 只有卡片无新 file → 催 WorkBuddy 写入 conv
3. 有新 file → 区分用途：
   - conv 文件 → SSH 读取最新内容
   - 非 conv 文件（文档更新等）→ **飞书 API 下载附件**
4. 辩论检查：独立分析 WorkBuddy 方案 → 找到漏洞发 `[辩论]` → 等回应
5. 全部闭环后向用户汇报

## 消息前缀

| 前缀 | 用途 |
|------|------|
| `[任务]` | 派任务给 WorkBuddy 执行 |
| `[讨论]` | 非执行型讨论 |
| `[辩论]` | 对结果有异议，走 R1→R2→R3 辩论 |
| `[协议调整]` | 更新协作规则 |

## 工具脚本

本 skill 附带 3 个脚本（`scripts/` 目录）：

| 脚本 | 用途 |
|------|------|
| `workbuddy_monitor.py` | SSH 长任务监控轮询（检测 status.json 变化） |
| `workbuddy_read_conv.py` | conv 文件增量读取（仅返回新增行） |
| `workbuddy_poll.py` | 飞书 API 轮询（备用通道：初始确认 + SSH 不通时） |

## 注意事项

- WorkBuddy 连续发送 file 和 card 时，两者可能间隔 <1 秒，轮询需注意可能漏文件
- 中文文件名必须用 Base64 UTF-16LE 编码传给 PowerShell
- SSH 仅限读取协作工作目录 `{PROJECT_DIR}/hermes_collab/` 下的文件
- WorkBuddy 上传的其他附件（如 MEMORY.md 更新）用飞书 API 下载，不走 SSH
- 所有答复同步写入 conv，卡片与 conv 内容一致
