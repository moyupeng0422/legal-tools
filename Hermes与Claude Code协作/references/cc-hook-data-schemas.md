# CC Hook Data Schemas & Known Gaps

> CC (Claude Code) 支持 PreToolUse、PostToolUse、Stop、Notification 等生命周期 hooks。
> 本文件记录各 hook 的 stdin 数据结构、已知限制、以及在构建 hook 驱动方案时的注意事项。

## Hook Types & stdin Schema

### PreToolUse

**触发时机**：CC 工具调用执行前（Write、Edit、Bash、Read 等）。

**stdin JSON**：
```json
{
  "tool_name": "Write",
  "tool_input": { "file_path": "...", "content": "..." },
  "session_id": "abc123-..."
}
```

**已知限制**：
- hook error 不阻止工具执行——文件操作仍会成功（见 pitfalls #135）
- `tool_input` 中的 `content` 字段可能为截断版本（超大文件时）

### PostToolUse

**触发时机**：CC 工具调用完成后。

**stdin JSON**：
```json
{
  "tool_name": "Write",
  "tool_input": { "file_path": "...", "content": "..." },
  "tool_output": "写入成功" 或 null,
  "session_id": "abc123-..."
}
```

**已知限制**：
- 大量工具调用时会产生刷屏式输出（每条工具调用都触发）
- IM 同步场景中不适合用 PostToolUse 同步——频率太高

### Stop

**触发时机**：CC 一轮对话结束时（assistant 输出完成后）。

**stdin JSON**：
```json
{
  "session_id": "abc123-...",
  "transcript_path": "/home/user/.claude/projects/.../abc123-....jsonl"
}
```

**⚠️ 关键限制（pitfall #136）**：
- **stdin 不包含 CC 回复文本**——只有 session_id 和 transcript_path
- 要获取回复文本，必须读取 jsonl 文件尾部并提取最后一条 assistant 消息
- jsonl 文件中的 content 格式不固定：
  ```json
  // 格式 1：纯字符串
  {"role": "assistant", "content": "回复文本"}
  
  // 格式 2：数组（含 thinking block）
  {"role": "assistant", "content": [
    {"type": "thinking", "thinking": "..."},
    {"type": "text", "text": "回复文本"}
  ]}
  ```
- 脚本需处理编码（Windows 路径、BOM）、大文件尾部读取（避免全文加载）

### Notification

**触发时机**：CC 发出通知时（工具调用需审批等）。

**stdin JSON**：
```json
{
  "message": "审批内容...",
  "session_id": "abc123-..."
}
```

**用途**：Hermes 当前配置中用于飞书通知（PreToolUse 权限审批时推送消息到飞书）。

## Hook 配置位置

### CC settings.json

路径：`~/.claude/settings.json`（Windows: `<windows-userhome>\.claude\settings.json`）

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "command": "powershell -File C:\\path\\to\\hook.ps1"
      }
    ],
    "PostToolUse": [...],
    "Stop": [...],
    "Notification": [...]
  }
}
```

### Hooks 目录（可选）

部分 CC 版本支持 `~/.claude/hooks/` 目录放置 hook 脚本，通过 settings.json 引用。

## Hook 脚本开发注意事项

1. **输出格式**：hook 的 stdout 会被 CC 读取。PreToolUse hook 的 stdout 用于显示反馈/警告，非空输出可能被 CC 当作错误信息。
2. **Exit code**：非零退出码 = hook error（见 pitfall #135），但不阻止工具执行。
3. **超时**：hook 执行有超时限制，长时间运行的 hook 可能被终止。
4. **编码**：Windows PowerShell 脚本需注意 UTF-8 BOM 和控制台编码问题。
5. **路径**：Windows 路径中的空格和中文字符需正确转义。

## IM 同步方案中的 Hook 使用评估

| Hook | 适合 IM 同步？ | 原因 |
|------|---------------|------|
| Stop | ⚠️ 有条件适合 | 触发频率合理（每轮一次），但需额外读 jsonl 获取回复文本，脚本复杂度高 |
| PostToolUse | ❌ 不适合 | 频率过高（每次工具调用都触发），刷屏 |
| PreToolUse | ❌ 不适合 | 是前置检查，不包含输出内容 |
| Notification | ❌ 不适合 | 仅审批场景触发 |

**结论**：Stop hook 是 IM 同步唯一可行的 hook 选择，但需解决 jsonl 尾部读取的复杂性。这也是 Claude Sessions 插件（方案 3）更优的原因——插件直接解析 jsonl，无需自建 hook 脚本。
