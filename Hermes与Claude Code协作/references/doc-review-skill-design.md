# 文件审核 Skill 设计共识（2026-06-17 Hermes×CC 辩论产出）

> 来源：Hermes 独立分析 → CC 独立分析（含 Explore agent 读现有 Skill + Web Search 搜公开项目）→ 两轮辩论 R1→R2 → 共识。
> 用途：后续构建 CC 本地文件审核 Skill 的设计基准文档。

## 一、需求背景

用户（中国执业知识产权律师）日常起草大量法律文书，发出前经常遇到"低级错误"未发现：
1. 条款/法条编号不对应
2. 数字计算错误（金额加总、利息计算等）
3. 错别字（同音字、法律术语误用）
4. 用过往文件作模板但旧客户名/日期/金额没有替换或删除

## 二、Phase 1 范围

| 检查项 | Phase 1 | Phase 2+ | 说明 |
|---|---|---|---|
| 模板残留检测（旧客户名/日期/金额未替换） | ✅ | — | 最高频问题 |
| 全文一致性（名称/编号/日期前后一致） | ✅ | — | |
| 金额计算校验（加总、大小写、利息计算） | ✅ | — | |
| 日期时序矛盾 | ✅ | — | IP 诉讼中日期极其敏感 |
| 法条编号**格式**是否正确 | ✅ | — | 如"第XX条第X款"格式规范 |
| 法条编号**内容**是否正确（法律法规库 MCP） | ✅ | — | 优先用国家法律法规库 MCP 校验法条内容 |
| 专利/商标编号**格式**是否正确 | ✅ | — | |
| 当事人名称全文一致 | ✅ | — | |
| 当事人名称与工商登记核验（WebSearch） | ✅ | — | 用网络检索免费核验，不用付费 API（节省 API 消耗） |
| 交叉引用完整性（证据/附件编号） | ✅ | — | 正文说"见附件一"但无附件一 |
| 错别字/法律术语误用 | ✅ | — | |
| 格式规范（案号格式、法院全称） | ✅ | — | |
| 中文标点格式（引号成对、序号统一、括号风格） | ✅ | — | 合并到 M8 格式规范模块 |
| 专利/商标当前法律状态 | — | ✅ | 需 CNIPA API |
| 页码与目录不对应 | — | 不做 | CC 读文本流，无法获取排版页码 |

**Phase 1 边界**：纯文本分析 + 免费外部工具（WebSearch、法律法规库 MCP）。需要付费 API 的放 Phase 2+。法律库 MCP 和 WebSearch 纳入 Phase 1 是用户确认的决策。

## 三、架构设计共识

### 3.1 独立 Skill，不做路由层

各 Skill 独立调用，文字细节审查作为通用前置步骤。未来在合同/广告/制度各 Skill 内部加入"调用校对检查"的步骤即可——这是 **Skill 之间的组合，不是路由**。

用户视角：
- "帮我校对这份起诉状" → 调用文字细节审查 Skill
- "帮我审查这份广告" → 调用广告合规审核 Skill（内部可先跑一轮校对）
- "两步都做" → 用户自己连续调用两个 Skill

**零抽象层，零误判风险。**

### 3.2 不做 Quick Scan / Full Review 模式

律师发文件前都是"能查的都查一遍"，不存在"我只查致命级"的真实需求。SKILL.md 里用配置块控制模块启停，用户注释/取消注释即可。

### 3.3 不做"通过/不通过"判断

只发现并提示，不做合规性定性。不做评分，不做自动修复。

### 3.4 模块化结构

```
SKILL.md（配置块控制模块启停 + 主流程）
├── references/
│   ├── 01-template-residue.md   （M1 模板残留检测）
│   ├── 02-consistency.md         （M2 全文一致性 + WebSearch 企业名称核验）
│   ├── 03-law-reference.md       （M3 法条校验，对接法律法规库 MCP）
│   ├── 04-calculation.md         （M4 金额计算校验）
│   ├── 05-legal-terms.md         （M5 法律术语/错别字）
│   ├── 06-date-logic.md          （M6 日期逻辑矛盾）
│   ├── 07-cross-reference.md    （M7 交叉引用完整性）
│   ├── 08-format-spec.md         （M8 格式规范 + 中文标点格式校对）
│   └── output-guide.md           （输出报告格式指南）
```

### 3.5 输出方式（v3 更新，2026-06-18）

**不再用颜色高亮+批注，改用真正的 Word Track Changes（`<w:ins>/<w:del>`）+ 原生 Comments。**

分层策略（Hermes×CC R1→R2 辩论后共识）：

| 场景 | 方案 | 说明 |
|------|------|------|
| **正常（Word 可用）** | **pywin32 + Word COM** | 原厂 Track Changes + Comments，100% 可靠 |
| **降级（Word 进程异常）** | **docx-revisions** 做 `<w:ins>/<w:del>` | Comments 降级为文档末尾汇总表（跳过 OOXML 四文件联动风险） |

**技术选型分析**：

| 方案 | Track Changes | Comments | 可靠性 | 依赖 Word |
|------|:---:|:---:|:---:|:---:|
| Word COM | 自动处理 | 自动处理 | 高 | 是 |
| docx-revisions | 可行 | 不确定/高风险 | 中 | 否 |

- docx-revisions 的文本替换（`<w:ins>/<w:del>`）够用且不算复杂
- Comments 需要 OOXML 四文件联动（Content_Types + document.xml.rels + comments.xml + commentsExtended.xml），纯 Python 拼装风险高，建议交给 COM
- 降级方案中批注转为文末汇总表，不丢失信息

**执行架构**：4 步流水线

```
Step 1 → Step 2 → Step 3 → Step 4
python-docx  M1-M8    生成     COM/docx-revisions
读取 .docx   规则检查  Issue    写入 Track Changes
                       List     + Comments
```

- Step 1-3：纯 python-docx + Python 规则引擎，零 Word 依赖，轻量快速
- Step 4：单独启动 Word COM 进程批量写入修订标记，启动开销只在最后一轮

### 3.6 执行主体（数据隐私要求，2026-06-18 新增）

**执行主体从 CC → WorkBuddy（本地 Windows Bot）。**

原因：
- 法律文书数据敏感，上传 CC 后台（Anthropic）违反保密要求
- WorkBuddy 运行在用户本机 Windows，数据不离开本地
- WorkBuddy 是 Python 环境，可调用 pywin32 + python-docx + docx-revisions

**技术栈**：
```
python-docx       ← Step 1-3 读取+分析
pywin32           ← Step 4 COM 修订输出（primary）
docx-revisions    ← Step 4 降级输出（fallback）
```

### 3.7 Issue List 数据结构

```python
@dataclass
class Issue:
    location_type: str     # "paragraph" | "table_cell" | "header" | "footer"
    para_index: int         # 段落索引（1-based）
    cell_ref: tuple | None  # (table_idx, row, col) for tables
    start_offset: int       # 在段落/单元格内的字符偏移
    end_offset: int         #
    issue_type: str         # "M1_格式" | "M3_错别字" | ...
    severity: str           # "error" | "warning" | "info"
    action: str             # "replace" | "delete" | "comment_only"
    original_text: str      # 原文（用于 replace 定位确认）
    suggested_text: str     # 建议替换文本（action=replace 时）
    comment_text: str       # 批注内容（所有 action 都有）
```

### 3.8 预期目录结构

```
文书细节校对/
├── checker.py            # 主入口：orchestrate Step1-4
├── rules/                # M1-M8 规则 Python 实现
│   ├── m1_format.py
│   ├── m2_numbering.py
│   └── ...
├── references/           # 规则参考文件（9个，保持 v1 原样）
├── SKILL.md              # v2 Skill 规范
└── requirements.txt      # python-docx, pywin32, docx-revisions
```

WorkBuddy 调用方式：`from checker import Proofreader`（模块化 import），不走 CLI。

## 四、公开参考项目

未找到直接匹配的开源中文法律文书审核工具。参考价值：
- **158 项裁判文书错误清单**（知乎/法院规范）：分类方法论有参考价值，条目不能照搬——法院文书格式要求（合议庭组成、上诉权告知等）不适用于律师文书。从 158 项中筛选与律师文书重叠的类型（30-40%），按律师实务场景重写具体规则。
- **PEAT-LLM4LCR**（GitHub）：多 Agent 合同审查的 CoT 方法论
- **OpenContracts**（Apache 2.0）：合同解析架构
- 讯飞 AI 智能校对：错误分层思路

## 五、关键设计决策记录

| 决策点 | 结论 | 辩论依据 |
|---|---|---|
| 范围 | Phase 1 纯文本+免费API，Phase 2+ 付费API | 用户明确说"当前只做文字细节审查"，付费API消耗大用WebSearch替代 |
| 模式 | 默认全量检查，无 Quick/Full | 律师发文件前全查一遍是常态，模式切换多此一举 |
| 路由 | 不做路由层 | CC 自动定性误判风险高，用户手动选和直接用不同 Skill 没区别 |
| 158项清单 | 参考方法论不照搬条目 | 法院文书 vs 律师文书格式要求不同 |
| 日期矛盾 | Phase 1 纳入，高优先级 | IP 诉讼中日期极其敏感（申请日、公开日、侵权日、时效起算点） |
| 附件引用 | Phase 1 纳入 | 交叉引用完整性的具体场景 |
| 页码 | Phase 1 不做 | CC 读文本流，页码是排版概念 |
| 法条内容校验 | Phase 1 纳入 | 用户确认用法律法规库 MCP，无需等 Phase 2 |
| 当事人核验 | Phase 1 用 WebSearch | 用户要求不用付费API（企查查等），直接网络检索 |
| 中文标点校对 | 合并到 M8 格式规范 | 引号成对/序号统一/括号风格同属格式范畴，没必要单建 M9 |
| 输出方式（v1） | 高亮+批注 .docx | python-docx 不支持 Track Changes；高亮+批注最务实 |
| 输出方式（v2→v3，2026-06-18） | 分层策略：COM 主 + docx-revisions 降级 | 用户要求真 Track Changes；本机有 Word，COM 最可靠；docx-revisions 做降级兜底 |
| 数据隐私 | WorkBuddy 本地执行，数据不上传云端 | 法律文书敏感，不上传 CC 后台 |
| 执行架构 | 4 步流水线：python-docx 读→M1-M8 检查→Issue List→COM 写修订 | Step1-3 轻量纯 Python，Step4 单独 COM 进程 |
| Issue List 结构 | `@dataclass Issue`（含位置/偏移量/操作类型/原文/建议文本/批注） | 精确定位 + 区分 replace/delete/comment_only 三种操作 |
