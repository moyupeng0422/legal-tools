---
description: "保存当前任务进度，立即插队处理紧急新任务"
argument-hint: "[新任务描述]"
allowed-tools: Read, Write, Bash(date:*), Edit, Glob
---

请执行以下插队流程：

## 步骤

1. 获取当前时间戳（格式 YYYYMMDD_HHMMSS）
2. 读取 `{PROJECT_DIR}/hermes_collab/status.json` 确认当前进行中的任务
3. **保存当前任务进度**到 `{PROJECT_DIR}/hermes_collab/conv_priority-save_<时间戳>.md`：

```markdown
# conv_priority-save_YYYYMMDD_HHMMSS.md

## 插队保存
- 时间：<当前时间>
- 被中断任务：<任务描述>
- 已完成步骤：<列举>
- 关键上下文：<变量、中间结果、文件路径>
- 下一步：<恢复时从何处继续>

[state: task=priority-save status=paused files=[...] upgrade=false]
```

4. 更新 `{PROJECT_DIR}/hermes_collab/status.json`：
   - 将当前任务标记为 "paused"
   - 添加 priority-save 文件到 conv_files

5. **立即开始处理新任务**：$ARGUMENTS
   - 遵循标准 [任务] 流程：分析 → 执行 → 写 conv → 更新 status → 发卡片
   - 新任务 conv 命名：`conv_<新任务简写>_YYYYMMDD.md`
   - 新任务 result 写在卡片中一并通知

6. 新任务完成后，发卡片（包含新任务完整结果 + 旧任务已保存的恢复指引，不精简）

注意：
- 保存文件必须包含足够上下文，避免恢复时丢失状态
- 新任务独立于旧任务，不共用 conv 文件
- 插队任务本身也可以被再次插队（但不建议嵌套超过 2 层）
