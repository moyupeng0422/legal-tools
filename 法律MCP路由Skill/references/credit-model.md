# 成本模型规范（credit-model）

> 作用：**成本估算与记账的统一规则**——预算守护模块的计算标准 + `mcp_usage_log.jsonl` 的字段定义。
> 前置依赖：`credit-dictionary.json`（工具→档位映射，本模型的查询源）。
> 下游消费：`scripts/log_usage.py`（写日志）· `scripts/verify_usage.py`（对账）· 主agent预算预检与成本汇总。

---

## 一、成本估算规则

### 1.1 单次调用成本

```
单次成本 = credit-dictionary.json → mcp[tool].tools[tool]
         （未收录工具按 default_cost；免费层=0；
           profile cost_known:false 的知识库外MCP = null，不参与积分统计）
```

| 场景 | 计算 |
|---|---|
| 法信/FLK/RMFYALK 调用 | 0（infinite） |
| 北大法宝 get_law_item_content | 25分（查字典） |
| 北大法宝 search_article | 125分（查字典） |
| 元典 rh_ft_detail | 1分（查字典） |
| 元典 hall_detect（API直调） | 50分（查字典，scripts直调） |
| 威科 search_law | 10次/次（one_time，按"次"计非积分） |

### 1.2 累计成本（按单位分别统计，禁止混加）

> ⚠️ **威科按"次"、北大法宝/元典按"分"、免费层=0——单位不同禁止直接求和**，按 quota_type 分池统计：

```
【积分池】recurring（北大法宝/元典）+ free_trial 消耗
   累计积分 = Σ(每次调用 cost，单位为"分")
   预警与确认阈值：按 1.3 分MCP策略执行（北大法宝≤500分/元典≤50分总量上限，跨池300分预警）

【次数池】one_time（威科）
   剩余次数 = 10 - 已用次数（每次调用 -1）
   警戒：剩余 ≤ 3次 → 停止使用并提示（战略储备）
```

### 1.3 确认阈值（触发用户确认·按MCP分策略）

> ⚠️ **本版已取代早期"单次>20分确认 + 累计>100分预警"规则**（用户2026-08-05定案：不用单一积分阈值，按MCP额度性质分策略）。
> ⚠️ **不用单一积分阈值**，也**不逐次确认**——按MCP的额度性质分策略：
> - **北大法宝/元典**：赠送积分（recurring）——**不做单次确认，做总量上限控制**（125分档工具多，逐次确认会打断类案研判流程）
> - **威科**：一次性稀缺（one_time）——任何调用都须确认

| MCP | 策略 | 细则 |
|---|---|---|
| **北大法宝** | **总量上限控制** | 单次任务内累计 **≤500分**（≈4次125分调用）；超限 → 停下询问用户 |
| **元典** | **总量上限控制** | 单次任务内累计 **≤50分**（≈1次hall_detect 或 10次5分检索）；超限 → 停下询问用户 |
| **威科** | **逐次确认** | any调用都须确认（一次性稀缺10次，战略储备）；剩余≤3次停止使用 |
| **法研** | 无需确认 | free_trial 0分（仅500次额度计数） |
| **免费层** | 无需确认 | 法信/FLK/RMFYALK infinite 0分 |

| 累计预警（跨MCP） | 动作 |
|---|---|
| 北大法宝+元典积分池合计 > 300分 | 中途预警，询问是否继续 |
| 北大法宝单任务 > 500分 / 元典单任务 > 50分 | 强制停止，上报用户决策 |
| 威科剩余 ≤ 3次 | 停止使用并提示（战略储备） |

### 1.4 预算预检流程（主agent执行，打卡表□2→□3）

```
① 子agent设计方案 → 列出"工具×预估次数"
② 主agent逐项查 credit-dictionary.json 估算成本
③ 按 1.3 分策略核对：北大法宝/元典查总量上限；威科逐次确认
④ 批准后进入执行（□3预算预检 → □4收费确认）
```

---

## 二、mcp_usage_log.jsonl 完整 Schema

> 日志文件：`data/mcp_usage_log.jsonl`（每行一个JSON对象，追加写入）。
> 写作者：`scripts/log_usage.py`（每次MCP调用后调用）。

### 2.1 字段定义

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `timestamp` | string | ✅ | 调用时间（ISO 8601+时区） | `2026-08-05T12:30:00+08:00` |
| `task_id` | string | ✅ | 本次检索任务唯一ID（手动记账=会话内自增如 `task-001`；**hook 记账=session_id**，2026-08-28 起） | `task-001` |
| `seq` | int | ✅ | 任务内调用序号（从1递增） | `3` |
| `scene_id` | string | ✅ | L2场景ID（scenario-map）；**hook 记账场景可空串**（scene/function 事后可补） | `A2` |
| `function_id` | string | ✅ | 功能编号（f1-f9） | `f5` |
| `mcp` | string | ✅ | MCP标识（credit-dictionary的key） | `pkulaw` |
| `tool` | string | ✅ | 工具名（MCP实际调用名） | `get_case_list` |
| `params_summary` | string | ✅ | 参数摘要（**脱敏**，不存完整入参/密钥；关键参数名+值） | `title=租赁合同 caseGrade=[指导性案例]` |
| `cost` | number\|null | ✅ | 本次消耗（积分/次/0；威科按"次"；**null=未知成本**——profile cost_known:false 的知识库外MCP，不参与积分对账） | `25` |
| `quota_type` | string | ✅ | 额度池类型：infinite/recurring/free_trial/one_time | `recurring` |
| `result` | string | ✅ | 调用结果：ok/empty/error | `ok` |
| `result_has_content` | bool | ✅ | **返回是否有内容**（区分"ok但空"与"ok有数据"——空结果正是防编造要盯的） | `true` |
| `return_count` | int | ✅ | **本次返回条数**（主agent核查翻页/截断用） | `10` |
| `total_count` | int\|null | 否 | **总命中数**（如北大法宝 get_law_list 的 Total；无此字段的记null） | `237` |
| `error_type` | string\|null | 否 | 错误分类：401/400/timeout/net/其他（result=error时必填；net=连接层失败，flk ConnectError 实证 2026-08-28） | `400` |
| `retry_count` | int | ✅ | 该工具**本次任务内**已重试次数（≤2，止损红线） | `1` |
| `agent` | string | ✅ | 调用主体：`main`（主agent/快答直执行）/ `sub`（子agent）/ `auto-hook`（CC宿主hook自动记账，2026-08-28）/ `backfill`（transcript离线补记） | `sub` |
| `note` | string\|null | 否 | 备注（如升级来源、坑位命中） | `法信失败→升级元典` |

> **不记录完整返回内容**（脱敏：防隐私/超长文本污染日志）——只记"有无内容+条数+总数"元数据，主agent核查足够。

### 2.2 示例行

```json
{"timestamp": "2026-08-05T12:30:00+08:00", "task_id": "task-001", "seq": 3, "scene_id": "A2", "function_id": "f5", "mcp": "pkulaw", "tool": "get_case_list", "params_summary": "title=租赁合同 caseGrade=[指导性案例]", "cost": 25, "quota_type": "recurring", "result": "ok", "result_has_content": true, "return_count": 10, "total_count": 237, "error_type": null, "retry_count": 0, "agent": "sub", "note": null}
```

### 2.3 写入规则

- **每次MCP调用必须写一行**（含失败调用——失败也消耗了额度）
- 重试产生的新调用**同样记新行**，`retry_count` 记录该工具在本任务内的累计重试次数
- **禁止**记录：完整参数、API Key、Cookie、Token（脱敏原则）

### 2.4 写入职责（方案B定案：子agent写、主agent对账）

```
【子agent · 执行时写】               【主agent · 任务结束时审计】
每次调用后立即写一行（seq递增）        verify_usage.py 对账
自己累计消耗 vs 预算上限               usage_log条数 vs traces mcp_tools事件数
超限停下上报主agent                   差异 → 先与子agent核实（漏记/重试/跨任务干扰）
                                     → 补记纠正后复对 → 仍异常才上报用户
```

- **写入者**：子agent（执行权）——通过 `scripts/log_usage.py` 追加写入，每次调用后立即执行
  - 变体①（轻量分发/快答，2026-08-27 起）：**主agent 直执行并记账**（`agent=main`）
  - 变体②（CC宿主装 hook，2026-08-28 起）：记账由 `scripts/hooks/auto_log_hook.py` 旁路履行（`agent=auto-hook`，task_id=session_id），LLM 零参与
- **审计者**：主agent（决策权）——任务结束时对账，不逐条介入（避免通信开销）；**差异先与子agent核实再上报**（避免子agent小疏漏放大成用户事件）
- **预算上限来源**：子agent在□2方案审核时从主agent获得批准方案中的预算上限（北大法宝≤500/元典≤50/威科逐次），执行中自行累计对照

---

## 三、三件套关系图（纪律×记账×对账）

```
                    ┌────────────────────────────────────────┐
                    │           credit-dictionary.json         │
                    │      （工具→档位映射，只读真相源）          │
                    └───────────────────┬────────────────────┘
                                        │ 查档位（估算/记账依据）
                                        ▼
   ┌──────────────┐   写入     ┌────────────────────┐
   │  discipline  │──────────→│  mcp_usage_log.jsonl │
   │  -check.md   │  打卡□5   │  （每次调用一行，     │
   │  （9项打卡）   │  记录     │    含失败调用）       │
   └──────┬───────┘           └─────────┬──────────┘
          │ 门禁：未打卡不调用           │ 对账输入
          │                             ▼
          │                    ┌────────────────────┐
          │                    │  scripts/           │
          │                    │  verify_usage.py    │
          │                    │  （日志 vs traces    │
          │                    │   计数对账）         │
          │                    └─────────┬──────────┘
          │                   差异=异常（偷偷重试/漏记）
          │                             │
          └────── 对账异常 → 打卡□9不通过 → 停止交付查原因

  服务商后台（北大法宝/元典/威科控制台）= 周期人工对账（最准，兜底）
```

**三件套职责**：
| 组件 | 管什么 | 何时 |
|---|---|---|
| discipline-check.md | 纪律门禁（9项） | 每环节 |
| mcp_usage_log.jsonl | 精确记账（逐调用） | 每次调用后 |
| verify_usage.py | 计数对账（日志 vs traces）；CC宿主可 `--from-transcript` 逐调用对账（工具名级，含 `--dedup-hook` 双记检测） | 任务结束 |
| 服务商后台 | 权威对账 | 周期人工 |

> **traces 口径固定（2026-08-27 立）**：CC 宿主的子agent/主agent 直调不入 WorkBuddy traces，对账时此类差异属**预期局限**勿当漏记追查（verify_usage.py 输出尾部同步提示）；服务商后台=绝对真相兜底。

---

## 四、与升级表/坑位的衔接

- **成本优先策略**：预算预检时按 upgrade-table 升级路径评估——确定型（找到即止）只算首选工具成本；分析型（多源互补）估算免费层全用+额度层至少1个的成本
- **坑位命中即成本异常**：调用命中 pitfall-checklist 任一坑位 → 该次成本计入但标记 `note="坑位命中"`，并在打卡表□6上报
