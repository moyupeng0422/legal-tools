# Hermes × WorkBuddy 飞书协作 Skill

云端 Hermes（Ubuntu）通过飞书群聊 + SSH 双通道指挥本地 WorkBuddy（Windows）执行任务——发任务、写文件、辩论、审阅，全程用户无需传话。

## 功能特点

- **双通道通信**：飞书 REST API（任务下发/回复接收）+ SSH（文件直读/状态监控）
- **结构化标记**：`[任务]`/`[讨论]`/`[辩论]`/`[协议调整]` 四种消息前缀
- **多轮辩论**：R1→R2→R3 三轮独立校验，确保结论质量
- **交付物分离**：沟通记录（conv）与成品交付（out）独立管理，v3.0 架构
- **状态灯监控**：status.json 实时追踪任务阶段，SSH 轮询零延迟感知
- **斜杠命令**：`/status`、`/stop`、`/priority` 支持用户直接操作

## 使用方法

### Hermes 端（云端 Ubuntu）

将 `hermes/` 目录下文件复制到 Hermes 的 CodeBuddy 配置目录：

```
cp hermes/SKILL.md {HERMES_PROJECT_DIR}/.codebuddy/skills/workbuddy-collab/SKILL.md
cp hermes/references/* {HERMES_PROJECT_DIR}/.codebuddy/skills/workbuddy-collab/references/
cp hermes/scripts/* {HERMES_PROJECT_DIR}/.codebuddy/skills/workbuddy-collab/scripts/
```

将 `.env.template` 复制为 `.env` 并填入实际值（`.env` 仅在 Hermes 侧使用）。

### WorkBuddy 端（本地 Windows）

将 `workbuddy/` 目录下文件复制到 WorkBuddy 项目目录：

```
# 协作规则（WorkBuddy 启动自动加载）
cp workbuddy/MEMORY.md {PROJECT_DIR}/.workbuddy/memory/MEMORY.md

# 斜杠命令
cp workbuddy/commands/*.md {PROJECT_DIR}/.codebuddy/commands/hermes/

# 协作工作区
cp -r workbuddy/hermes_collab/* {PROJECT_DIR}/hermes_collab/
```

## ⚠️ 使用前必读

本规范中的路径、ID 等均为占位符，使用前**必须替换为你自己的实际配置**：

| 占位符 | 替换为 | 示例 |
|--------|--------|------|
| `{PROJECT_DIR}` | WorkBuddy 项目根目录 | `D:\workbuddy\MyProject\` |
| `{SSH_ALIAS}` | Hermes 连接 WorkBuddy 的 SSH 别名 | `local-win` |
| `{FEISHU_CHAT_ID}` | 飞书群聊 ID | `oc_xxxxxxxxxxxxxxxx` |
| `{WORKBUDDY_OPEN_ID}` | WorkBuddy 在飞书群中的 open_id | `ou_xxxxxxxxxxxxxxxx` |
| `{WORKBUDDY_HERMES_OPEN_ID}` | Hermes 视角的 WorkBuddy open_id | `ou_xxxxxxxxxxxxxxxx` |
| `{FEISHU_APP_ID}` | 飞书应用 AppID | 飞书开放平台 > 应用凭证 |
| `{FEISHU_APP_SECRET}` | 飞书应用 AppSecret | 飞书开放平台 > 应用凭证 |
| `{HERMES_PROJECT_DIR}` | Hermes 项目根目录 | `/home/user/hermes-project/` |

**占位符分布：**

| 文件 | 包含的占位符 |
|------|-------------|
| `workbuddy/MEMORY.md` | `{PROJECT_DIR}`, `{SSH_ALIAS}` |
| `workbuddy/commands/*.md` | `{PROJECT_DIR}` |
| `workbuddy/hermes_collab/PROTOCOL.md` | `{PROJECT_DIR}`, `{SSH_ALIAS}` |
| `hermes/SKILL.md` | `{FEISHU_CHAT_ID}`, `{WORKBUDDY_OPEN_ID}`, `{WORKBUDDY_HERMES_OPEN_ID}`, `{SSH_ALIAS}`, `{PROJECT_DIR}` |
| `.env` | `{FEISHU_APP_ID}`, `{FEISHU_APP_SECRET}`, `{FEISHU_CHAT_ID}`, `{WORKBUDDY_OPEN_ID}`, `{WORKBUDDY_HERMES_OPEN_ID}`, `{SSH_ALIAS}` |

## 架构概览

```
用户 ←→ Hermes(云端Ubuntu)
         │        │
         │ 飞书群聊│ ← REST API 发消息 / ListMessage 轮询回复
         │   ↕    │
         └────────┘
                  │
              SSH 直读
                  │
         WorkBuddy(本地Windows)
                  │
              飞书群聊 ← WorkBuddy GUI 收发消息 + 写文件
```

**消息流转**：

1. 用户 @Hermes 下达任务
2. Hermes @WorkBuddy 发送 `[任务] 描述`
3. WorkBuddy 收到后自动执行，写入 conv 文件，更新 status.json，发卡片通知
4. Hermes 通过 SSH 读取 status.json 和 conv 文件内容
5. Hermes 将结果汇报用户

**消息前缀**：

| 前缀 | 用途 |
|------|------|
| `[任务]` | 派任务给 WorkBuddy 执行 |
| `[讨论]` | 非执行型讨论 |
| `[辩论]` | 对 WorkBuddy 结果有异议，走 R1→R2→R3 辩论 |
| `[协议调整]` | 更新协作规则 |

## WorkBuddy 斜杠命令

| 命令 | 功能 |
|------|------|
| `/hermes:status` | 查看当前协作状态 |
| `/hermes:stop` | 中断当前任务并记录断点 |
| `/hermes:priority` | 保存进度，插队处理新任务 |

## 部署验证

1. 飞书群中 @Hermes 发送：`[任务] 测试协作通道`
2. 检查 WorkBuddy 侧是否收到消息并自动创建 `conv_测试协作通道_YYYYMMDD.md`
3. 检查 `status.json` 中 `current_task.status` 是否变为 `completed`
4. Hermes 侧 SSH 执行 `cat status.json` 确认状态灯可见
5. Hermes 侧 SSH 执行 `cat conv_测试协作通道_YYYYMMDD.md` 确认内容完整
6. 发送 `[辩论] conv_测试协作通道_YYYYMMDD.md` 测试辩论流程

## 文件说明

| 文件/目录 | 说明 |
|-----------|------|
| `hermes/SKILL.md` | Hermes 端操作流程总控（反面案例 + 规则汇总） |
| `hermes/references/` | 参考文档（写作工作流、响应时间观测、v3.0 架构） |
| `hermes/scripts/` | 自动化脚本（SSH 监控、回复轮询、conv 增量读取） |
| `workbuddy/MEMORY.md` | WorkBuddy 协作规则（部署到 `.workbuddy/memory/`） |
| `workbuddy/commands/` | 斜杠命令（部署到 `.codebuddy/commands/hermes/`） |
| `workbuddy/hermes_collab/` | 协作工作区（部署到 `{PROJECT_DIR}/hermes_collab/`） |
| `.env.template` | 环境变量模板（仅 Hermes 侧使用） |

## 许可证

MIT License - 详见 [LICENSE](LICENSE)
