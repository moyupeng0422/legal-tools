---
description: "一键输出 Hermes 协作状态到 conv 文件，供 SSH 拉取"
allowed-tools: Read, Write, Bash(date:*), Bash(ls:*), Glob, Edit
---

请执行以下 Hermes 协作状态报告：

## 步骤

1. 读取 `{PROJECT_DIR}/hermes_collab/status.json` 获取当前状态
2. 获取当前时间戳（格式 YYYYMMDD_HHMMSS）
3. 归纳：
   - 协议版本
   - 已有 conv 文件列表及状态
   - 辩论中文件（如有）
   - 已完成待归档文件
   - 最近 3 轮任务摘要
4. 写入 `{PROJECT_DIR}/hermes_collab/conv_status_<时间戳>.md`，按以下格式：

```markdown
# conv_status_YYYYMMDD_HHMMSS.md

## Hermes 协作状态报告
- 时间：<当前时间>
- 协议版本：<版本号>
- 工作目录：{PROJECT_DIR}

## conv 文件列表
| 文件 | 状态 | 备注 |
|------|------|------|

## 辩论中
- 无 / 列出

## 待归档
- 列出

## 最近活动
1. ...
2. ...
3. ...

[state: task=status-report status=done files=[conv_status_xxx.md] upgrade=false]
```

5. 更新 `{PROJECT_DIR}/hermes_collab/status.json` 的 `updated` 时间戳
6. 发卡片（内容与状态报告一致，包含完整摘要，不精简）
