# 子skill 改造指南（subskill-adaptation-guide）

> **作用**：把任何现成 skill 改造为法律MCP路由总skill 的场景子skill 的**通用规范**。适用于两类人：①skill 作者本人（把自研 skill 挂入路由体系）②开源用户（把自己的 skill 挂入本框架）。
> **核心思想**：总skill 管"怎么调MCP"（决策权），现有 skill 管"怎么做事"（业务逻辑）。改造 = 把后者的前者剥离上交。
> 配套：`scenario-map.md`（场景字典，同目录）· `../data/subskills-registry.json`（注册表）· `../subskills/_TEMPLATE-wrapper.md`（壳模式模板）

---

## 一、前置检查（改造成本判断）

改造前先看原 skill 的 MCP 调用方式：

| 原 skill 特征 | 改造模式 | 成本 |
|---|---|---|
| **无任何 MCP 调用硬编码**（纯方法论/规则库，如审核清单类） | ✅ 壳模式（wrapper） | 低（~半小时） |
| 有 MCP 调用，但只在少数环节、工具名集中 | ⚠️ 壳模式可挂，但需在壳中加"参数接管层"声明 | 中 |
| **大量 MCP 调用硬编码**（正文写死具体工具名/参数表，检索是核心流程） | ❌ 壳模式管不住，必须走**融合模式**（fused） | 高（等同新建） |

判断方法：grep 原 skill 全文中的 MCP 工具名（如 `get_case_list`、`faxin_law_search`、`search_case` 等）。命中 0 处 → 壳模式；命中集中在个别段落 → 壳模式+接管层；贯穿全文 → 融合模式。

## 二、三明治改造法（两种模式通用）

### 加头（frontmatter + 衔接协议块）

frontmatter 追加两个字段：

```yaml
subskill_of: legal-mcp-router
L2_id: D2          # 对应 scenario-map.md 的 L2 场景编号；自定义场景用 X 前缀
```

正文**开头**插入衔接协议块（照抄，只改场景名）：

```markdown
> **定位**：内容产出器。总skill 完成 L1/L2 识别后，以子agent 方式启动本skill 执行。
> **执行权/决策权边界**（与总skill 分工，违反即越权）：
> - 本skill（子agent）有：L3复杂度判断、调用方案设计、按批准方案执行、步骤汇报、输出报告草稿
> - 总skill（主agent）有：方案审核/批准、纠错/换MCP/升级决策、输出审核、打卡、对账
> **衔接协议（5步）**：①方案设计（工具×参数×预估次数+预算）提交审核 → ②批准后执行，每次MCP调用后立即写 ../../scripts/log_usage.py → ③环节完成即步骤汇报（工具/结果概要/累计消耗/空结果） → ④遇问题立即上报（错误类型+现场），不自行重试 → ⑤输出草稿提交三维度审核（来源清晰/可追溯/已校验），补正≤2次
> **禁止**：自行决定换MCP/升级/改预算；未经批准调用收费项；编造"该法条不存在"（空结果≠无数据，须上报）。
```

### 换腹（MCP 调用层上交）

正文中所有"调XX工具传XX参"的具体指令，替换为一行引用：

```markdown
> 工具参数按 `../../references/parameter-cards/fN-*.md` 执行（功能N速查卡）；
> 可用 MCP 与预算按 `../../data/user-profile.json` 执行。
```

**路径硬约定（所有子skill 统一）**：子skill 目录深度固定 2 层（`subskills/<name>/SKILL.md`），引用总skill 资产一律用 `../../` 前缀——`../../references/`（速查卡/坑位/升级表/字典）与 `../../scripts/`（日志脚本）。禁止各自发明相对路径。

删除原 skill 自维护的参数表/数据源对比表（会过时，且与总skill 速查卡冲突时以速查卡为准）。

### 留核（业务逻辑文件级保留）

**文件级定义**：留核 = 原 skill 的 `references/`、`scripts/`、`evals/` **全量随迁**到子 skill 目录，非 MCP 调用内容**逐字保留**（字节一致）。以下类型内容是原 skill 的真正价值，原样保留：
- L3 复杂度分层 / 模式选择（Quick/Full）
- 审核维度、检查清单、风险分级方法论
- 输出模板、报告结构
- 领域知识（法规体系、行业规则）

⚠️ **词数声明（防压缩偏差）**：子 skill 词数**不与总 skill 的 <5k 词渐进披露约束挂钩**——子 skill 由子 agent 物理隔离加载，其内容不进入主 agent 上下文。子 skill 可以（且应该）按"优秀 skill 结构"组织：SKILL.md 作索引 + references/ 按需加载。**禁止为省词数把方法论压缩进单文件**（2026-08-22 修复的历史偏差：A2 融合改造曾把原 skill 3 个 references + scripts 压缩丢掉，当时"以 F1 为模板"复制了压缩形态）。

## 三、两种模式

### 壳模式（wrapper）——原 skill 不动，加一个 ~50 行薄壳

适用：原 skill 无 MCP 硬编码（纯方法论），或改造成本高想先挂上再说。

做法：复制 `../subskills/_TEMPLATE-wrapper.md`，替换 3 个占位符（L2_id / source_skill 路径 / 功能组合），存为 `subskills/legal-scene-<L2>-<slug>/SKILL.md`。原 skill 文件**不动**。

⚠️ 壳模式的固有局限：原 skill 内部若有 MCP 调用，这些调用**不受总skill 方案审核/预算管控**（壳只能"建议"其按速查卡执行）。原 skill 硬编码越多，管控漏洞越大——这就是前置检查表第三行要求改融合模式的原因。

### 融合模式（fused）——程序化五步法（2026-08-22 重写，取代旧"按 F1 模板重写"）

适用：检索是原 skill 核心流程、MCP 调用贯穿全文。

**五步法**（不再依赖任何实体 skill 作范本；原"以 F1 为模板"做法已废弃——F1 本身是压缩形态的历史产物，作范本会复制压缩偏差）：

**第 1 步·整体拷贝**：原 skill 全目录（SKILL.md + `references/` + `scripts/` + `evals/` 若有）拷贝到 `subskills/legal-scene-<L2>-<slug>/`。原 skill 的所有资产文件**全量随迁**，一个不丢。

**第 2 步·加头**：frontmatter 追加 `subskill_of: legal-mcp-router` + `L2_id` 两字段；正文开头插入衔接协议块（照抄第二节模板，只改场景名）。

**第 3 步·换腹（手术式编辑，按内容分类）**：在拷贝件中**仅编辑含 MCP 调用的行**，按内容分三类处理：
| 内容类型 | 判别 | 处理 |
|---|---|---|
| **调用指令**（工具名+参数写死的步骤） | "调 rmfyalk_get_case 传 cpws_al_id"类指令 | **替换**为速查卡功能引用（`../../references/parameter-cards/fN-*.md`） |
| **自维护参数格式表 / 数据源对比表** | 会过时、与总skill 速查卡冲突 | **删除**（速查卡接管） |
| **方法论性数据来源说明**（说明分析依据，非调用指令，如"该因素权重来自法院倾向类案例筛选"） | 说明性提及 | **保留原样**（删了丢方法论价值） |

- 不含 MCP 调用的 references 文件**保持字节一致，一个字不改**
- **scripts/ 特例**：scripts 若含 MCP/HTTP 直调（类比总skill 的 hall_detect.py），同样手术式处理或显式标注"该脚本由子skill 自主管理，不属总skill 管控范围"

**第 4 步·留核验证**：
- `diff -r` 原 skill 目录 vs 子skill 目录——所有差异必须逐一归因为第 3 步的换腹/删除编辑，留痕记录
- `grep` 子skill **全目录**（含 references/）的 **MCP 工具调用名（下划线式，如 `rmfyalk_get_case` / `faxin_case_search`）= 0 处**。**豁免规则**：说明性/溯源性提及（如"免费层法信/FLK 优先"的产品名、"原 rmfyalk_get_case 环节"的溯源注记）允许保留——grep 命中处逐条核验：调用型已换腹、说明型豁免并留痕

**第 5 步·登记 + 真跑**：registry 登记（见第五节）+ **真跑一次**验证工具名与速查卡一致（调用链真实走通）——融合模式最典型故障点是换腹后工具名漂移，只有真跑能暴露。

**原 skill 处置**：保留原位作历史底稿（registry 的 `source_skill` 字段溯源），后续迭代以子skill 为主本——融合=新本体（与壳=引用层不同）。

**历史遗留注记（F1/A2）**：两者为旧规下的压缩形态，**不作为模板**。补救路径分两类：
- **A2 类（有原 skill）**＝references 回迁：按本五步法补做第 1-4 步 + 真跑复验（复用 test-run-20260821 的 A2 用例，Quick 模式免费层）
- **F1 类（原创无源）**＝结构性重组（如确有需要）：把正文方法论按优秀 skill 结构拆 references，非"回迁"
- 补救完成前，新子skill 验收一律以本节五步法为准

## 四、非法律MCP 白名单（cost_level 分级 + 运行时三段判断）

子skill 的调用不止法律 MCP（企查查/网页/文件处理等），处理规则：

| cost_level | 例子 | 规则 |
|---|---|---|
| **free** | 网页阅读、搜索、文件读写 | 子skill **自主调用**，步骤汇报列明即可 |
| **paid** | 企查查、天眼查、智慧芽等计费 MCP | **主agent 审核方案时执行三段判断**（见下） |

**计费非法律MCP 三段判断（运行时，主agent 执行）**：
1. **查领域路由skill**：方案中出现计费非法律MCP 调用时，检查 `data/subskills-registry.json` 的 `redirects` 注册 + 当前宿主可用 skill 列表中是否存在对应领域的路由skill（如"企业MCP路由skill"管企查查/天眼查类）
2. **有 → 整体转交**：该类调用的确认与管控移交该路由skill，子agent 对应环节按其规范执行（本总skill 只做"识别→转交"，不重复建设管控逻辑）
3. **无 → 本skill 通用兜底**：子skill 首次调用前向主agent 报备（工具+预计次数），主agent 按单类**一次性确认**（"本任务企查查约N次，确认？"），确认后同类调用不再逐次打断；实际调用超确认次数 50% 再报备

白名单本身是 profile 可配置项（`autonomous_nonlegal_mcp`，见 `../data/user-profile.json`）。

## 五、注册登记（改造完成后必须做）

在 `../data/subskills-registry.json`（format_version 3，2026-08-27 起；v2/v3 字段定义见该文件 `_meta` 与本节下方）追加一条：

```json
"legal-scene-D2-ad": {
  "L2_id": "D2",
  "name": "广告合规（壳模式挂接）",
  "path": "subskills/legal-scene-D2-ad/SKILL.md",
  "adapter_mode": "wrapper",
  "source_skill": "法律相关skill自研仓库/广告合规审核",
  "autonomous_mcp": [{ "name": "web", "cost_level": "free" }],
  "status": "active",
  "see_provenance": true
}
```

字段说明：
- `adapter_mode`：`wrapper`（壳）| `fused`（融合）
- `source_skill`：原 skill 的路径（本地相对路径或名称，供溯源）
- `autonomous_mcp`：本子skill 会用到的非法律MCP 清单（含 cost_level）
- `see_provenance`（可选，2026-08-27 替代原 `note`）：`true` = 溯源注记全文见本子skill SKILL.md 尾部「变更归档注记」节（registry 不再存长文本 note，控制启动扫描体积）
- `redirects`（可选，顶层键）：跨领域转交注册——如 B1 知产尽调转企业尽调skill、将来"企业MCP路由skill"建成后的注册入口

**新增子skill = 注册表加一行 + 放好文件，零改动总skill。**

> **schema 字段定义详版承接（2026-08-27）**：`data/subskills-registry.json` `_meta.schema_v2_fields/schema_v3_fields/adaptation_guide/lightweight_protocol` 四键已压成一行指针，本文本节即承接的详版真相源；各子skill 原 registry `note` 溯源全文已迁入各子skill SKILL.md 尾部「变更归档注记」节。

**registry v3 字段（2026-08-27 增）**：
- `light_layer`（可选）：子skill 轻量层文件相对路径（如 `layers/f1-1-quick.md`）——非空且判层命中轻量层时，总skill 改走轻量分发协议（`references/lightweight-protocol.md`）。子skill 侧配套要求：SKILL.md frontmatter 加 `light_layer` 字段 + 判层表"加载文件"列指向轻量层文件。缺省=无轻量层，走标准分发。

### 5.1 覆盖约定声明（2026-08-27 立，子skill 与总skill 默认规则不一致时用）

子skill 因业务场景需要，可与总skill **默认路径/规则**不同（如 F1 的"F1.2/F1.3 关键结论≥2源"覆盖 upgrade-table 4.2 确定型"命中即止"）。机制：

1. **显式声明**：子skill 在 SKILL.md 设"覆盖约定声明"节，表格逐条标注：**覆盖对象**（总skill 哪条默认规则）/ **约定内容**（本场景怎么做）/ **理由**——未显式声明的差异视为违规，主agent 有权驳回
2. **方案差异点列出**：子agent 提交调用方案时，须列出方案中与总skill 默认规则的全部差异点（覆盖约定的执行体现）
3. **主agent 放行**：主agent 审核时按"**子skill 覆盖约定优先**"放行，不得以"总skill 没这么写"驳回显式覆盖约定（总skill 分发协议已同步声明）
4. **不可覆盖项（硬约束）**：纪律红线（禁止编造/禁止自行重试/禁止越权/禁止混加单位/禁止AGG/注入红线/路径外工具红线）、预算硬上限、确认白名单——任何覆盖约定不得触碰

## 六、验证清单（每个新子skill 上线前跑一遍）

**通用（两模式）**：
- [ ] frontmatter 含 `subskill_of: legal-mcp-router` + `L2_id`（自定义场景 X 前缀）
- [ ] 衔接协议块在正文开头，5步协议完整
- [ ] 所有总skill 资产引用用 `../../` 前缀，逐一 Read 验证可达
- [ ] registry 已登记，path 真实存在
- [ ] 真跑一次（至少 Quick 模式 + 免费层 MCP），验证分发链路与工具名
- [ ] 有轻量层：registry `light_layer` 字段与子skill 内文件路径一致且真实存在；轻量层文件含转全流程触发条件
- [ ] 有覆盖约定：SKILL.md"覆盖约定声明"节存在且逐条含覆盖对象/约定内容/理由三列；未触碰硬约束（红线/预算上限/确认白名单）

**融合模式专项（第三节五步法对应的验收）**：
- [ ] 原 skill 的 references/scripts/evals 文件**全量随迁**（文件数与原目录一致，逐一核对）
- [ ] `diff -r` 验证：非换腹差异 = 0（或全部差异已逐条归因为换腹/删除编辑并留痕）
- [ ] 全目录（含 references/）无自维护参数表；`grep` MCP 工具调用名（下划线式）= 0 处，命中的说明性提及逐条核验豁免并留痕
- [ ] SKILL.md 未为压缩而删减内容——子skill 无词数上限，词数与总skill <5k 约束不挂钩；如词数显著低于原 skill，必须能解释差异来源
