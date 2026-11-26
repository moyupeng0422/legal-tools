> 🔐 **占位符说明**：本文件为发布版，所有 ID（cli_/ou_/oc_）、Tailscale IP、用户名均已替换为占位符。
> 使用时请将占位符替换为你自己环境的真实值；原始内部版含真实 ID，**不得外发**。

# 凭据集中管理

> 本文档集中所有飞书协作相关的凭据、ID、群名等敏感信息。其他 reference 文件中涉及这些 ID 时引用本文，不硬编码。
>
> 打包发布/脱敏时，本文档可单独处理 (如替换为占位符)。

## 1. Hermes Profile 凭据

| Profile | App ID | 自身 open_id | Gateway 端口 |
|---------|--------|------------|-------------|
| Default (Hermes) | `<app-id>` | `<open-id>` | (默认) |
| 法律助手 (legal) | `<app-id>` | `<open-id>` | — |
| 家庭助手 (family) | `<app-id>` | `<open-id>` | — |
| Coordinator (传令员) | `<app-id>` | `<open-id>` | 8646 |

## 2. 外部 Bot 凭据

| Bot | App ID | 自身 open_id | Hermes App 视角 open_id |
|-----|--------|------------|----------------------|
| 芭迪 (WorkBuddy) | `<app-id>` | `<open-id>` | `<open-id>` |
| CC (Claude Code via bridge) | `<app-id>` | `<open-id>` | ✅ <bot群名>（bot_count=5 实证 2026-11-23） |

## 3. 跨 App open_id 映射

| 在哪个 App | 看到的 open_id |
|----------|--------------|
| legal App 中的 Hermes | `<open-id>` |
| default (Hermes) App 中的法律助手 | `<open-id>` |
| default App 中的 Coordinator | `<open-id>` (待跨 App 事件确认) |
| default App 中的芭迪 | `<open-id>` |

## 4. 飞书群信息

| 项目 | 值 |
|------|-----|
| 群名称 | <bot群名> |
| chat_id | `<collab-group-chat-id>` |

## 5. 协作目录路径

| 目录 | 路径 |
|------|------|
| 芭迪协作目录 | `D:\<workbuddy-root>\Claw\hermes_collab\` |
| CC 协作目录 | `D:\<projects-root>\cc_hermes_collab\` |
| 云端 Hermes 协作目录 | `~/hermes_collab/` (Ubuntu 服务器) |

## 6. SSH 连接

| 项目 | 值 |
|------|-----|
| SSH Host alias | `local-win` |
| SSH 端口 | 2222 |
| 网络 | Tailscale |

## 7. 使用约定

- 其他 reference 文件中涉及上述 ID 时，**必须引用本文**而非硬编码
- 示例：`<at user_id="<见 credentials.md §1 Default>">Hermes</at>`
- 实际使用时从本表查值填入

## 8. 安全注意

- 本文件包含敏感凭据，**不要提交到公开 git repo**
- 打包发布 skill 时，用占位符替换 (如 `<HERMES_APP_ID>`、`<BAR_DI_OPEN_ID>`)
- 定期审查：凭据是否过期、open_id 是否仍有效

## 9. 跨 App 消息发送凭据路由 (2026-07-06)

**踩坑**：Coordinator profile 的 `.env` 中 `FEISHU_APP_ID=<app-id>` 是 Coordinator 自身 App 的 ID。用这个 app 的 tenant_access_token 发消息给 CC 的 open_id (`<open-id>`) 会报 `99992361 open_id cross app`——因为 CC 属于另一个 App。

**正确做法**：用 **Gateway App** (`<app-id>`，在 `/home/ubuntu/.hermes/.env`) 的 tenant_access_token，发送到**群 chat_id**（`<collab-group-chat-id>`），消息体中用 `<at user_id="ou_xxx">` 标签 @ 目标。

**规则**：
- **@ 任何 Bot 时**，必须用 Gateway App 的凭据（`/home/ubuntu/.hermes/.env`），不能用 profile 自身 App 的凭据
- **发送目标**用群 chat_id（`receive_id_type=chat_id`），不用目标 Bot 的 open_id
- Profile `.env` 中的 App ID/Secret 是给 Gateway 进程鉴权用的，不用于直接调 REST API
- **获取 tenant_access_token 的代码环境**：`terminal()` 中 `os.environ` 有完整的值，`execute_code()` 中 `os.environ` 可能不包含 Hermes 加载的 `.env` 值——用 `terminal()` 或写脚本文件后执行
