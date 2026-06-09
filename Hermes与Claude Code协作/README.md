# Hermes × Claude Code 协作规范

云端 Hermes（Ubuntu）通过 SSH + tmux 指挥本地 Claude Code（Windows）执行任务的结构化协作协议。

## 功能特点

- **双通道通信**：Print Mode（一次性任务）和 tmux 模式（多轮交互）
- **结构化标记**：ACK/DONE/ERROR/PAUSE/DISPUTE 五种消息协议
- **CC 状态监控**：三区域终端分析 + 两步确认法判断 CC 空闲
- **辩论协议**：R1→R2→R3 三轮独立校验，确保结论质量
- **拒绝与降级**：CC 拒绝不规范指令，协议违反自动降级
- **错误恢复**：PAUSE + 四种恢复路径（恢复/跳过/终止/人工）

## 使用方法

### Hermes 端（云端 Ubuntu）

将 `SKILL.md` 加载到 Hermes 的上下文中。`references/` 下 22 个参考文档按需引用，涵盖会话管理、错误恢复、监控辩论、SSH 诊断等场景。

### CC 端（本地 Windows）

将 `hermes-collab.md` 放入 `.claude/rules/` 目录，CC 启动时会自动加载。该文件定义了 CC 的协作身份、标记输出格式、拒绝权和降级规则。

## 架构概览

```
用户 ←→ Hermes(云端) ──SSH/tmux──→ CC(本地Windows)
         ↑                              │
         └──── capture-pane 监控 ←──────┘
```

## 文件说明

| 文件/目录 | 说明 |
|-----------|------|
| `SKILL.md` | Hermes 端操作流程总控 |
| `hermes-collab.md` | CC 端协作规范（放入 `.claude/rules/` 自动加载） |
| `references/` | 22 个参考文档（会话生命周期、错误恢复、监控辩论等） |
| `templates/` | 启动模板 |
