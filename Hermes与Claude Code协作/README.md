# Hermes与Claude Code协作

> **版本 v4.1.0** | 云端 Hermes Agent 通过 SSH+tmux / Print Mode 编排本地 Windows Claude Code 的完整协作规范

## 这是什么

一套双 AI Agent 结构化协作协议：Hermes（云端 Ubuntu）指挥 Claude Code（本地 Windows）执行文件操作、代码修改、Git 操作、脚本运行等任务。包含：

- **CC 端协议**（`references/cc-context-file.md` 部署草案——复制到 CC 侧 `.claude/rules/hermes-collab.md` 后由 CC 自动加载：结构化标记、DONE/ERROR/PAUSE、校验与回滚）
- **Hermes 端规范**（`SKILL.md`：会话生命周期、监控、辩论协议、错误恢复、文件传输）
- **五件套脚本**（`scripts/cc-tools/`：把裸 tmux send-keys 操作脚本化，消除结构性缺陷）
- **35 篇 references**（监控、辩论、ACP、传输、诊断、项目迁移/归档、pitfalls 完整集等）

## v3.x → v4.0 主要变化

### ① Print Mode (`claude -p`) 成为推荐方式

新增决策树：**能用 `-p` 就不用 tmux**。Print Mode 零截断风险、无需 capture-pane 轮询、权限精确可控（`--allowedTools`）；只有需要多轮辩论（R1→R2→R3 维持上下文）时才走 tmux。

```
一次性任务 / 纯分析 / 单轮写文件 → Print Mode (-p)
需要多轮辩论或长会话上下文      → tmux（配合五件套脚本）
```

### ② 五件套脚本化（`scripts/cc-tools/`，2026-11 定稿）

裸 `tmux send-keys` 发消息存在**同帧吞 Enter**的结构性缺陷（Ink TUI 将同帧文本+Enter 合并为粘贴事件，Enter 被吞——详见 pitfalls #20a/#157-bis）。五件套把高频操作固化为一发即用的脚本：

| 脚本 | 用途 |
|------|------|
| `cc-send.sh` | 结构化发消息（文本与 Enter 拆分发送 + 发后验证） |
| `cc-wait.sh` | 等待 CC 回复（capture-pane 轮询 + thinking 标记检测） |
| `cc-mode.sh` | 切换 CC 权限模式（plan / accept edits 等） |
| `cc-approve.sh` | 处理权限弹窗审批 |
| `cc-start.sh` | 六步法启动 CC（`CC_PROJECT_DIR` 环境变量指定项目目录） |

2026-11-22 起为**硬性工具链**：禁止裸 send-keys 发消息。

### ③ 辩论豁免声明制（2026-11-22，硬约束）

方案类输出（含新提出的方案/建议/立场）必须经 R2 质询**或显式声明豁免**（豁免入审计日志）——用机制替代纪律，堵住"未质询直接转达结论"的漏洞。

### ④ 协议 v2.1 升级

- **ACK 指纹**：收到 TASK 后必须回 ACK（含任务意图复述 + task_id/step/done 回显），CC 不做截断判断
- **done 语义**：done = 已收到 DONE 确认的最高 step 编号，只升不降
- **PAUSE / COMPLETE / 回滚策略**：PAUSE 必带 reason + suggested；ERROR/PAUSE 时不主动回滚，列 files_changed 供决策

### ⑤ references 32 → 35 个

新增 4 篇：`cc-mode-approve-scripts.md`（五件套详解）、`cc-project-migration.md`（项目迁移）、`cc-project-archival.md`（项目归档）、`skill-creation-workflow.md`（skill 开发流程）。

### ⑥ pitfalls 134 → 144 条

完整集 `references/pitfalls.md`（884 行）新增 v4.x 批次：#150（plan mode 假更新）、#157（Skill() 无法加载本地 skill）、#20a 重写版（send-keys 文本与 Enter 拆分，推翻旧同帧铁律）、#47b/c/d/e（DISCUSS 标记合法性 / 分段发送假阳性截断 / 完成状态误判 / Skill 加载）。SKILL.md 另保留 ~26 条核心高频。

## 占位符替换表

发布版已将环境特定值统一为占位符（权威源：[references/environment-config.md](references/environment-config.md)）。使用时按你的环境替换：

| 占位符 | 含义 | 示例 |
|--------|------|------|
| `<cloud-tailscale-ip>` | 云端 Ubuntu 的 Tailscale IP | `100.x.x.x` |
| `<windows-tailscale-ip>` | Windows 笔记本的 Tailscale IP | `100.x.x.x` |
| `<windows-username>` | Windows 登录用户名 | `yourname` |
| `<windows-hostname>` | Windows 主机名 | `LAPTOP-XXXX` |
| `<projects-root>` | 本地项目根目录 | `D:\projects` |
| `<api-endpoint>` | Anthropic 兼容 API endpoint（CC 与 Hermes 各自配置） | 各自 settings/config 中获取 |

> 模型配置示例使用 `glm-5.2[1m]` / `glm-5-turbo`（`[1m]` 后缀 = 1M context window），可替换为任意 Anthropic 兼容模型。

## 快速开始

```bash
# 1. 前置：Tailscale 连通 + SSH 免密（端口 2222）
ssh -o ConnectTimeout=10 <windows-username>@<windows-tailscale-ip> "echo OK"

# 2. 一次性任务（推荐）：Print Mode
claude -p "分析这个专利的有效性" --output-format json --max-turns 10

# 3. 长会话/辩论任务：tmux + 五件套
export CC_PROJECT_DIR="<projects-root>"
bash scripts/cc-tools/cc-start.sh        # 六步法启动
bash scripts/cc-tools/cc-send.sh "任务描述"
bash scripts/cc-tools/cc-wait.sh         # 等待回复
```

## 文件结构

```
Hermes与Claude Code协作/
├── SKILL.md                     # Hermes 端主规范（v4.1.0，555 行）
├── references/                  # 35 篇参考文档
│   ├── cc-context-file.md       # CC 端协议部署草案（→ CC 侧 .claude/rules/hermes-collab.md）
│   ├── environment-config.md    # 环境占位符权威源
│   ├── pitfalls.md              # 144 条完整集
│   ├── cc-mode-approve-scripts.md / cc-project-migration.md / cc-project-archival.md
│   ├── monitoring-*.md          # 监控与辩论
│   ├── ssh-*.md                 # SSH 诊断与重连
│   └── ...
├── scripts/                     # SKILL.md 维护脚本（Python）
│   └── cc-tools/                # 五件套运行时脚本（v4.0 新增）
└── templates/                   # ACP 引导模板
```

## 使用条件

- 云端：Hermes Agent 环境（任意支持 terminal 的 Agent 框架）
- 本地：Windows + Claude Code + Tailscale + SSH 免密
- 相关仓库：[legal-tools](https://github.com/moyupeng0422/legal-tools)

## 许可证

MIT — 见仓库根 [LICENSE](../LICENSE)
