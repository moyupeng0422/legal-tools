# doc-proofreading · 法律文书细节校对 Skill

> 一个面向法律文书（起诉状 / 合同 / 催告函 / 仲裁申请书等）的 **AI 细节校对流水线**：
> 机械规则 + AI 语义审查双引擎，产出 Word 原生 **Track Changes（修订）+ Comments（批注）**，
> 律师只需逐条 Accept / Reject，不再逐字通读找错。
>
> **AI 出判断，脚本管定位**——LLM 最容易出错的 `para_index / start_offset` 手算环节由脚本接管，零失误。

---

## 目录

- [解决什么问题](#解决什么问题)
- [8 个校验模块](#8-个校验模块)
- [架构总览](#架构总览)
- [安装](#安装)
- [快速开始（CLI）](#快速开始cli)
- [AI 宿主工作流](#ai-宿主工作流)
- [防误配设计](#防误配设计)
- [回归测试](#回归测试)
- [目录结构](#目录结构)
- [已知边界](#已知边界)
- [免责声明](#免责声明)
- [License](#license)

---

## 解决什么问题

把法律文书交给 LLM 校对，会遇到三层问题：

| # | 痛点 | 本 skill 的对策 |
|---|------|----------------|
| 1 | **LLM 手算位置必错**：让 AI 输出"第几段第几个字符到第几个字符"，offset 频繁错位，修订写歪或写不上 | AI 只产出宽松 JSON（搜索串 + 判断），`locate_issues.py` 在文档中精确查找并生成合规位置字段；多命中拒绝输出、强制消歧 |
| 2 | **纯 LLM 校对不稳定**：金额加总、日期先后这类机械问题时对时错，无法回归 | M3/M4/M6/M8 四个模块为纯 Python 机械检查，配 12+5 个回归样本，改一版跑一遍 |
| 3 | **校对经验用完即丢**：每次漏检都靠 AI 当场发挥 | 自我进化机制：漏检案例入库 → 提炼一句话经验 → 沉淀为规则 → 回归验证 |

## 8 个校验模块

| 模块 | 名称 | 引擎 | 检查内容示例 |
|------|------|------|-------------|
| M1 | 模板残留 | AI 语义 | `___年___月___日`、`[请填写]` 占位符；新旧当事人名称残留 |
| M2 | 全文一致性 | AI 语义 | 当事人名称前后变体（可接企查查/天眼查 MCP 核验工商名称） |
| M3 | 法条校验 | 机械 | 法条首次出现须全称；"第585条"→"第五百八十五条" |
| M4 | 金额计算 | 机械 | 表格分项加总 vs 合计；大小写金额比对；单位混用 |
| M5 | 法律术语/错别字 | AI 语义 | 定金 vs 订金、法人 vs 法定代表人、"委拖"→"委托" |
| M6 | 日期逻辑 | 机械 | 提交日 > 验收日、签订前付款、晚于落款的未来日期 |
| M7 | 交叉引用 | AI 语义 | "证据五"无对应清单、"第3.2条"不存在等孤儿引用 |
| M8 | 格式规范 | 机械 | 案号格式、法院简称补全（"杭州中院"→"杭州市中级人民法院"） |

## 架构总览

```
输入 .docx
    │
    ▼
[Step 1] DocReader ──── python-docx 提取段落/表格/页眉页脚（零 Word 依赖）
    │
    ▼
[Step 2] 机械检查 ───── M3/M4/M6/M8 纯 Python 规则 → mech.json
    │
    ▼
[Step 3] AI 语义审查 ── M1/M2/M5/M7 → 宽松 JSON（search 串定位，不手算 offset）
    │
    ▼
[Step 3.5] locate_issues.py ─ 脚本定位：未命中/歧义/重复 → 报告人工消歧
    │                          全命中才输出 ai_issues.json
    ▼
[Step 4] 写入修订+批注 ─ --mode 三级降级
    │   ├─ ooxml → 纯 Python 词级修订（推荐，无需 Word，~0.2s）
    │   ├─ com   → Word COM（兜底复杂结构）
    │   └─ auto  → ooxml → com → docx-revisions 汇总表
    ▼
输出 _校对.docx（Word 直接 Accept/Reject + 查看批注）
```

## 安装

```bash
# Python 3.10+（3.13+ 已验证）
pip install -r requirements.txt   # python-docx / pywin32 / docx-revisions
```

- 作为 Agent Skill 使用：把整个 `文书细节校对/` 目录放入宿主的 skills 目录（Claude Code / Workbuddy 等）
- 仅用 CLI：任意目录下直接运行 `python checker.py` 即可
- `--mode ooxml`（默认首选）**无需安装 Word**；`--mode com` 需要 Windows + Word

## 快速开始（CLI）

```bash
# 1. 仅跑机械检查（默认不写文件，只看结果）
python checker.py "文书.docx" --mechanical-only --export-json mech.json

# 2. AI 产出宽松 JSON 后，脚本定位生成 ai_issues.json
python locate_issues.py "文书.docx" loose_issues.json -o ai_issues.json --report locate_report.md

# 3. 合并机械 + 语义结果，写入修订稿（--mode auto 默认 ooxml 优先）
python checker.py "文书.docx" --issues-json ai_issues.json -o "文书_校对.docx"

# 复用步骤 1 的机械结果，避免二次检查
python checker.py "文书.docx" --issues-json ai_issues.json --mech-json mech.json -o "文书_校对.docx"
```

宽松 JSON 每条只需 6 个字段：

```json
[
  {
    "search": "委拖",
    "issue_type": "M5_错别字",
    "severity": "严重",
    "action": "replace",
    "suggested_text": "委托",
    "comment_text": "“委拖”为错别字，应为“委托”"
  }
]
```

可选消歧字段：`occurrence`（取第 N 处命中）、`scope`（限定段落/表格/页眉页脚）、`context_before` / `context_after`（上下文锚）。

## AI 宿主工作流

在 Claude Code / Workbuddy 等 AI 宿主中，`SKILL.md` 即完整操作规范。AI 的职责边界被严格限定：

- **AI 只做语义判断**：读文档 → 对照 `references/` 规则与 `feedback/LESSONS.md` 经验 → 产出宽松 JSON
- **定位交给脚本**：AI 拿到定位报告后核对每条命中的前后文摘录，确认锚点无误才进入写入
- **失败即拒绝**：任何一条未命中/歧义/重复，脚本不产出 `ai_issues.json`，AI 修正后重跑——绝不带着疑问进入写入环节

## 防误配设计

| 机制 | 说明 |
|------|------|
| 多命中拒绝 | 搜索串命中多处且未消歧 → AMBIGUOUS，列出全部候选位置 |
| 上下文锚 | `context_before/after` 先过滤，过滤后唯一即通过；与 occurrence 冲突时以 context 为准并警告 |
| DUPLICATE 检测 | 多条条目命中同位置同类型 → 判失败（多为漏改 occurrence/复制忘改字段） |
| 原文逐字校验 | 写入前 Writer 校验 covering runs 文本 = original_text，不匹配跳过修订仅留批注（双保险） |
| 不可见字符标记 | NOT_FOUND 时近似候选显式标记 `⟨U+00A0⟩` 零宽字符等（PDF/网页复制常见坑） |
| 引号归一化 | 批注正文 ASCII/单弯引号自动转全角 `“”` |

## 回归测试

```bash
# 机械模块回归（16 个样本，含反向防误报样本）
python feedback/run_regression.py

# locate 定位回归（5 个场景；场景 C/E 随仓库分发可直接跑）
python feedback/tests/locate/verify_locate.py

# 场景 A/B/D 需自备测试文书资产（含表格/页眉/歧义串的 docx），设置环境变量后启用
PROOFREAD_TEST_ASSETS=/path/to/your/test/assets python feedback/tests/locate/verify_locate.py
```

## 目录结构

```
文书细节校对/
├── SKILL.md            # AI 宿主操作规范（四步流水线 + 消歧规则 + 自我进化机制）
├── checker.py          # 主模块（DocReader + 机械检查 + 三级 Writer + CLI）
├── locate_issues.py    # Step 3.5 定位脚本（宽松 JSON → ai_issues.json）
├── requirements.txt
├── rules/              # 8 个校验模块（M1~M8）
├── references/         # AI 语义审查的规则参考文件（01~08 + 输出指南）
└── feedback/           # 自我进化：漏检案例库 + 一句话经验 + 回归测试
    └── tests/          # 16 个机械回归样本 + locate/ 5 个定位回归场景
```

## 已知边界

- 页眉/页脚：**修订支持**（词级修订写入 headerN.xml），**批注跳过**（Writer 限制）——页眉页脚问题请用 replace/delete
- COM 路径使用 Word 全局段落编号（含表格内段落），与 python-docx 编号在表格前置文档中存在错位；默认 `--mode auto` 走 OOXML 可规避，且 COM 写入前有原文包含性校验兜底
- OOXML 词级修订对文本框、SDT 内容控件等复杂结构覆盖有限，此类文档建议显式 `--mode com`
- `--issues-json` 不校验字段枚举（locate_issues.py 才校验），建议始终经 Step 3.5 生成语义 Issue
- 案号检测（M8）："半角括号+第字"形态（如 `(2025)浙01民初第456号`）暂不报（旧版既有盲区）；全角左+半角右混合括号归入"半角括号"提示（建议重建正确，下批修正归类）

## 免责声明

本工具输出的一切校对结果（修订建议与批注）**仅供人工复核参考，不构成法律意见**。
采用本工具产出的文书在提交/签署前，应当由执业律师逐条审查确认。

## License

[MIT](./LICENSE) © 2026 moyupeng0422
