---
description: "打断当前 Hermes 协作任务，记录中断点后停止"
argument-hint: "[原因（可选）]"
allowed-tools: Read, Write, Bash(date:*), Edit
---

请执行以下任务中断流程：

## 步骤

1. 获取当前时间戳（格式 YYYYMMDD_HHMMSS）
2. 读取 `{PROJECT_DIR}/hermes_collab/status.json` 确认当前进行中的任务
3. 写入中断记录到 `{PROJECT_DIR}/hermes_collab/conv_stop_<时间戳>.md`：

```markdown
# conv_stop_YYYYMMDD_HHMMSS.md

## 中断记录
- 时间：<当前时间>
- 原因：$ARGUMENTS（或"用户手动中断"）

## 当前进度
- 进行中的任务：<任务描述>
- 已完成步骤：<列举>
- 未完成步骤：<列举>

## 建议
- 恢复时需从 <步骤> 继续
- 相关文件：<列表>

[state: task=stop status=interrupted files=[conv_stop_xxx.md] upgrade=false]
```

4. 更新 `{PROJECT_DIR}/hermes_collab/status.json`：
   - 将当前进行中的任务状态标记为 "interrupted"
   - 添加 stop 文件到 conv_files 列表
5. 发卡片（内容与中断记录一致，包含完整进度和恢复指引）

注意：
- 如果有长时间运行的后台任务（Bash），先调用 TaskStop 终止
- 不要删除任何已完成的工作文件
- 中断记录应足够详细，使恢复时无需重新分析
