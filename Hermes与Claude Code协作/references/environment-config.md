# 环境配置参考

> 本文件集中本 skill 中使用的环境特定值（IP/路径/模型等）。其他 reference 保留各自内联值便于操作；本文件作为查阅权威源。

## Tailscale 网络

| 节点 | IP | 说明 |
|------|-----|------|
| 云端 Ubuntu（Hermes 运行处） | `<cloud-tailscale-ip>` | Hermes 主机，非 Windows |
| Windows 笔记本（CC 运行处） | `<windows-tailscale-ip>` | CC 本地机器 |

⚠️ **常见混淆**：`ssh -p <ssh-port> <cloud-tailscale-ip>` 实际是回到云端自己，**不是**连 Windows。Windows 必须用 `ssh -p <ssh-port> <ssh-user>@<windows-tailscale-ip>`。

## SSH 配置

- **Alias**: `<ssh-alias>`（在 `~/.ssh/config` 中定义）
- **端口**: `2222`
- **用户**: `<ssh-user>`
- **快速连通测试**: `ssh -o ConnectTimeout=10 <ssh-alias> "echo OK"`

## tmux Session

- **固定 session 名**: `claude-session`（单 session 复用，多任务通过 `claude_task_map.json` 映射）
- **窗口尺寸**: `tmux new-session -d -s claude-session -x 200 -y 60`
- **架构**: tmux 在云端运行，session 内部 SSH 到 Windows 执行 cmd，不是 Windows 上跑 tmux

## API Endpoint（CC 与 Hermes 不同）

> ⚠️ CC 和 Hermes 走不同的 API endpoint，命令操作时注意区分。

| 端 | Endpoint | 来源 |
|----|---------|------|
| **CC**（本地 Windows Claude Code） | `<api-endpoint-anthropic>` | `~/.claude/settings.json` 的 `ANTHROPIC_BASE_URL` |
| **Hermes**（云端 Ubuntu） | `<api-endpoint-coding>` | Hermes `config.yaml`（Coding Plan API） |

## 模型配置

### CC 侧（基于 `~/.claude/settings.json`）

- `ANTHROPIC_DEFAULT_OPUS_MODEL`: `glm-5.2[1m]`（`[1m]` 后缀启用 1M context window）
- `ANTHROPIC_DEFAULT_SONNET_MODEL`: `glm-5.2[1m]`（同上）
- `ANTHROPIC_MODEL`（默认）: `glm-5-turbo`（无 `[1m]` 后缀，基础 200K context）
- `ANTHROPIC_DEFAULT_HAIKU_MODEL`: `glm-5-turbo`

### Hermes 侧

- **Default profile**: `glm-5.2`（走 API billing 模式，具体 context window 长度以 Hermes `config.yaml` 实际配置为准）
- **Coordinator profile**: 工作模型不固定（当前 `glm-5-turbo`），基础 200K context

## Windows 关键路径

- **用户目录**: `<windows-userhome>\`
- **项目根**: `<windows-project-root>\`
- **Claude 配置**: `<windows-userhome>\.claude\`（全局）/ `<windows-project-root>\.claude\`（项目）
- **CC 协作 context**: `<windows-project-root>\.claude\rules\hermes-collab.md`（CC 自动加载）
- **Bridge 配置**（CC 飞书接入）: `<windows-userhome>\.lark-channel\config.json`
- **临时文件中转**: `<windows-userhome>\temp.md`（SSH 中文路径乱码时的 ASCII workaround）

## 状态文件

- **任务追踪**: `claude_task_map.json`（云端 Hermes 工作目录，session↔task 映射）
- **任务状态**: `cc-task-state.json`（注：self-audit 发现常未被创建，不可依赖）
- **CC 会话存储**: `~/.claude/projects/`（CC session jsonl 文件）

## 启动序列关键参数

```bash
# 云端 tmux 内执行
ssh <ssh-alias>                              # 1. SSH 连接
cd /d "<windows-project-root>"                   # 2. 切换到项目目录（不是 home）
claude --model glm-5.2                     # 3. 启动 CC（禁止 --dangerously-skip-permissions）
# Bypass Permissions 警告弹窗：1=No exit / 2=Yes accept
# 后续：HERMES-ACTIVATE → /rename Hermes:<任务名> → 写 task_map
```

恢复旧对话：`claude --model glm-5.2 --resume`（启动参数，弹出交互列表）或 CC 内部 `/resume <会话名>`。
**绝对禁止**：`--continue`（可能误入用户 session）、`--dangerously-skip-permissions`。

## 数据源权威性等级

| Tier | 来源 | 用途 |
|------|------|------|
| **A** ⭐⭐⭐ | 最高人民法院执行信息公开网、国家企业信用信息公示系统、国家税务总局、信用中国 | 司法/工商/税务核心 |
| **B** ⭐⭐ | 工信部 ICP、自然资源部、国家知识产权局（商标局/专利）、地方工商 | 行业主管平台 |
| **C** ⭐ | 协会、半官方平台 | 参考 |

跨源冲突时 Tier A 优先。
