# ACP 替代 tmux 方案研究

> 2026-06-02 讨论：用户提出当前 tmux 模拟终端交互方式效率低下（send-keys 截断、capture-pane 轮询、弹窗盲按），探讨 Agent-to-Agent 原生协议替代方案。

## 现状痛点

| 痛点 | 根因 |
|------|------|
| send-keys 分段截断 | 模拟人类打字，受终端缓冲区限制 |
| capture-pane 轮询延迟 | 无事件驱动，需 5-8s 轮询 + 肉眼判断 |
| 权限弹窗不可见 | TUI 弹窗无法结构化传递，只能盲按 |
| plan mode paste-buffer 不可靠 | CC 输入框只捕获最后一段文本 |
| SSH 断连后状态丢失 | tmux session 内 SSH 断开，scrollback 残留旧输出误导 |

## 探索路径

### 1. Headless Mode (`claude -p`)

CC 支持非交互执行：`claude -p "prompt" --output-format json`

**优点**：完全绕过 TUI，stdin/stdout 直接通信，支持 `--output-format stream-json` 实时流。

**致命缺陷**：
- `-p` 每次执行后退出，无持久会话
- 多轮对话需 `--resume <session_id>` 但每次重新加载上下文
- 权限需预设（`--allowedTools` 或 `--dangerously-skip-permissions`）
- 不支持交互式审批流程

**结论**：适合一次性任务，不适合需要多轮辩论和交互的协作场景。

### 2. Claude Code 原生 ACP（等待官方）

GitHub Issue [#6686](https://github.com/anthropics/claude-code/issues/6686) 请求 CC 支持 `--acp --stdio` 模式。截至 2026-06-02 **未实现**，无明确时间表。

### 3. 自建 ACP 适配器（最有希望）

#### 3.1 已有轮子：`@zed-industries/claude-agent-acp`

Zed 编辑器使用的 ACP 适配器，**可独立运行**（不依赖 Zed）：

```bash
npm install -g @zed-industries/claude-agent-acp
ANTHROPIC_API_KEY=sk-xxx ANTHROPIC_BASE_URL=https://your-proxy/v1 claude-agent-acp
```

架构：
```
ACP client ←→ claude-agent-acp (stdio JSON)
                  └── Claude Agent SDK (@anthropic-ai/claude-agent-sdk)
                        └── Claude Code 引擎
```

#### 3.2 关键依赖条件

Claude Agent SDK 通过 `ANTHROPIC_BASE_URL` 支持自定义 API endpoint，但必须是 **Anthropic 协议兼容**的接口（非 OpenAI 格式）。

用户当前使用 glm-5-turbo（智谱），需确认：
- 是否已通过 `ANTHROPIC_BASE_URL` 指向 Anthropic 兼容代理？
- 如是 OpenAI 兼容格式，需 LiteLLM 等中间层转换为 Anthropic 格式

#### 3.3 部署架构（条件满足后）

```
Hermes(云端) ──SSH pipe──→ claude-agent-acp (Windows)
                ↑ ACP JSON 双向通信
                │  • session/new → 创建会话
                │  • session/update → 流式输出
                │  • session/request_permission → 权限审批（结构化！）
                │  • session/load → 恢复会话
```

#### 3.4 Hermes 侧集成

Hermes 的 `delegate_task` 已支持 `acp_command`（如 `copilot --acp --stdio`），但目前仅限本地 spawn。远程 ACP 需：
- 通过 SSH 管道启动：`ssh <ssh-alias> "claude-agent-acp"`
- 或等待 Hermes 实现 GitHub Issue [#689](https://github.com/NousResearch/hermes-agent/issues/689)（Remote Agent Connection）

### 4. tmux 优化（渐进改进，不换底层）

如果 ACP 路线前置条件不满足，可针对性优化现有 tmux 方案：

| 痛点 | 改进 |
|------|------|
| send-keys 截断 | 长内容 scp 到 Windows 文件 → CC `读取 文件路径` |
| 弹窗盲按 | 一次性配置 `/permissions` 预设项目目录允许规则 |
| 监控延迟 | 利用 `<!-- DONE -->` + `<!-- ACK -->` 标记替代纯肉眼判断 |

## ✅ 前置条件验证（2026-06-02 已确认）

通过 CC 自检 `~/.claude/settings.json` 和系统环境变量，确认了智谱 API 的兼容性：

| 字段 | 值 | 说明 |
|------|-----|------|
| `ANTHROPIC_BASE_URL` | `<api-endpoint-anthropic>` | 智谱提供 **Anthropic 协议兼容** 端点 |
| `ANTHROPIC_AUTH_TOKEN` | 智谱 API Key | 认证凭据 |
| `ANTHROPIC_MODEL` | `glm-5-turbo` | 默认模型 |
| 配置位置 | `~/.claude/settings.json` → `env` 字段 | CC 启动时注入，非系统环境变量 |

**结论**：智谱 AI 提供了 `/api/anthropic` 端点，接受 Anthropic 协议格式的 API 调用。Claude Agent SDK 通过 `ANTHROPIC_BASE_URL` 可以直接走智谱，**自建 ACP 适配器的技术前提已全部满足**。

## 🏆 ACP 适配器安装与验证（2026-06-02 已完成）

### 官方 ACP 适配器

使用 `@agentclientprotocol/claude-agent-acp`（ACP 官方组织维护）替代 Zed 版本：

```bash
npm install -g @agentclientprotocol/claude-agent-acp
# 安装版本：v0.39.0（103 packages，23s）
```

### 启动方式

```bash
set ANTHROPIC_BASE_URL=<api-endpoint-anthropic>
set ANTHROPIC_AUTH_TOKEN=<智谱API Key>
claude-agent-acp
```

### 协议特征

| 特征 | 说明 |
|------|------|
| 通信模式 | **stdin/stdout JSON-RPC**（默认即为 ACP 模式） |
| 终端输出 | **无**——静默等待 stdin 握手，所有日志在 stderr |
| `console.log` | 被重定向到 `console.error`（stdout 纯粹是 ACP JSON） |
| `protocolVersion` | **数字 `1`**（非日期字符串如 `2025-06-01`） |
| 握手命令 | `claude-agent-acp`（不带任何参数，直接 stdin 管道） |

### ACP Initialize 握手

```json
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "id": 1,
  "params": {
    "protocolVersion": 1,
    "capabilities": {"auth": {"_meta": {"gateway": true}}},
    "clientInfo": {"name": "hermes", "version": "1.0.0"}
  }
}
```

### 已验证的响应能力

握手成功返回 agent 信息，确认支持：
- `promptQueueing` — 任务队列
- `image` — 图片输入
- `mcp`（http+sse）— MCP 服务器连接
- `loadSession` — 会话恢复
- `sessionCapabilities` — 会话能力声明

### 协议格式确认（2026-06-02 CC 源码分析）

CC 阅读了 claude-agent-acp 源码（`runAcp` 函数），确认协议细节：

| 特征 | 确认结果 |
|------|---------|
| **消息边界** | 一行一个 JSON + `\n`（换行符），非 WebSocket、非长度前缀 |
| **写入方式** | `JSON.stringify(msg) + '\n'` → stdin |
| **读取方式** | `stdout.readline()` 逐行解析 |
| **进程生命周期** | stdin EOF → `connection.closed` → `shutdown()` → `process.exit(0)` |
| **信号处理** | SIGTERM/SIGINT → 干净退出，不留孤儿进程 |
| **SSH pipe 断连** | stdin EOF 自动触发退出，无需手动清理 |

### Hermes 侧 Python 验证脚本

采用 `subprocess.Popen` 方案（轻量，无需 paramiko）：

```python
import subprocess, json

proc = subprocess.Popen(
    ["ssh", "<ssh-alias>", "claude-agent-acp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

init_msg = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": 1,
        "clientInfo": {"name": "hermes", "version": "1.0.0"},
        "capabilities": {"auth": {"_meta": {"gateway": True}}}
    }
}

proc.stdin.write(json.dumps(init_msg) + '\n')
proc.stdin.flush()
response = json.loads(proc.stdout.readline())
print(response)
```

### 关键踩坑

- **protocolVersion 是数字 1**：最初用了日期字符串 `2025-06-01` 导致 `Invalid params` 错误，正确值为 `1`
- **stdout vs stderr**：所有业务输出在 stdout（ACP JSON），日志/错误在 stderr。管道通信时只需读取 stdout
- **--cli 模式**：该包另支持 `--cli` 参数直接调用 Claude CLI（相当于 `claude -p`），非 ACP 模式
- **消息分隔符就是 `\n`**：不要加 `Content-Length:` 前缀或其他 MCP 风格的帧格式——标准的换行分隔 JSON 即可

## 下一步行动

1. ~~确认 API 兼容性~~ ✅ 已确认：智谱 Anthropic 兼容端点可用
2. ~~安装并验证 claude-agent-acp~~ ✅ v0.39.0 安装成功，ACP 握手验证通过
3. 🔄 **设计 Hermes 侧的 ACP 管道**（2026-06-02 与 CC 讨论中，详见下方架构设计讨论）
4. ~~实现 Python ACP 客户端~~ ✅ **端到端验证通过**（2026-06-02）— 详见下方 E2E 验证结果
5. **渐进迁移**：先并存（tmux + ACP），验证稳定性后切换
6. **备选**：若 ACP 适配器有问题，继续打磨 tmux 方案

## 架构设计讨论（2026-06-02 Hermes × CC）

CC 在讨论中提出了 5 个关键设计决策，部分已定论：

### #1 SSH Pipe 数据流方向

| 方案 | 描述 | 评估 |
|------|------|------|
| A: Hermes SSH → Windows | 云端 Python 客户端通过 SSH pipe 连 Windows ACP stdio | **推荐** — 与现有 tmux 方向一致，复用 Tailscale，无需额外隧道 |
| B: Windows SSH → 云端 | CC 所在 Windows 主动维持到云端的 SSH | 需要 Windows 端常驻 SSH 进程 |
| C: 双向 SSH 隧道 | 类似现有 dashboard 的 -L 转发 | 可复用已有模式 |

**倾向**：方案 A — `ssh <ssh-alias> "claude-agent-acp"` 建立 stdio 管道，最简且方向与 tmux 一致。

### #2 协议层实现方式

- **裸 JSON-RPC over stdio**：直接实现 ACP JSON-RPC，无需第三方 SDK
- ACP 协议本身是简单的 JSON-RPC，自己实现 parse/pack 即可，预计几百行 Python
- claude-agent-acp 无官方 Python client SDK

### #3 会话管理与 tmux 共存 ✅ 已定论

**ACP 和 CC/tmux 互不感知、互不冲突**：
- ACP 管自己的 Claude 会话（通过 `loadSession` 持久化）
- tmux 管 CC 的交互式协作
- Hermes 侧路由层决定消息走哪个通道
- ACP 有序列号，断连后可 `loadSession` 恢复，比 tmux 断连恢复更可靠

### #4 CC 角色定位 ✅ 已定论

**CC 在此架构中是纯执行层，ACP 客户端独立于 CC**：
- Hermes 通过 ACP 直接调用 Claude API（经智谱 Anthropic 兼容端点）
- 不需要 CC 中转
- CC 继续走现有 tmux 协作协议，处理需要交互式审批/文件操作的任务
- ACP 和 tmux/CC 是两条并行通道

### #5 错误处理与重连

- SSH pipe 断开 → 自动重连 + `loadSession` 恢复
- ACP 协议层错误 → JSON-RPC error 响应处理
- 优势：ACP 有消息序列号和会话 ID，断点恢复比 tmux 盲 reconnect 更可靠

### 整体架构

```
用户(QQ/飞书) → Hermes(云端)
                  ├── tmux → SSH → CC(Windows)  ← 交互式协作，文件操作
                  └── ACP Client(Python) → SSH pipe → claude-agent-acp(Windows)
                                                        └── Claude Agent SDK → 智谱 Anthropic 端点
```

两条通道并行，Hermes 路由层决定消息走向。

## 参考资料

- [ACP 协议规范](https://agentclientprotocol.com)
- [Claude Agent SDK TypeScript](https://github.com/anthropics/claude-agent-sdk-typescript)
- [CC Headless Mode 文档](https://code.claude.com/docs/en/headless)
- [CC Issue #6686 - ACP 支持请求](https://github.com/anthropics/claude-code/issues/6686)
- [Hermes Issue #689 - 远程 Agent 连接](https://github.com/NousResearch/hermes-agent/issues/689)
- [acp-implementation.md](acp-implementation.md) — P1-P3 实施阶段的所有修正细节和集成测试结果

## ⚠️ ACP 能力边界（2026-06-02 最终结论，次日修正）

经过系统性验证，claude-agent-acp v0.39.0 的能力矩阵如下：

| 能力 | 声明 | 实际 | 验证方式 |
|------|------|------|---------|
| MCP 工具调用 | `mcpCapabilities: {http:true, sse:true}` | ❌ `mcpServers` 只接受空数组 `[]` | 6 种格式全部 `Invalid params`；ACP 协议规范要求的 `name+command+args` 格式同样失败 |
| 会话持久化 | `loadSession: true` | ✅ `session/load`（单数）可用 | **之前错误：** 测了 `sessions/load`（复数）报 `Method not found`，正确方法名是 `session/load` |
| 会话恢复 | `sessionCapabilities.resume` | ✅ `session/resume` 可用 | SSH 断连后重新 initialize → session/resume 恢复上下文 |
| 会话关闭 | — | ✅ `session/close` 可用 | — |
| 文件操作 | 无声明 | ❌ 无文件系统访问 | — |
| 命令执行 | 无声明 | ❌ 无 shell 访问 | — |

**session/load 端到端验证（2026-06-02）：**
```
Step1: 创建session → "记住我喜欢蓝色" → 断开
Step2: 重新initialize → session/load → "你记住了什么？"
  → 回复：你喜欢的颜色是蓝色 🔵  ← 上下文完整保留
```

**ACP 现阶段定位：纯推理通道，不是 CC 替代品。**

| ACP 能做 | ACP 不能做 |
|----------|-----------|
| 纯推理/分析（法律、策略） | 读写本地文件 |
| 文档草稿生成 | 执行命令/脚本 |
| 会话持久化（session/load） | 调用 MCP 工具（mcpServers 参数不生效） |
| 流式输出 + cost 追踪 | — |

**决策：ACP 保持一次性推理定位。需要工具/文件操作的场景继续走 CC。**

## 🎉 E2E 端到端验证（2026-06-02）

Hermes 侧 Python 脚本 `~/.hermes/scripts/acp_test.py` 测试结果：**全链路通过**。

### 远程命令

```bash
ssh <ssh-alias> "set ANTHROPIC_BASE_URL=<api-endpoint-anthropic> && set ANTHROPIC_AUTH_TOKEN=<key> && set ANTHROPIC_MODEL=glm-5-turbo && set ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5-turbo && claude-agent-acp"
```

### 测试结果

| 步骤 | 方法 | 结果 |
|------|------|------|
| Step 1 | SSH 启动 ACP 进程 | ✅ 连接成功 |
| Step 2 | `initialize` | ✅ serverInfo 返回，capabilities 确认 |
| Step 3 | `session/new` | ✅ sessionId: a44c8521-... |
| Step 4 | `session/prompt` | ✅ stopReason 返回 |
| Step 5 | stdin.close() → 清理 | ✅ exit code 0 |

### CC 脚本的三个错误（已修正）

| 问题 | CC 错误值 | 正确值 | 依据 |
|------|----------|--------|------|
| ACP 方法名 | `messages/create` | `session/new` → `session/prompt` | client.js 示例 + 源码确认 |
| BASE_URL | `api/paas/v4/anthropic` | `api/anthropic` | 智谱文档：Anthropic 协议端点是 `/api/anthropic`，OpenAI 协议端点是 `/api/paas/v4`，不存在混合端点 |
| model 参数 | 在 prompt 中传 `model: "claude-sonnet-4-..."` | 不传；由环境变量 `ANTHROPIC_MODEL=glm-5-turbo` 控制 | ACP client.js 示例中 session/new 和 prompt 均不传 model 参数 |

## 📡 P0 参数结构探明（2026-06-02 Hermes 侧探测）

### session/new

**请求**（accepted fields）：
```json
{
  "cwd": "/path/to/workdir",
  "mcpServers": [],
  "systemPrompt": "系统提示词（接受，不报错）",
  "mode": "plan|default|acceptEdits|bypassPermissions|...",
  "model": "optional-override（一般不需要）"
}
```

**响应**：
```json
{
  "sessionId": "uuid",
  "models": {
    "availableModels": [{"modelId": "sonnet", "name": "glm-5-turbo"}, ...],
    "currentModelId": "sonnet"
  },
  "modes": {
    "currentModeId": "acceptEdits",
    "availableModes": ["auto","default","acceptEdits","plan","dontAsk","bypassPermissions"]
  },
  "configOptions": [mode/model/effort selectors]
}
```

**模型映射**（智谱端点）：
| ACP 模型名 | 实际 GLM 模型 | 备注 |
|-----------|-------------|------|
| default | glm-5.1 | 高推理能力，$5/$25 per Mtok |
| opus | glm-5.1 | 最高档 |
| sonnet | glm-5-turbo | 当前默认，速度快 |
| haiku | glm-5-turbo | 轻量级 |

**SOUL 注入**：`systemPrompt` 通过 `session/new` 传入，可把 Hermes 的 SOUL.md + USER.md 拼接后作为系统提示词。

### session/prompt

**请求**：
```json
{
  "sessionId": "uuid",
  "prompt": [{"type": "text", "text": "你的问题"}]
}
```

**响应是流式 ndjson**（多行，method 始终为 `session/update`）：

| 行 | sessionUpdate 类型 | 内容位置 | 说明 |
|----|-------------------|---------|------|
| N | `available_commands_update` | `params.update.availableCommands` | CC 可用命令列表（一次性） |
| N | `usage_update` (0 tokens) | `params.update.used=0` | 初始用量 |
| N+ | `agent_thought_chunk` | `params.update.content.text` | 思考过程（逐 token） |
| N+ | `agent_message_chunk` | `params.update.content.text` | **实际回复文本**（逐 token） |
| N | `usage_update` (final) | `params.update.used/cost` | 最终用量和费用 |
| **末行** | **id=N 的 response** | `result: {stopReason, usage}` | **不含文本，仅 stopReason + usage** |

**关键发现**：回复内容在 `agent_message_chunk` 中逐 token 推送，不在最终 response 里。提取文本需累加所有 `agent_message_chunk` 的 `content.text`。

**Usage 结构**：
```json
{
  "used": 53371,
  "size": 200000,
  "cost": {"amount": 0.266927, "currency": "USD"}
}
```

## 🏗️ P1 ACP Client 实现（2026-06-02）

### 模块结构

```
~/.hermes/acp_client/
├── __init__.py          # 导出 ACPClient, ACPSession, build_system_prompt
├── config.py            # SSH_TARGET, 超时常量, MODEL_MAP, paths
├── client.py            # ACPClient 核心类（SSH pipe + ndjson + 超时 + 重连）
├── session.py           # ACPSession 封装（create + prompt，流式解析）
└── prompt_builder.py    # SOUL.md + USER.md + ACP_ROLE_APPENDIX 拼接
```

### 核心 API

```python
from acp_client import ACPClient, ACPSession

with ACPClient(api_key="...") as client:
    session = ACPSession.create(client, mode="plan")
    result = session.prompt("你的问题")
    print(result.text)       # 完整回复
    print(result.thoughts)   # 思考过程
    print(result.usage.cost) # 费用（USD）
```

### CC P1 代码中的两个关键错误（已修正）

| 错误 | CC 写成了 | 正确 | 影响 |
|------|----------|------|------|
| 环境变量名 | `ANTHROPIC_API_KEY` | `ANTHROPIC_AUTH_TOKEN` | ACP 进程无法认证 |
| 流式事件解析 | `event.get("method") == "agent_message_chunk"` | 先检查 `method == "session/update"`，再取 `params.update.sessionUpdate` | 回复文本提取永远为空 |

**正确的事件解析逻辑**：
```python
if event.get("method") == "session/update":
    update = event.get("params", {}).get("update", {})
    session_update = update.get("sessionUpdate", "")
    if session_update == "agent_message_chunk":
        text = update.get("content", {}).get("text", "")
```

