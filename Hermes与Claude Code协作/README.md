# Hermes × Claude Code 协作规范

云端 Hermes（Ubuntu）通过 SSH + tmux 指挥本地 Claude Code（Windows）执行任务的结构化协作协议。v3.40+。

## 功能特点

- **双模式通信**：Print Mode（一次性任务，推荐）和 tmux 模式（多轮交互）
- **长时监控模式**：轮询策略、自言自语格式（💭/⚠️/📋）、token 预算管理、分段汇报
- **结构化标记**：ACK/DONE/ERROR/PAUSE 五种消息协议，支持辩论 DISPUTE
- **CC 状态监控**：capture-pane 轮询 + 三区域终端分析判断 CC 空闲
- **辩论协议**：R1→R2→R3 三轮独立校验，确保结论质量（含风险分级、R2 子轮）
- **拒绝与降级**：CC 拒绝不规范指令，协议违反自动降级
- **错误恢复**：PAUSE + 四种恢复路径（恢复/跳过/终止/人工），含长任务 SSH 断连恢复
- **CC Hook 数据**：CC hooks 触发事件的结构化 schema 参考
- **Pitfalls**：完整反面案例库，按场景分类，含 TOC 导航
- **环境配置集中**：IP/路径/SSH/API 端点统一在 `references/environment-config.md`

## 使用方法

### Hermes 端（云端 Ubuntu）

将 `SKILL.md` 加载到 Hermes 的上下文中。`references/` 下 31 个参考文档按需引用，涵盖会话管理、错误恢复、监控辩论、长时监控、SSH 诊断、ACP 研究、文件传输等场景。

### CC 端（本地 Windows）

将 `hermes-collab.md` 放入 `.claude/rules/` 目录，CC 启动时会自动加载。该文件定义了 CC 的协作身份、标记输出格式、拒绝权和降级规则。

## ⚠️ 使用前必读

本规范中的路径、IP、端口等均为占位符，使用前**必须替换为你自己的实际配置**：

| 占位符 | 替换为 | 示例 |
|--------|--------|------|
| `<cloud-tailscale-ip>` | 云端 Ubuntu 的 Tailscale IP | `100.x.x.x` |
| `<windows-tailscale-ip>` | Windows 的 Tailscale IP | `100.x.x.x` |
| `<windows-public-ip>` | Windows 的公网 IP | `x.x.x.x` |
| `<ssh-port>` | SSH 监听端口 | `2222` |
| `<ssh-alias>` | `~/.ssh/config` 中的 Host 别名 | `local-win` |
| `<ssh-user>` | Windows SSH 登录用户名 | `your-username` |
| `<http-port>` | 临时 HTTP 文件服务端口 | `18888` |
| `<windows-userhome>` | Windows 用户目录 | `C:\Users\yourname` |
| `<windows-project-root>` | 项目根目录 | `D:\your-project` |
| `<api-endpoint-anthropic>` | CC 的 Anthropic 兼容 API 端点 | 由你的 AI 服务商提供 |

## 架构概览

```
                    ┌─── 云端 Ubuntu ──────────────────────┐
                    │                                        │
用户 ←──→ Hermes ──→ tmux claude-session                    │
                    │    │                                   │
                    │    └── SSH ──→ Windows cmd ──→ CC     │
                    │                                        │
                    │    ←── capture-pane ── CC 输出 ←───── │
                    └────────────────────────────────────────┘
```

> tmux 在云端，不在 Windows。Hermes 通过 `tmux send-keys` 向 session 内发送命令，SSH 连接在 tmux session 内部，CC 运行在 Windows cmd 中。

## 文件说明

| 文件/目录 | 说明 |
|-----------|------|
| `SKILL.md` | Hermes 端操作流程总控（511 行，含 Print Mode + tmux 模式） |
| `hermes-collab.md` | CC 端协作规范（放入 `.claude/rules/` 自动加载） |
| `references/` | 31 个参考文档 |
| `scripts/` | 维护脚本（TOC 生成、pitfalls 提取/裁剪、SKILL.md 重建） |
| `templates/` | 启动模板（ACP bootstrap、批量验证） |

### references 重点文档

| 文件 | 说明 |
|------|------|
| `environment-config.md` | 环境配置权威源（IP/路径/SSH/API 端点集中管理） |
| `pitfalls.md` | 134 条完整反面案例库（含 TOC 分类导航） |
| `error-recovery.md` | 错误恢复协议（PAUSE + 四种恢复路径） |
| `monitoring-debate.md` | 监控与辩论协议（capture-pane 分析 + R1/R2/R3，含风险分级） |
| `monitoring-mode.md` | 长时监控模式（轮询策略、自言自语格式、token 预算管理） |
| `cc-hook-data-schemas.md` | CC Hooks 触发事件的结构化 schema 参考 |
| `session-lifecycle.md` | 会话生命周期管理（创建/恢复/销毁） |
| `ssh-diagnostics.md` | SSH 连接故障诊断 |
| `ssh-reconnect-playbook.md` | SSH 重连操作手册 |
| `bulk-file-transfer.md` | 批量文件传输（scp + http.server） |
| `acp-research.md` / `acp-implementation.md` | Agent Control Protocol 研究与实现 |

## 许可证

MIT License - 详见 [LICENSE](LICENSE)
