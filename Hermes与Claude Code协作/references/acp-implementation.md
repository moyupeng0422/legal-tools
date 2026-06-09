# ACP 客户端实现细节（2026-06-02 集成测试通过）

> 补充 `references/acp-research.md` 中 P1-P3 实施阶段的具体发现和修正。

## P1 集成测试修正全记录

### 错误 1：环境变量名 `ANTHROPIC_API_KEY` vs `ANTHROPIC_AUTH_TOKEN`

- **CC 写了**：`set ANTHROPIC_API_KEY=...`
- **正确**：`set ANTHROPIC_AUTH_TOKEN=...`
- **症状**：ACP 进程静默失败，prompt 返回空或报 internal error
- **根因**：CC 的 `settings.json` 中字段是 `ANTHROPIC_AUTH_TOKEN`，CC 混淆了两个变量名
- **修正**：`~/.hermes/acp_client/client.py` L118 → `ANTHROPIC_AUTH_TOKEN`

### 错误 2：流式事件解析扁平化

- **CC 假设（错误）**：`{"method": "agent_message_chunk", "params": {"text": "..."}}`
- **实际结构**：`{"method": "session/update", "params": {"update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "..."}}}}`
- **症状**：`result.text` 始终为空字符串
- **修正**：`~/.hermes/acp_client/session.py` L124-145 → 先匹配 `method == "session/update"`，再取 `params.update.sessionUpdate`

### 错误 3：cwd 平台路径

- **CC 写了**：`cwd="/home/<云端用户>"`（Linux 路径）
- **症状**：`[-32603] Internal error`
- **根因**：ACP 进程运行在 Windows 上，不接受 Linux 文件路径
- **修正**：默认值改为 `cwd="C:\\"`，接受 Windows 路径

### 错误 4：mode 参数

- **CC 写了**：`params["mode"] = mode` 传给 `session/new`
- **症状**：`[-32602] Invalid params`
- **根因**：`session/new` 不接受 `mode` 参数（模式由 agent 侧 settings 控制）
- **修正**：从 `ACPSession.create()` 参数中移除 `mode` 字段，保留 `mcpServers: []`

### 错误 5：send() 遇推送行误读

- **症状**：`session/new` 偶尔返回 `session/update` 推送而非会话 ID
- **根因**：ACP 在创建会话后会立即推送 `session/update`（如 `available_commands_update`），`send()` 只读一行，可能读到推送消息（无 `id` 字段）
- **修正**：`~/.hermes/acp_client/client.py` → `send()` 循环跳过无 `id` 行，直到找到匹配 `request_id` 的响应

## P2 路由策略

### 路由优先级

1. **P0: 用户显式指定**（"走cc"/"用acp"/"你直接回答"）
2. **P1: 需要本地资源**（文件→CC，命令→CC，MCP→CC）
3. **P2: 纯推理** → ACP（含法律术语/长问题/分析类动词）或 SELF（日常问答）

### 降级链

- ACP 故障 → 降级 SELF + 告知用户
- CC 故障 → 直接告知用户（不静默回退）
- SELF 故障 → 升级 ACP（不告知）

## P3 编排模板

三个已实现的编排模板：

| 模板 | 流程 | 适用场景 |
|------|------|---------|
| `query_and_analyze` | CC 查数据 → ACP 分析 | 企查查查询 + 法律风险分析 |
| `analyze_and_write` | ACP 分析 → CC 写文件 | 法律分析 + 文档生成 |
| `read_and_advise` | CC 读文件 → ACP 给建议 | 审查合同 + 合规建议 |

### 模板匹配

通过关键词正则匹配自动选择模板：
- `查询.*分析` / `检索.*评估` → `query_and_analyze`
- `分析.*写入` / `生成.*保存` → `analyze_and_write`
- `读取.*建议` / `审查.*咨询` → `read_and_advise`

## 集成测试结果

```python
from acp_client import ACPClient, ACPSession

client = ACPClient(api_key="...")
client.connect()
session = ACPSession.create(client)
result = session.prompt("用一句话介绍中国专利法的基本框架")
# result.text = "中国专利法以《专利法》为核心..."
# result.stop_reason = "end_turn"
# result.usage.cost = 0.2687  # USD
```

全链路耗时 ~8 秒，费用 $0.27/次（含 53095 input tokens + 129 output tokens）。

## 必须注入的完整环境变量

通过 SSH 远程命令注入（cmd.exe `set` 语法）：

```
set ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
set ANTHROPIC_AUTH_TOKEN=<key>
set ANTHROPIC_MODEL=glm-5-turbo
set ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5-turbo
```

> ⚠️ 注意名称：是 `ANTHROPIC_AUTH_TOKEN`，不是 `ANTHROPIC_API_KEY`
> ⚠️ 注意端点：是 `/api/anthropic`，不是 `/api/paas/v4/anthropic`（后者是 OpenAI + Anthropic 协议的混血，不存在）
