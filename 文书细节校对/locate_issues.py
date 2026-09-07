# -*- coding: utf-8 -*-
"""locate_issues.py —— AI 出判断、脚本管定位（Step 3 语义 Issue 定位器）

背景：Step 3 最慢最易错的环节不是语义判断，而是 AI 手算 para_index/start_offset/end_offset。
本脚本接收"宽松 JSON"（每条仅需 搜索串 + issue_type + severity + action + suggested_text + comment_text），
在 docx 的段落/表格单元格/页眉页脚文本中精确查找，输出与 checker.py `load_issues_from_json`
完全兼容的 ai_issues.json（裸数组，11 字段）。

坐标系：重新用 python-docx 打开 docx，在**未 strip** 的段落全文上搜索——
与 OOXML Writer（checker.py `_locate_paragraph` → `doc.paragraphs[para_index-1]` + run 切分）
严格一致；COM Writer 使用 Word 全局段落编号（含表格内段落），表格前置文档存在既有编号差异
（auto 降级链已 ooxml 优先，影响可控；COM 侧另有 original_text 包含性校验兜底）。

宽松 JSON schema（裸数组，每条 6 必填 + 3 可选）：
    search          必填  搜索串，必须与原文逐字一致（空格/全半角差异会导致 NOT_FOUND）
    issue_type      必填  M1_模板残留 | M2_一致性 | M5_术语 | M5_错别字 | M5_语病 | M7_引用 | M7_孤儿引用
    severity        必填  致命 | 严重 | 一般
    action          必填  replace | delete | comment_only
    suggested_text  replace 必填；delete 多写会被警告并丢弃；comment_only 填 ""
    comment_text    必填  批注正文（写出前经 normalize_cn_quotes 归一化引号）
    occurrence      可选  多命中时取第 N 处（1-based，按文档顺序计）
    scope           可选  paragraph | table_cell | header | footer（缺省按此顺序全域搜索）
    context_before  可选  上下文锚：命中处前方文本须以此结尾
    context_after   可选  上下文锚：命中处后方文本须以此开头

消歧优先级（固定规则）：context 锚先过滤 → 过滤后唯一即 OK（occurrence 可不填）
→ 仍多值再看 occurrence → occurrence 与 context 指向不同命中时以 context 为准并出警告。
occurrence 超出命中数时：多命中场景判 AMBIGUOUS（越界）；唯一命中场景位置本无歧义，
出"超出命中数，已忽略"警告后仍 OK（提示 AI 核对原文是否漏嵌/搜索串是否过窄）。

输出策略：全部条目定位成功才写 -o 输出文件；任何失败（NOT_FOUND/AMBIGUOUS/INVALID/
CONTEXT_MISMATCH/DUPLICATE）→ 只出定位报告、不写 ai_issues.json（--allow-partial 兜底可写出已命中部分）。
退出码：0=全命中 / 1=有失败条目 / 2=用法或 IO 错误。

DUPLICATE 检测：多条条目命中同一位置且 issue_type 相同 → 判 DUPLICATE（按失败处理）。
重复往往意味着 AI 出错（漏改 occurrence、复制条目忘改字段），静默放行会掩盖问题。
注意：同一位置**不同** issue_type 的多条条目是合法场景（如 M5_术语＋M7_引用同段），不误伤。
同一搜索串需要 N 条 Issue（原文出现 N 处）时，必须逐条给 occurrence（1..N）。

用法：
    python locate_issues.py 文书.docx loose_issues.json -o ai_issues.json --report locate_report.md
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import dataclass, field

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from checker import normalize_cn_quotes

# 合法枚举（与 SKILL.md Step 3 章节一致；新增 issue_type 时同步此处与 SKILL.md）
VALID_ISSUE_TYPES = {
    "M1_模板残留", "M2_一致性",
    "M5_术语", "M5_错别字", "M5_语病",
    "M7_引用", "M7_孤儿引用",
}
VALID_ACTIONS = {"replace", "delete", "comment_only"}
VALID_SEVERITIES = {"致命", "严重", "一般"}
VALID_SCOPES = {"paragraph", "table_cell", "header", "footer"}
SCOPE_ORDER = ["paragraph", "table_cell", "header", "footer"]

REQUIRED_KEYS = ("search", "issue_type", "severity", "action", "comment_text")

# 不可见字符 → 报告中的显式标记（NOT_FOUND 排查：PDF/网页复制常见）
INVISIBLE_MARKS = {
    " ": "⟨U+00A0⟩",   # 不间断空格
    "​": "⟨U+200B⟩",   # 零宽空格
    "‌": "⟨U+200C⟩",
    "‍": "⟨U+200D⟩",
    "﻿": "⟨U+FEFF⟩",   # BOM
    "　": "⟨U+3000⟩",   # 全角空格
    "\t": "⟨TAB⟩",
    "\n": "⟨LF⟩",
}


def mark_invisible(text: str) -> str:
    """把文本中的不可见字符替换为显式标记，供报告展示。"""
    out = []
    for ch in text:
        if ch in INVISIBLE_MARKS:
            out.append(INVISIBLE_MARKS[ch])
        elif unicodedata.category(ch) in ("Cf", "Zl", "Zp"):
            out.append(f"⟨U+{ord(ch):04X}⟩")
        else:
            out.append(ch)
    return "".join(out)


def _norm(text: str) -> str:
    """近似匹配用归一化：NFKC + 去除空白与格式字符（Cf/Zs/Zl/Zp）。"""
    out = []
    for ch in unicodedata.normalize("NFKC", text):
        if ch.isspace() or unicodedata.category(ch) in ("Cf", "Zs", "Zl", "Zp"):
            continue
        out.append(ch)
    return "".join(out)


@dataclass
class Location:
    """一个可搜索位置（与 Writer 坐标系对齐）。"""
    scope: str                 # paragraph | table_cell | header | footer
    text: str                  # 未 strip 文本
    para_index: int            # 段落号：正文/header/footer 1-based；table_cell 固定 0
    cell_ref: list | None = None  # 表格 (t, r, c) 0-based，JSON 中为 list

    @property
    def label(self) -> str:
        if self.scope == "paragraph":
            return f"正文段落 §{self.para_index}"
        if self.scope == "table_cell":
            t, r, c = self.cell_ref
            return f"表格{t + 1} 行{r + 1} 列{c + 1}"
        return f"{'页眉' if self.scope == 'header' else '页脚'} §{self.para_index}"


@dataclass
class Match:
    loc: Location
    start: int
    end: int

    def excerpt(self, width: int = 20) -> str:
        text = self.loc.text
        before = text[max(0, self.start - width):self.start]
        after = text[self.end:self.end + width]
        return f"…{mark_invisible(before)}【{mark_invisible(text[self.start:self.end])}】{mark_invisible(after)}…"


@dataclass
class EntryResult:
    idx: int                       # 宽松 JSON 中的条目序号（1-based）
    status: str                    # OK | AMBIGUOUS | NOT_FOUND | CONTEXT_MISMATCH | INVALID | DUPLICATE
    entry: dict
    warnings: list = field(default_factory=list)
    match: Match | None = None     # OK/DUPLICATE 时的命中
    candidates: list = field(default_factory=list)   # AMBIGUOUS 候选
    fuzzy: list = field(default_factory=list)        # NOT_FOUND 近似候选
    context_detail: dict | None = None               # CONTEXT_MISMATCH 三行对照
    occurrence_note: str = ""                        # OK 时"第 N 处/共 M 处"


def build_locations(docx_path: str) -> list[Location]:
    """用 python-docx 打开文档，构建与 OOXML Writer 一致的位置索引。"""
    import docx

    doc = docx.Document(docx_path)
    locs: list[Location] = []
    for i, para in enumerate(doc.paragraphs, start=1):
        locs.append(Location("paragraph", para.text, i))
    for t, table in enumerate(doc.tables):
        for r, row in enumerate(table.rows):
            for c, cell in enumerate(row.cells):
                if cell.paragraphs:
                    locs.append(Location("table_cell", cell.paragraphs[0].text, 0, [t, r, c]))
    if doc.sections:
        for i, para in enumerate(doc.sections[0].header.paragraphs, start=1):
            locs.append(Location("header", para.text, i))
        for i, para in enumerate(doc.sections[0].footer.paragraphs, start=1):
            locs.append(Location("footer", para.text, i))
    return locs


def find_all(locs: list[Location], search: str, scopes: list[str]) -> list[Match]:
    """收集所有精确命中（按域顺序 + 文档顺序）。"""
    matches: list[Match] = []
    for scope in scopes:
        for loc in locs:
            if loc.scope != scope:
                continue
            pos = loc.text.find(search)
            while pos >= 0:
                matches.append(Match(loc, pos, pos + len(search)))
                pos = loc.text.find(search, pos + 1)
    return matches


def check_context(m: Match, before: str, after: str) -> bool:
    """上下文锚校验：前方须以 before 结尾，后方须以 after 开头。"""
    text = m.loc.text
    if before and not text[:m.start].endswith(before):
        return False
    if after and not text[m.end:].startswith(after):
        return False
    return True


def context_actual(m: Match, before: str, after: str) -> tuple[str, str]:
    """命中处实际前后文（与 AI 提供锚等长截取，供三行对照）。"""
    text = m.loc.text
    actual_before = text[max(0, m.start - len(before)):m.start] if before else ""
    actual_after = text[m.end:m.end + len(after)] if after else ""
    return actual_before, actual_after


def first_diff(provided: str, actual: str) -> str:
    """找出两串第一个差异字符位置与内容（用于三行对照的差异标注）。"""
    if provided == actual:
        return "无差异（锚文本正确，可能是长度不足/越界）"
    n = min(len(provided), len(actual))
    for i in range(n):
        if provided[i] != actual[i]:
            return (f"第 {i + 1} 字不同：提供 ⟨{mark_invisible(provided[i])}⟩(U+{ord(provided[i]):04X}) "
                    f"实际 ⟨{mark_invisible(actual[i])}⟩(U+{ord(actual[i]):04X})")
    longer, whose = (provided, "提供的锚") if len(provided) > len(actual) else (actual, "实际文本")
    return f"前 {n} 字一致，{whose}多出：⟨{mark_invisible(longer[n:])}⟩"


def fuzzy_candidates(locs: list[Location], search: str, scopes: list[str], limit: int = 5) -> list[Match]:
    """NOT_FOUND 时的近似候选：归一化后子串匹配（仅提示，绝不直接生成 Issue）。"""
    ns = _norm(search)
    if not ns:
        return []
    out: list[Match] = []
    for scope in scopes:
        for loc in locs:
            if loc.scope != scope:
                continue
            ntext = _norm(loc.text)
            pos = ntext.find(ns)
            if pos < 0:
                continue
            # 归一化坐标近似映射回原文（展示用，不用于定位）
            real_start = max(0, pos - 5)
            real_end = min(len(loc.text), real_start + len(search) + 10)
            out.append(Match(loc, real_start, real_end))
            if len(out) >= limit:
                return out
    return out


def validate_entry(entry: dict, idx: int) -> EntryResult:
    """字段校验（不依赖文档），INVALID 时该条目不输出。"""
    res = EntryResult(idx=idx, status="OK", entry=entry)
    missing = [k for k in REQUIRED_KEYS if not entry.get(k)]
    if missing:
        res.status = "INVALID"
        res.warnings.append(f"缺少必填字段或为空：{', '.join(missing)}")
        return res
    if entry["issue_type"] not in VALID_ISSUE_TYPES:
        res.status = "INVALID"
        res.warnings.append(f"issue_type 非法：{entry['issue_type']}（合法值：{'、'.join(sorted(VALID_ISSUE_TYPES))}）")
    if entry["action"] not in VALID_ACTIONS:
        res.status = "INVALID"
        res.warnings.append(f"action 非法：{entry['action']}（合法值：replace、delete、comment_only）")
    if entry["severity"] not in VALID_SEVERITIES:
        res.status = "INVALID"
        res.warnings.append(f"severity 非法：{entry['severity']}（合法值：致命、严重、一般）")
    if res.status == "INVALID":
        return res
    action, suggested = entry["action"], entry.get("suggested_text", "")
    if action == "replace" and not suggested:
        res.status = "INVALID"
        res.warnings.append("action=replace 但 suggested_text 为空")
    elif action == "delete" and suggested:
        res.warnings.append("action=delete 不消费 suggested_text，已自动丢弃该字段")
    if entry["issue_type"].startswith("M7") and action != "comment_only":
        res.warnings.append("SKILL.md 约定 M7 固定 comment_only（引用问题需人工确认），请复核")
    occ = entry.get("occurrence")
    if occ is not None and (not isinstance(occ, int) or occ < 1):
        res.status = "INVALID"
        res.warnings.append(f"occurrence 须为正整数，收到：{occ!r}")
    scope = entry.get("scope")
    if scope is not None and scope not in VALID_SCOPES:
        res.status = "INVALID"
        res.warnings.append(f"scope 非法：{scope}（合法值：{'、'.join(VALID_SCOPES)}）")
    return res


def locate_entry(res: EntryResult, locs: list[Location]) -> EntryResult:
    """对单个通过校验的条目执行搜索与消歧。"""
    entry = res.entry
    search: str = entry["search"]
    before: str = entry.get("context_before", "") or ""
    after: str = entry.get("context_after", "") or ""
    scopes = [entry["scope"]] if entry.get("scope") else SCOPE_ORDER

    matches = find_all(locs, search, scopes)
    if not matches:
        res.status = "NOT_FOUND"
        res.fuzzy = fuzzy_candidates(locs, search, scopes)
        hint = ""
        if any(ch in INVISIBLE_MARKS or unicodedata.category(ch) in ("Cf", "Zs") for ch in search):
            hint = f"（搜索串含不可见/空白字符：{mark_invisible(search)}）"
        res.warnings.append(f"全文未找到搜索串{hint}；检查全半角/空格/标点是否与原文逐字一致")
        return res

    # 消歧优先级：context 锚先过滤
    if before or after:
        filtered = [m for m in matches if check_context(m, before, after)]
        if not filtered:
            res.status = "CONTEXT_MISMATCH"
            m0 = matches[0]
            actual_b, actual_a = context_actual(m0, before, after)
            res.context_detail = {
                "match": m0,
                "provided_before": before, "provided_after": after,
                "actual_before": actual_b, "actual_after": actual_a,
                "diff_before": first_diff(before, actual_b) if before else "",
                "diff_after": first_diff(after, actual_a) if after else "",
            }
            res.warnings.append(f"context 锚过滤后 0 命中（原始命中 {len(matches)} 处，首处：{m0.loc.label}）")
            return res

        # occurrence 与 context 冲突时以 context 为准并警告
        occ = entry.get("occurrence")
        if occ is not None and occ <= len(matches):
            raw_pick = matches[occ - 1]
            if raw_pick not in filtered:
                res.warnings.append(
                    f"occurrence={occ} 指向的命中被 context 锚过滤（{raw_pick.loc.label}），以 context 为准")
        if len(filtered) > 1 and occ is not None:
            if occ <= len(filtered):
                pick, note = filtered[occ - 1], f"第 {occ} 处/共 {len(filtered)} 处（context 过滤后）"
            else:
                res.status = "AMBIGUOUS"
                res.candidates = filtered
                res.warnings.append(f"occurrence={occ} 越界（context 过滤后仅 {len(filtered)} 处）")
                return res
        elif len(filtered) == 1:
            pick, note = filtered[0], f"唯一命中/共 {len(matches)} 处（原始）"
            if occ is not None and occ > len(matches):
                res.warnings.append(
                    f"occurrence={occ} 超出命中总数 {len(matches)}，已忽略（以 context 锚结果为准）")
        else:
            res.status = "AMBIGUOUS"
            res.candidates = filtered
            res.warnings.append(
                f"context 锚过滤后仍 {len(filtered)} 处命中，请补 occurrence 或细化 context/搜索串")
            return res
        res.match, res.occurrence_note = pick, note
        return res

    # 无 context 锚：直接看命中数
    total = len(matches)
    occ = entry.get("occurrence")
    if total == 1:
        # 唯一命中时位置无歧义，occurrence 无效不阻断，但必须点破（防 AI 绕圈猜原因）
        if occ is not None and occ > total:
            res.warnings.append(
                f"occurrence={occ} 超出命中数 {total}，已忽略（全文仅 1 处命中；"
                f"若预期多处，请核对原文是否漏嵌/搜索串是否过窄）")
        res.match, res.occurrence_note = matches[0], "唯一命中"
        return res
    if occ is None:
        res.status = "AMBIGUOUS"
        res.candidates = matches
        res.warnings.append(f"搜索串命中 {total} 处，请补 occurrence（第几处）或 context 锚消歧")
        return res
    if occ > total:
        res.status = "AMBIGUOUS"
        res.candidates = matches
        res.warnings.append(f"occurrence={occ} 越界（共 {total} 处命中）")
        return res
    res.match, res.occurrence_note = matches[occ - 1], f"第 {occ} 处/共 {total} 处"
    return res


def mark_duplicates(results: list[EntryResult]) -> None:
    """DUPLICATE 检测：多条 OK 条目命中同一位置且 issue_type 相同 → 全部改判 DUPLICATE。

    判定键 (location_type, para_index, cell_ref, start_offset, end_offset, issue_type)。
    不同 issue_type 同位置是合法场景（如 M5_术语＋M7_引用同段），不误伤。
    """
    seen: dict[tuple, list[EntryResult]] = {}
    for r in results:
        if r.status != "OK" or r.match is None:
            continue
        m = r.match
        key = (m.loc.scope, m.loc.para_index,
               tuple(m.loc.cell_ref) if m.loc.cell_ref else None,
               m.start, m.end, r.entry["issue_type"])
        seen.setdefault(key, []).append(r)
    for group in seen.values():
        if len(group) < 2:
            continue
        peers = [g.idx for g in group]
        for r in group:
            r.status = "DUPLICATE"
            others = "、#".join(str(i) for i in peers if i != r.idx)
            r.warnings.append(
                f"与条目 #{others} 命中同一位置且 issue_type 相同——疑似漏改 occurrence 或复制条目忘改字段；"
                f"如原文多处需分别标注，请逐条补 occurrence（1..N）；如同一条问题请删去多余条目")


def to_issue_dict(res: EntryResult) -> dict:
    """OK 条目 → 与 load_issues_from_json 兼容的 11 字段 dict。"""
    entry, m = res.entry, res.match
    action = entry["action"]
    suggested = entry.get("suggested_text", "")
    if action == "delete":
        suggested = ""  # Writer delete 路径不消费该字段（校验阶段已警告）
    return {
        "location_type": m.loc.scope,
        "para_index": m.loc.para_index,
        "cell_ref": m.loc.cell_ref,
        "start_offset": m.start,
        "end_offset": m.end,
        "issue_type": entry["issue_type"],
        "severity": entry["severity"],
        "action": action,
        "original_text": entry["search"],   # 逐字拷贝，满足 Writer covering-runs 校验
        "suggested_text": suggested,
        "comment_text": normalize_cn_quotes(entry["comment_text"]),
    }


# ---------------- 报告渲染 ----------------

def render_report(results: list[EntryResult], docx_path: str, total: int) -> str:
    ok = [r for r in results if r.status == "OK"]
    failed = [r for r in results if r.status != "OK"]
    lines: list[str] = []
    if failed and ok:
        lines.append(f"> ⚠ **部分产出 {len(ok)}/{total}**——存在失败条目，Step 4 前必须补齐\n")
    lines.append(f"# locate_issues 定位报告")
    lines.append(f"- 文书：`{docx_path}`")
    lines.append(f"- 条目：{total}；命中 {len(ok)}；失败 {len(failed)}"
                 f"（{'、'.join(sorted({r.status for r in failed})) if failed else '无'}）\n")

    for r in results:
        e = r.entry
        head = f"## #{r.idx} {e.get('issue_type', '?')}：{mark_invisible(e.get('search', ''))[:30]}"
        lines.append(head)
        lines.append(f"- **状态**：{r.status}" + (f"（{r.occurrence_note}）" if r.occurrence_note else ""))
        for w in r.warnings:
            lines.append(f"- ⚠ {w}")
        if r.status == "OK" and r.match:
            lines.append(f"- 位置：{r.match.loc.label}，offset [{r.match.start}, {r.match.end})")
            lines.append(f"- 摘录：{r.match.excerpt()}")
        elif r.status == "DUPLICATE" and r.match:
            lines.append(f"- 位置：{r.match.loc.label}，offset [{r.match.start}, {r.match.end})（与同组条目重复）")
            lines.append(f"- 摘录：{r.match.excerpt()}")
        elif r.status == "AMBIGUOUS":
            lines.append(f"- 候选 {len(r.candidates)} 处：")
            for i, c in enumerate(r.candidates, 1):
                lines.append(f"  {i}. {c.loc.label} offset [{c.start}, {c.end}) {c.excerpt()}")
        elif r.status == "NOT_FOUND":
            if r.fuzzy:
                lines.append("- 近似候选（归一化匹配，仅提示，注意其中不可见字符）：")
                for i, c in enumerate(r.fuzzy, 1):
                    lines.append(f"  {i}. {c.loc.label} {c.excerpt()}")
            else:
                lines.append("- 无近似候选（建议核对原文后重抄搜索串）")
        elif r.status == "CONTEXT_MISMATCH" and r.context_detail:
            d = r.context_detail
            lines.append("- 三行对照（以首处命中为参照）：")
            lines.append(f"  1. AI 提供锚：前=`{mark_invisible(d['provided_before'])}` 后=`{mark_invisible(d['provided_after'])}`")
            lines.append(f"  2. 命中处实际：前=`{mark_invisible(d['actual_before'])}` 后=`{mark_invisible(d['actual_after'])}`")
            diffs = [x for x in (d["diff_before"], d["diff_after"]) if x]
            lines.append(f"  3. 差异：{'；'.join(diffs) if diffs else '见上'}")
        lines.append("")

    lines.append("## 汇总")
    lines.append("| # | issue_type | 搜索串 | 状态 | 备注 |")
    lines.append("|---|-----------|--------|------|------|")
    for r in results:
        e = r.entry
        note = r.occurrence_note or "；".join(r.warnings)[:60]
        lines.append(f"| {r.idx} | {e.get('issue_type', '?')} | {mark_invisible(e.get('search', ''))[:20]} "
                     f"| {r.status} | {note} |")
    return "\n".join(lines) + "\n"


# ---------------- CLI ----------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="宽松 JSON → 精确定位 → ai_issues.json（AI 出判断、脚本管定位）")
    parser.add_argument("docx", help="待校对文书 docx 路径")
    parser.add_argument("loose", help="宽松 JSON 路径（裸数组，schema 见文件头 docstring）")
    parser.add_argument("-o", "--output", help="输出 ai_issues.json 路径（全部命中才写）")
    parser.add_argument("--report", help="定位报告输出路径（缺省打到 stdout）")
    parser.add_argument("--allow-partial", action="store_true",
                        help="兜底：有失败条目时仍写出已命中部分（报告顶部会标注部分产出）")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    # 读入（IO 错误 → 退出码 2）
    try:
        with open(args.loose, "r", encoding="utf-8") as f:
            entries = json.load(f)
        locations = build_locations(args.docx)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[错误] 用法/IO 问题：{e}", file=sys.stderr)
        return 2
    if not isinstance(entries, list):
        print("[错误] 宽松 JSON 须为裸数组", file=sys.stderr)
        return 2

    results: list[EntryResult] = []
    for idx, entry in enumerate(entries, 1):
        res = validate_entry(entry if isinstance(entry, dict) else {}, idx)
        if res.status != "INVALID":
            res = locate_entry(res, locations)
        # INVALID 但字段足够时仍尝试定位，让报告一并给出定位信息（不参与输出）
        elif entry and isinstance(entry, dict) and entry.get("search"):
            probe = EntryResult(idx=idx, status="INVALID", entry=entry)
            located = locate_entry(probe, locations)
            res.match, res.candidates, res.fuzzy = located.match, located.candidates, located.fuzzy
            res.occurrence_note = located.occurrence_note
        results.append(res)

    mark_duplicates(results)   # 同位置同类型多条 → DUPLICATE（按失败处理）

    ok_results = [r for r in results if r.status == "OK"]
    failed = [r for r in results if r.status != "OK"]

    report = render_report(results, args.docx, len(entries))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"定位报告已写入：{args.report}")
    else:
        print(report)

    # 写输出：全命中，或 --allow-partial
    wrote = False
    if args.output:
        if not failed:
            data = [to_issue_dict(r) for r in ok_results]
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            wrote = True
            print(f"ai_issues.json 已生成：{len(data)} 条 → {args.output}")
        elif args.allow_partial:
            data = [to_issue_dict(r) for r in ok_results]
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            wrote = True
            print(f"⚠ 部分产出 {len(data)}/{len(entries)} 条 → {args.output}（失败条目见报告）")
        else:
            print(f"未写 {args.output}：{len(failed)} 条失败（修正后重跑，或加 --allow-partial 兜底）")

    if args.verbose:
        for r in ok_results:
            m = r.match
            print(f"  OK #{r.idx} {r.entry['issue_type']} @ {m.loc.label} [{m.start},{m.end}) {r.occurrence_note}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
