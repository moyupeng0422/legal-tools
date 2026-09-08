---
name: doc-proofreading
description: 法律文书细节校对技能（v2）。对法律文书进行四步检查：python-docx 读取 → M1-M8 模块规则检查 → 本地 LLM 语义检查 → 写入 Track Changes + Comments（COM/OOXML 双路径）。适用场景：(1) 用户提交法律文书（起诉状、律师函、合同、代理词等）要求校对时；(2) 用户提到"校对""检查细节""有没有低级错误""有没有错别字""文书审校"等关键词时；(3) 用户要求检查文书中的模板残留、金额计算、法条引用、日期逻辑等问题时；(4) 用户要求对文书进行 Track Changes 修订或批注标记时。
---

# 文书细节校对 v2

对法律文书进行四步细节检查，最终输出带 Track Changes + Comments 的 .docx 文件。

## 架构概览

```
输入 .docx 文件路径
    │
    ▼
[Step 1] DocReader — python-docx 纯 Python 读取
    │  提取段落/表格/页眉页脚文本 + 位置映射
    │  零 Word 依赖
    ▼
[Step 2] M3/M4/M6/M8 机械检查 — 纯 Python
    │  • M3 法条格式（编号、全称）
    │  • M4 金额计算（加总、大小写）
    │  • M6 日期逻辑（先后关系）
    │  • M8 格式规范（案号、序号）
    │  输出 List[Issue]（机械确定性问题）
    ▼
[Step 3] M1/M2/M5/M7 语义审查 — AI Agent
    │  WorkBuddy AI agent 读取文档 + references/ 规则参考文件
    │  • M1 模板残留（异常检测）
    │  • M2 全文一致性（实体变体、企业名称核验）
    │  • M5 法律术语/错别字（上下文判断）
    │  • M7 交叉引用（引用链完整性）
    │  输出宽松 JSON（search 串 + issue_type + severity + action + 建议文本 + 批注），
    │  无需手算 para_index / offset
    ▼
[Step 3.5] locate_issues.py — 脚本定位（AI 出判断、脚本管定位）
    │  在未 strip 段落/单元格文本中精确查找 search 串，
    │  生成 para_index / start_offset / end_offset（与 OOXML Writer 坐标系一致）
    │  未命中/歧义 → 定位报告人工消歧；全命中才输出 ai_issues.json
    ▼
[Step 4] 写入 Track Changes + Comments（--mode 三选一）
    │  合并机械 + 语义 Issue List
    │  ├─ com   → COMWriter（pywin32 + Word COM，需 Word）
    │  ├─ ooxml → OOXMLWriter（纯 Python lxml，词级修订 + 原生批注，跨平台）
    │  └─ auto  → OOXML → COM → FallbackWriter 三级降级（默认，2026-09-07 倒置）
    ▼
输出带修订标记的 .docx 文件（Word 可直接 Accept/Reject + 查看批注）
```

## Issue 数据结构

所有检查模块统一输出 `Issue` 对象：

```python
@dataclass
class Issue:
    location_type: str      # "paragraph" | "table_cell" | "header" | "footer"
    para_index: int          # 段落索引（1-based，Word Paragraphs 集合）
    cell_ref: tuple | None   # (table_idx, row, col) 仅表格单元格
    start_offset: int        # 段落/单元格内字符偏移（0-based）
    end_offset: int          # 段落/单元格内字符结束偏移
    issue_type: str          # "M1_模板残留" | "M2_一致性" | ...
    severity: str            # "致命" | "严重" | "一般"
    action: str              # "replace" | "delete" | "comment_only"
    original_text: str       # 原文（用于 COM 定位确认）
    suggested_text: str      # 建议替换文本（action=replace/delete 时有值）
    comment_text: str        # 批注内容（所有 action 都有）
```

### action 与输出行为

| action | Track Changes | Comment |
|--------|:---:|:---:|
| `replace` | 删除原文 → 插入建议文本 | 批注说明原因 |
| `delete` | 删除原文 | 批注说明原因 |
| `comment_only` | 无修订 | 仅添加批注（用于需人工判断的问题） |

### severity 与批注颜色

| severity | Comment 标记前缀 |
|----------|----------------|
| 致命 | `🔴 致命` |
| 严重 | `🟡 严重` |
| 一般 | `🟢 一般` |

### 批注格式规范（醒目清楚，完整不截断）

所有 Writer 共用 `format_comment()` 生成结构化批注（OOXML 渲染为真实多段落 `<w:p>` + 标题上色加粗，COM 用 `\r` 分段 + 首段上色加粗）：

```
● 致命 · 术语                      ← 标题行（红色加粗）：彩色● + severity + 中文类型
定金/订金法律后果不同：定金适用定金罚则…  ← 正文段（按 \n 拆分，完整不截断）
→ 建议改为：订金                     ← 末段（仅 action=replace 且建议非空时附）
```

设计目标：
- **标题行醒目**：彩色 `●`（基础字符 U+25CF，继承标题色）+ 严重度 + **中文类型**（`issue_type_label()` 取下划线后中文，如 `M5_术语`→`术语`，不显示 M 编码），按 severity **上色加粗**
- **不用彩色 emoji**：🔴🟡🟢 中 🟡🟢 是 Emoji 12.0 新增，需彩色 emoji 字体；给 run 设显式 `font.color` 后 Word 不再走彩色 emoji 回退，🟡🟢 在普通字体（宋体）里无字形会丢失。改用 `●` 继承颜色，跨字体/跨 Office 版本稳定
- **标题配色**：致命=红 `FF0000` / 严重=橙 `FF8000` / 一般=蓝 `4472C4`（信息性、不刺眼）
- **正文完整**：**不截断**（截断会丢信息），靠模块/AI 用词简洁控制篇幅
- **引号归一化**：`normalize_cn_quotes()` 在渲染前把各类引号统一为中文全角双弯引号 `“”`（成对）：ASCII 直引号 `"`/`'`、弯单引号 `‘’` 一律收敛为 `“”`（2026-09-07 扩展，规范 1.3 要求中文引号一律 `“”`），AI/模块误写也能兜底
- **建议行**：replace 类问题完整附"→ 建议改为：…"

## 审查原则

1. **只报确定性问题**：置信度不足的问题不输出，宁可漏报不误报
2. **定位精确**：每个 Issue 必须包含可定位到文档的具体位置（para_index + offset）
3. **给出修改建议**：每个 Issue 的 comment_text 必须附上可操作的建议
4. **不做内容判断**：不评价论点是否成立、策略是否合理，只检查机械性错误
5. **零幻觉**：不编造法律条文内容、企业信息等外部事实，必须通过 MCP 实际查询

## 配置

### 启用模块

默认全部启用，按需禁用：

```python
enabled_modules = [
    "M1",  # 模板残留检测
    "M2",  # 全文一致性（含企业名称核验）
    "M3",  # 法条校验（需法律法规库 MCP）
    "M4",  # 金额计算校验
    "M5",  # 法律术语/错别字
    "M6",  # 日期逻辑矛盾
    "M7",  # 交叉引用完整性
    "M8",  # 格式规范
]
```

### 输出配置

```python
config = {
    "output_path": None,        # None = 原文件名_校对.docx
    "write_mode": "auto",       # "com" | "ooxml" | "auto"（auto = ooxml→com→fallback 三级降级，2026-09-07 倒置）
    "comment_author": "文书校对助手",
    "include_module_summary": True,  # 在文档末尾添加模块摘要表
}
```

## Step 1: DocReader（python-docx）

使用 `python-docx` 读取 .docx，提取结构化文本并建立位置映射。

### 提取范围

| 区域 | 位置映射 | 提取方式 |
|------|---------|---------|
| 正文段落 | `location_type="paragraph"`, `para_index=N` | `doc.paragraphs` |
| 表格单元格 | `location_type="table_cell"`, `cell_ref=(t, r, c)` | `doc.tables[t].rows[r].cells[c]` |
| 页眉 | `location_type="header"`, `para_index=N` | `section.header.paragraphs` |
| 页脚 | `location_type="footer"`, `para_index=N` | `section.footer.paragraphs` |

> **页眉/页脚写入能力差异（2026-09-07 三文书实测确认）**：**修订支持** header/footer
> （OOXML 词级修订正常写入 `word/headerN.xml` / `footerN.xml`）；**批注跳过** header/footer（Writer 限制）。
> 页眉页脚类问题请用 replace/delete 修订而非 comment_only。

### 输出结构

```python
@dataclass
class DocContent:
    paragraphs: list[dict]   # [{text, index, style}]
    tables: list[dict]      # [{cells: [{text, row, col}], table_idx}]
    headers: list[dict]      # [{text, index, section_idx}]
    footers: list[dict]      # [{text, index, section_idx}]
    entity_index: dict       # 实体 → 出现位置列表
```

### 实体提取

从全文中提取以下实体，构建结构化索引：

| 实体类型 | 提取内容 | 示例 |
|---------|---------|------|
| 当事人名称 | 原告/被告/甲方/乙方等全称 | "深圳市腾讯计算机系统有限公司" |
| 案号/编号 | 案号、申请号、专利号 | "（2025）浙01民初123号" |
| 日期 | 所有日期表述（含大写） | "2024年3月15日" |
| 金额 | 所有金额数字（含大小写） | "50000元"、"伍万元整" |
| 法条引用 | 法律名称 + 条文号 | "《专利法》第六十五条第一款" |
| 证据/附件 | 证据编号、附件引用 | "证据一"、"附件一" |
| 法院名称 | 受理法院、管辖法院 | "杭州市中级人民法院" |

## Step 2: 机械检查（M3/M4/M6/M8）

以下 4 个模块为纯 Python 正则/计算可确定的问题，由 `MechanicalChecker` 自动执行。

### M3: 法条格式校验

读取 [references/03-law-articles.md](references/03-law-articles.md)。

检测：
- 首次引用法律时是否使用完整名称（如《中华人民共和国专利法》而非《专利法》）
- 条文编号是否使用中文数字（如"第十五条"而非"第15条"）

输出 action：`replace`（格式修正）

> 注意：法条内容正确性校验（3b）需法律法规库 MCP，由 AI Agent 在 Step 3 中调用。

### M4: 金额计算校验

读取 [references/04-amount-calculation.md](references/04-amount-calculation.md)。

检测（纯 Python 计算）：
- 分项加总 = 合计
- 大写金额 ↔ 小写金额（精确数值转换）
- 金额单位一致性

输出 action：`replace`（修正计算错误）

### M6: 日期逻辑矛盾

读取 [references/06-date-logic.md](references/06-date-logic.md)。

从实体索引提取所有日期，检查逻辑关系：
- 合同签订日 ≤ 履行期限起算日
- 侵权行为日 ≤ 起诉日
- 各阶段日期的先后顺序

输出 action：`comment_only`（日期矛盾需人工核实原始事实）

### M8: 格式规范

读取 [references/08-format-spec.md](references/08-format-spec.md)。

检查：
- 案号格式规范
- 法院名称使用完整称谓
- 序号连续性
- 称谓前后一致

输出 action：`replace`（格式修正）

---

## Step 3: AI Agent 语义审查（M1/M2/M5/M7）

以下 4 个模块需要语义理解，由 **WorkBuddy AI Agent 直接阅读文档并对照规则执行**。

### 为什么不能正则化

| 模块 | 检查内容 | 为什么必须 AI |
|------|---------|-------------|
| M1 模板残留 | 旧当事人名、旧日期、上下文异常 | 需理解"什么算异常"——旧名称可能藏在非结构位置 |
| M2 全文一致性 | 同实体变体识别、"华为"是不是"华为技术有限公司" | 需判断简称合法性与上下文关联 |
| M5 法律术语/错别字 | 定金/订金、法人/法定代表人 | 需判断具体语境中的正确用法 |
| M7 交叉引用 | 引用链断裂、条款内容是否匹配引用 | 需阅读被引用段落，判断内容一致性 |

### AI Agent 执行流程

**准备阶段**：
1. 运行 `python checker.py <文件> --mechanical-only --export-json mech.json` 获取机械检查结果作为参考（该模式默认不写文件）；AI 审查完成后正式执行时加 `--mech-json mech.json` 复用机械结果，避免二次机械检查
2. 读取以下参考文件，理解每类问题的判断标准：
   - `references/01-template-residue.md`
   - `references/02-consistency.md`
   - `references/05-legal-terms.md`
   - `references/07-cross-reference.md`
3. **必读 [feedback/LESSONS.md](feedback/LESSONS.md)**——历史实战沉淀的校对经验（一句话规则），审查时逐条对照，重点防范曾漏检的问题类型

**审查阶段**（按模块顺序）：

#### M1: 模板残留检测

逐段阅读文档，检测以下异常：
1. **占位符残留**：`___年___月___日`、`[请填写]`、`{{变量名}}` 等未替换的模板占位符
2. **旧当事人名称残留**：与文档首部声明的当事人不一致的其他名称
3. **旧日期/编号残留**：与文档核心时间线不符的日期（如去年的日期）
4. **上下文语义异常**：段落内容与前后文逻辑冲突

对每个发现，构造宽松 JSON 条目：
- `issue_type`: `"M1_模板残留"`
- `action`: 确认可替换用 `"replace"`，需人工判断用 `"comment_only"`
- `search`: 问题文本从原文**逐字拷贝**（定位由 locate_issues.py 完成，无需手算 offset）

#### M2: 全文一致性

1. **M2-2a 文内一致性**：
   - 提取文档中出现的所有当事人名称/机构名称/编号
   - 逐一比对：同一实体每次出现的写法是否完全一致
   - 判断变体是否合法简称（如附件中有"以下简称X"的声明）

2. **M2-2b 企业名称核验**（可选，需企查查/天眼查 MCP）：
   - 对乙方（服务提供方）的全称，调用 MCP 查询工商登记名称
   - 比对文档中使用的名称与工商登记名称
   - 对甲方名称同样验证

Issue 格式：
- `issue_type`: `"M2_一致性"`
- `action`: 确认错误用 `"replace"`（建议文本为正确名称），简称合法性需确认用 `"comment_only"`
- `search`: 问题名称写法从原文逐字拷贝；同段多个写法需分别出条目

#### M5: 法律术语/错别字

1. **易混法律术语**：扫描以下术语并判断语境正确性
   - 定金 vs 订金
   - 法人 vs 法定代表人
   - 抵押 vs 质押
   - 专利权人 vs 专利申请人
   - 执行异议 vs 执行异议之诉

2. **同音/形近错别字**：
   - 赔偿 vs 赔尝、委托 vs 委拖、记录 vs 纪录
   - 在 vs 再、的 vs 地 vs 得

3. **语病检测**：
   - 主谓搭配不当
   - 指代不清（如"其""该"指代不明）
   - 句式杂糅

Issue 格式：
- `issue_type`: `"M5_术语"` 或 `"M5_错别字"` 或 `"M5_语病"`
- `action`: 确认错误用 `"replace"`（建议文本为正确用语），需人工判断用 `"comment_only"`
- `search`: 错误用词从原文逐字拷贝（如 `"委拖"`，勿带多余空格/标点）

#### M7: 交叉引用完整性

1. 扫描所有引用标记（"证据X""附件X""详见第X条""根据第X.X条"）
2. 逐一验证被引用对象是否存在：
   - "证据一" → 全文搜索是否存在定义"证据一"的段落
   - "附件一" → 全文搜索是否存在附件清单
   - "第X.X条" → 全文搜索是否存在该条款编号

Issue 格式：
- `issue_type`: `"M7_引用"` 或 `"M7_孤儿引用"`
- `action`: `"comment_only"`（引用问题始终需人工确认）
- `search`: 引用标记从原文逐字拷贝；同一引用多处出现时用 `occurrence` 或 `context_after` 消歧

### 输出格式（宽松 JSON，2026-09-07 起定位由脚本完成）

AI Agent 完成语义审查后，**只产出宽松 JSON**（`loose_issues.json`），每条仅需 6 个必填字段，
**不需要也不允许手算 `para_index` / `start_offset` / `end_offset`**：

```json
[
  {
    "search": "自___年___月___日起至___年___月___日止",
    "issue_type": "M1_模板残留",
    "severity": "致命",
    "action": "comment_only",
    "suggested_text": "",
    "comment_text": "服务期限起止日期为空白占位符，起诉前必须核实补齐实际约定日期"
  }
]
```

可选消歧字段：

| 字段 | 说明 |
|------|------|
| `occurrence` | `search` 命中多处时取第 N 处（1-based，按文档顺序） |
| `scope` | 限定搜索域：`paragraph` / `table_cell` / `header` / `footer` |
| `context_before` / `context_after` | 上下文锚：命中处前方须以此结尾 / 后方须以此开头 |

然后运行定位脚本：

```bash
python locate_issues.py "文书.docx" loose_issues.json -o ai_issues.json --report locate_report.md
```

**脚本行为约定**：
- 消歧优先级：context 锚先过滤 → 过滤后唯一即 OK → 仍多值再看 `occurrence` → 两者冲突以 context 为准并警告
- **同一搜索串需要 N 条 Issue（原文出现 N 处）时，必须逐条给 `occurrence`（1..N）**；多条条目命中同一位置且 issue_type 相同会被判 **DUPLICATE**（按失败处理，默认不输出）——这通常意味着漏改 occurrence 或复制条目忘改字段；同位置**不同** issue_type 是合法场景，不受影响
- `search` 必须与原文**逐字一致**（空格/全半角/标点差异会 NOT_FOUND；报告会给出近似候选并显式标记不可见字符）
- 非法 `issue_type` / `action` / `severity` 会被拒绝（INVALID），该条目不输出
- 全部条目定位成功才生成 `ai_issues.json`（退出码 0）；有失败只出定位报告（退出码 1），修正后重跑；`--allow-partial` 可兜底写出已命中部分
- AI 必须读报告核查每条命中的"前后 20 字摘录"，确认锚点无误后才进入 Step 4
- 批注正文的引号由脚本自动归一化为 `“”`，AI 直接写即可（但仍建议遵守 1.3 引号规范）

**坐标系说明**（脚本内部行为，排查问题时参考）：脚本重新用 python-docx 打开文档，在**未 strip**
的段落全文上搜索，与 OOXML Writer 的 `doc.paragraphs[para_index-1]` + run 切分严格一致；
表格单元格取 `cell.paragraphs[0]`（offset 相对该段，`para_index=0`）；页眉页脚仅第 1 个 section。

### 合并与写入

AI Agent 完成语义审查后，调用：

```python
from checker import Proofreader

p = Proofreader()
issues = p.check_full("文书.docx", ai_issues_json="ai_issues.json")
p.write_revisions("文书.docx", issues)
```

或通过 CLI：

```bash
python checker.py "文书.docx" --issues-json ai_issues.json -o "文书_校对.docx"
```

## Step 4: 写入 Track Changes + Comments（COM / OOXML 双路径）

> （自我进化机制见下方「自我进化」章节——校对完成后如收到漏检反馈，走进化流程。）

通过 `--mode` 选择写入路径，`auto` 模式三级降级。

### 路径对比

| | COMWriter（com） | OOXMLWriter（ooxml） | FallbackWriter（末位） |
|---|---|---|---|
| 依赖 | Word + pywin32 | 纯 Python（python-docx lxml） | docx-revisions |
| 跨平台 | ❌ 仅 Windows | ✅ 全平台 | ✅ |
| 修订精度 | 段落级（Start/End） | **词级**（跨 run 切分） | 整段替换 |
| 原生批注 | ✅ | ✅（python-docx add_comment） | ❌（降级汇总表） |
| 速度 | 慢（启动 Word 进程） | 快（纯文件 IO） | 快 |

### OOXMLWriter 词级修订原理（推荐）

用 lxml 直接操作段落 XML，把目标文本精确包进 `<w:ins>`/`<w:del>`：

1. **切分 run**：在 `start_offset`/`end_offset` 处切分 run，使目标范围对齐 run 边界（`_split_at` + `_split_run`，deepcopy 保留 `w:rPr` 格式）
2. **原文校验**：covering runs 拼接文本必须等于 `original_text`，否则跳过修订（防偏移错位破坏文档）
3. **批注优先**：先调 `doc.add_comment(covering_runs, ...)` 放置 `commentRangeStart/End`（落在 w:del 外层，避免嵌入导致结构损坏）
4. **Track Changes**：把 covering runs 包进 `<w:del>`（`w:t`→`w:delText`），replace 时在其后插入 `<w:ins>`
5. **倒序处理**：按 `(para_index, start_offset)` 降序，避免前修改致后续偏移
6. **settings.xml**：写入 `<w:trackChanges/>` 保证 Word 可 Accept/Reject

```python
# 词级修订核心（Vaquill 方案）
def _wrap_run_as_deletion(self, run):
    r_el = run._r
    del_el = OxmlElement("w:del")
    del_el.set(qn("w:id"), str(self._next_rev_id()))   # 文档级唯一
    del_el.set(qn("w:author"), self.author)
    del_el.set(qn("w:date"), self._date_iso)            # ISO 8601 UTC + Z
    r_el.addprevious(del_el)
    del_el.append(r_el)
    for t in r_el.findall(qn("w:t")):
        t.tag = qn("w:delText")                         # 删除必须用 delText，否则 Word 静默丢弃
    return del_el
```

**Vaquill 12 条避坑清单**全部落实：删除用 `w:delText`、`w:id` 唯一、ISO 日期带 Z、全用 `qn()`、deepcopy 保留格式、`xml:space=preserve`、倒序应用、批注三锚点、`trackChanges` 设置、不给修订设颜色样式。

### COMWriter 路径

使用 pywin32 调用 Word COM API（段落级 Start/End 定位，`Duplicate` 避免 off-by-one）：

```python
word = win32com.client.Dispatch("Word.Application")
doc = word.Documents.Open(docx_path)
doc.TrackRevisions = True
# 按 para_index 降序遍历，rng.Comments.Add(rng, comment_text_for_com(issue))
```

### 路径选择与降级（`--mode`）

| mode | 行为 |
|------|------|
| `com` | 仅 COMWriter，失败直接抛异常 |
| `ooxml` | 仅 OOXMLWriter，失败直接抛异常 |
| `auto`（默认） | OOXML → COM → FallbackWriter 逐级降级（OOXML 纯 Python 约 0.19s，COM 因 Word 进程启动约 7.6s，故 OOXML 优先；COM 降级保留作兜底与渲染验证） |

降级触发：OOXML 覆盖 runs 文本不匹配 / 文档结构异常 → 降级 COM；`pywin32` 未装 / Word 启动失败 / COM 操作异常 → 降级 Fallback。

### Range 定位辅助

```python
def locate_range(doc, issue):
    """根据 Issue 的 location_type 和位置信息定位 Word Range"""
    if issue.location_type == "paragraph":
        return doc.Paragraphs(issue.para_index).Range
    elif issue.location_type == "table_cell":
        t, r, c = issue.cell_ref
        return doc.Tables(t + 1).Cell(r + 1, c + 1).Range
    elif issue.location_type == "header":
        return doc.Sections(1).Headers(1).Range.Paragraphs(issue.para_index).Range
    elif issue.location_type == "footer":
        return doc.Sections(1).Footers(1).Range.Paragraphs(issue.para_index).Range
```

### 同位置合并

同一 `(location_type, para_index, start_offset)` 的多个 Issue 合并为一次 COM 操作：
- 保留 severity 最高的 action
- 合并所有 comment_text（用分号分隔）

## WorkBuddy 调用接口

### 完整工作流（推荐）

```python
from checker import Proofreader

p = Proofreader()

# Step 1-2: 机械检查
mech_issues = p.check_mechanical("文书.docx")

# Step 3: AI Agent 执行 M1/M2/M5/M7 语义审查（在对话中完成）
# …AI Agent 阅读文档，产出宽松 JSON loose_issues.json（search 串定位，无需手算 offset）…

# Step 3.5: 脚本定位 → ai_issues.json（全命中才输出；失败条目读报告修正后重跑）
#   python locate_issues.py "文书.docx" loose_issues.json -o ai_issues.json --report locate_report.md
ai_issues = p.load_issues_from_json("ai_issues.json")

# Step 4: 合并写入
all_issues = p.check_full("文书.docx", ai_issues=ai_issues)
p.write_revisions("文书.docx", all_issues)
```

### 使用 JSON 中转

```bash
# Step 1: 导出机械检查结果（供 AI Agent 参考）
python checker.py "文书.docx" --mechanical-only --export-json mech.json   # 默认不写文件（2026-09-07 行为变更，加 --write 才生成修订文档）

# Step 2: AI Agent 在对话中读取 mech.json + 文档 → 生成宽松 JSON loose_issues.json（6 字段，search 串定位）

# Step 3: 脚本定位（未命中/歧义只出报告不写文件，退出码 1；AI 修正后重跑）
python locate_issues.py "文书.docx" loose_issues.json -o ai_issues.json --report locate_report.md

# Step 4: 合并写入
python checker.py "文书.docx" --issues-json ai_issues.json -o "文书_校对.docx"
```

### 纯机械检查（无 AI 语义）

```bash
python checker.py "文书.docx" --mechanical-only -o "文书_校对.docx"
```

### 指定写入路径（--mode）

```bash
# 纯 Python 词级修订（无需 Word，跨平台，推荐）
python checker.py "文书.docx" --mechanical-only --mode ooxml

# Word COM 路径（需安装 Word）
python checker.py "文书.docx" --mechanical-only --mode com

# 自动降级（默认：ooxml→com→汇总表）
python checker.py "文书.docx" --mechanical-only --mode auto
```

> `--no-com` 仍保留，等价于 `--mode ooxml`（向后兼容）。

## 自我进化机制

当用户发现**校对遗漏**（某个问题没检查出来）或要求**补充校对点**（特殊情况需增加检查项）时，执行以下进化流程。触发关键词：'校对漏了''这个没检查出来''漏检''补充校对点''校对进化'等。

### 进化目录

```
feedback/
├── cases.md              # 漏检案例库（原始素材，只追加不删除）
├── LESSONS.md            # 一句话经验（Step 3 准备阶段必读）
├── run_regression.py     # 回归测试脚本（改 rules 后必跑）
└── tests/                # 回归样本（YYYY-MM-DD-NN.json，与 cases.md 条目 ID 一致）
```

### 进化流程（五步）

**第 1 步：记录案例**

向 `feedback/cases.md` 追加条目（格式见文件内说明）：日期 ID、原文片段（脱敏）、应报 Issue、漏检原因。

**第 2 步：分类判断**——问题落哪一层？

| 判断 | 特征 | 落点 |
|------|------|------|
| 机械规则 | 可用正则/计算确定（如新错别字对、新金额格式、新案号规则） | `rules/mXx.py` |
| 语义规则 | 需上下文理解（如新易混术语、新模板残留模式） | `references/XX.md` 对应章节 |
| 全新类型 | 现有 M1-M8 均不覆盖 | 与用户讨论是否新增模块（如 M9），不擅自新增 |

**第 3 步：提炼一句话经验**

写入 `feedback/LESSONS.md`（格式：`- [日期] [模块] 规则一句话（→ 案例YYYY-MM-DD-NN）`）。这是最快生效的路径——即使暂不改代码/参考文件，LESSONS.md 在下次 Step 3 就会被读取。

**第 4 步：落规则（分层授权）**

- ✅ **可直接改**：`feedback/cases.md`、`feedback/LESSONS.md`、`references/*.md`（追加规则条目）
- ⚠️ **须先展示 diff 并征得用户同意**：`rules/*.py`、`SKILL.md` 核心流程

**第 5 步：回归验证（改了 rules/*.py 时必做）**

1. 把案例做成回归样本：`feedback/tests/YYYY-MM-DD-NN.json`（格式见 `run_regression.py` 文档字符串；语义模块 M1/M2/M5/M7 的案例无法机械回归，跳过）
2. 运行 `python feedback/run_regression.py`
3. 全部 PASS 才算完成；FAIL 则修复后重跑

### 维护约定（防膨胀）

- LESSONS.md 条目保持**一句话**，详细内容放 cases.md（指针引用）
- 条目被正式规则吸收后标 `[已固化]`；每月蒸馏一次，`[已固化]` 条目可清理归档
- cases.md **只追加不删除**（原始档案）

## 文件结构

```
文书细节校对/
├── SKILL.md                  # 本文件（含 AI Agent 语义审查流程 + 自我进化机制）
├── checker.py                # 主模块（DocReader + MechanicalChecker + COMWriter + OOXMLWriter + FallbackWriter + Proofreader）
├── locate_issues.py          # Step 3.5 定位脚本（宽松 JSON → ai_issues.json，AI 出判断、脚本管定位）
├── requirements.txt          # 依赖清单（python-docx, pywin32, docx-revisions）
├── rules/                    # 检查模块
│   ├── __init__.py           # MECHANICAL_REGISTRY (M3/M4/M6/M8) + SEMANTIC_MODULES 引用
│   ├── m3_law_articles.py    # 机械：法条格式校验
│   ├── m4_amount.py          # 机械：金额计算校验
│   ├── m6_date_logic.py      # 机械：日期逻辑矛盾
│   ├── m8_format.py          # 机械：格式规范
│   ├── m1_template.py        # 语义参考（AI Agent 读取，不自动调用）
│   ├── m2_consistency.py     # 语义参考（AI Agent 读取，不自动调用）
│   ├── m5_legal_terms.py     # 语义参考（AI Agent 读取，不自动调用）
│   └── m7_cross_reference.py # 语义参考（AI Agent 读取，不自动调用）
├── feedback/                 # 自我进化（漏检案例 + 经验 + 回归测试）
│   ├── cases.md              # 漏检案例库
│   ├── LESSONS.md            # 一句话经验（Step 3 必读）
│   ├── run_regression.py     # 回归脚本
│   └── tests/                # 回归样本 JSON
│       └── locate/           # locate_issues.py 样本（8 条验收样本 + 边界用例）
└── references/               # 规则参考文件（AI Agent 阅读）
    ├── 01-template-residue.md
    ├── 02-consistency.md
    ├── 03-law-articles.md
    ├── 04-amount-calculation.md
    ├── 05-legal-terms.md
    ├── 06-date-logic.md
    ├── 07-cross-reference.md
    ├── 08-format-spec.md
    └── output-guide.md
```

## 许可证

SPDX-License-Identifier: MIT

Copyright (c) 2026 moyupeng0422

采用 MIT License 许可，许可证原文见本目录 `LICENSE`。
