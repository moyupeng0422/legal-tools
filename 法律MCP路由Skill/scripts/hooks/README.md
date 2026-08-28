# scripts/hooks/ — MCP 调用自动记账（宿主增强层）

> **首行声明：本目录是可选增强，非协议必需。** 未安装时 skill 完整可用（手动记账流程）；
> 安装后记账由机制履行，LLM 零参与。

## 多宿主适用性

| 宿主 | hook 支持 | 记账方式 |
|------|-----------|---------|
| **Claude Code** | ✅（PostToolUse） | 安装本目录 hook → 全自动；或手动 CLI |
| **Codex** | ✅（PostToolUse，2026-08-28 适配） | 安装 [hooks-codex-example.json](hooks-codex-example.json) → 全自动；或 `backfill_from_transcript.py` 离线补记 |
| **WorkBuddy** | ❌ 无 hooks 机制 | 手动 CLI（`scripts/log_usage.py`），协议不变 |

> 本目录脚本为纯 Python（无第三方依赖），任何支持等价"工具调用后回调"机制的宿主可复用。
> 两宿主 hook stdin 的 JSON 字段同构（`tool_name / tool_input / tool_response / session_id`），
> 同一脚本通用；账本条目 note 带 `host=cc|codex` 标记供审计。

## 安装（Claude Code，三步）

1. **拷配置**：把 [hooks-settings.example.json](hooks-settings.example.json) 的 `hooks` 段并入 `~/.claude/settings.json`（已有 PostToolUse 配置时并列追加，matcher 合并无冲突）；
2. **替换路径**：把 `<SKILL_DIR>` 改为本 skill 实际安装路径（正斜杠）；
3. **验证**：任意会话跑一次法律 MCP 调用（如 `rmfyalk_check_token`），查 `data/mcp_usage_log.jsonl` 末尾出现 `"agent":"auto-hook"` 条目即成功。

**卸载**：删除 settings.json 中该段即回到手动模式；skill 协议零依赖本 hook。

## 安装（Codex，三步）

1. **拷配置**：把 [hooks-codex-example.json](hooks-codex-example.json) 的 `hooks` 段并入 `~/.codex/hooks.json`（或项目级 `.codex/hooks.json`——项目级仅在该项目受信任后加载）；
2. **替换路径**：把 `<SKILL_DIR>` 改为本 skill 实际安装路径（正斜杠）；
3. **审核信任（⚠️ Codex 特有步骤）**：在 Codex CLI 内运行 `/hooks`，对本 hook **审核并信任**——非托管 hook 按定义 hash 记信任，**未信任的 hook 会被静默跳过**（启动时 Codex 会打印"需审核"提醒）。hook 定义任何改动（含路径替换后）都会重新标记为待审核。

**验证**：同上，账本末尾应出现 `"agent":"auto-hook"` 且 note 含 `host=codex` 的条目。
**卸载**：删除该段或 `/hooks` 禁用即回到手动模式。

> ⚠️ **审批策略（2026-08-28 真跑实测）**：非交互 `codex exec` 的默认审批策略可能为 `never`——
> MCP 调用在执行前即被拦截（"MCP tool call requires approval, but approval policy is never"），
> hook 根本收不到事件。正式使用请用交互式会话并允许 MCP 审批；自动化测试可用
> `--dangerously-bypass-hook-trust` 跳过信任审核（仅限已自行审核过的配置）。
> 模板顶层说明字段必须是 `description`（`_readme` 会被 Codex schema 拒绝解析，2026-08-28 实测）。
>
> 可选：给 handler 加 `"async": true` 可后台记账（零等待），但会话结束时未完成的 async hook
> 会被取消——有丢最后几条账的风险，默认同步更稳（记账耗时 <1s）。

## 工作原理

- 宿主每次 MCP 工具调用后向 hook stdin 注入 `tool_name / tool_input / tool_response / session_id`——
  脚本纯旁路解析落账，**LLM 全程无感知、不占模型往返**；
- **任务边界 = session_id**（一个会话天然一个 task_id），无任何 LLM 维护的状态文件——
  检索中途降级/升级换 MCP 完全不影响记账；
- 只记 `credit-dictionary.json → server_alias` 映射内的 7 个法律 MCP；未映射（企查查/天眼查等）静默跳过；
- 档位由脚本三形态查表（禁凭记忆），quota_type 从 `data/user-profile.json` 的 tier 映射；
  profile 标 `cost_known: false` 的知识库外 MCP → 记 `cost=null`+note（不查表不掉 default 档，
  不参与 `verify_usage` 积分对账，2026-08-28 立）；
- **永远 exit 0**：记账失败不阻塞主流程，异常写 stderr。

## 装了 hook 之后（LLM 侧约定）

- **免手动执行 log_usage**（手动+自动会双记；`verify_usage --dedup-hook` 可兜底去重）；
- 任务结束仍需对账：`python scripts/verify_usage.py --task-id <session_id> --from-transcript <留痕路径>`；
- `scene_id / function_id` 留空，可在任务结束对账时按需后补。

## 离线补记（两宿主通用）

```bash
# CC transcript / Codex rollout 自动探测，可传多个文件（主会话 + 子 agent）
python scripts/hooks/backfill_from_transcript.py --session <留痕.jsonl> [--dry-run]
# Codex 子 agent 是独立 rollout 文件（~/.codex/sessions/YYYY/MM/DD/ 下），与主文件并列传入即可
```

幂等可重跑（同工具+调用时刻匹配即跳过）；`--dry-run` 只预览。

## 文件清单

| 文件 | 用途 |
|---|---|
| `auto_log_hook.py` | PostToolUse hook 主脚本（实时旁路记账，CC/Codex 双宿主） |
| `backfill_from_transcript.py` | 离线补记：从会话留痕提取 MCP 调用补账（幂等，可重跑；格式自动探测） |
| `hooks-settings.example.json` | Claude Code settings.json 配置模板（`<SKILL_DIR>` 占位符） |
| `hooks-codex-example.json` | Codex hooks.json 配置模板（`<SKILL_DIR>` 占位符 + `/hooks` 信任说明） |
| `README.md` | 本文件 |

> 解析逻辑共享模块：`../transcript_parsers.py`（CC transcript / Codex rollout 自动探测，
> 补记与 `verify_usage --from-transcript` 对账共用）。

## 局限（诚实声明）

- 未映射 server 的调用不入账（`--from-transcript` 对账 diff 会暴露"有调用无记账"，人工裁决）；
- hook 的响应解析尽力而为（isError/内容非空可靠，返回条数部分 server 取不到）；
- 多会话并发天然支持（按 session_id 隔离），无单文件状态；
- WorkBuddy 宿主的调用不经过本 hook 覆盖范围（用 traces 对账，见 verify_usage.py）；
- **Codex code mode 形态待实证**：部分 Codex 版本经 code mode（JS 脚本）包装 MCP 调用，
  PostToolUse 对嵌套调用的 stdin 字段形态需以探针实测为准（C0 用例）；即使该形态不触发，
  `backfill_from_transcript.py` 的 rollout 兜底解析（含 code mode 层正则抽取）仍可补账。
  **2026-08-28 真跑状态**：配置解析 ✅（description 修正后）/ C2 rollout 补记 ✅（3 条提取+
  error 判定+幂等）/ C3 对账 ✅（3=3）/ C0 stdin 字段与 C1 实时记账 ⏳ 待复测
  （首轮被宿主审批策略阻断——按上方审批策略警示调整会话模式后复测）。
