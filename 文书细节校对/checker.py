"""
文书细节校对 v2 — 主模块

三步流水线：DocReader → 机械检查（M3/M4/M6/M8）/ AI Agent 语义审查（M1/M2/M5/M7）→ COMWriter

用法：
    # 机械检查模式（仅 Python 正则）
    python checker.py "文书.docx" --mechanical-only -o "文书_校对.docx"

    # 完整模式（需先由 AI Agent 完成语义审查，输出 JSON）
    python checker.py "文书.docx" --issues-json ai_issues.json -o "文书_校对.docx"

    # 降级模式（无 Word COM）
    python checker.py "文书.docx" --mechanical-only --no-com
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import docx
from docx.document import Document

logger = logging.getLogger(__name__)


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class Issue:
    """校对问题统一数据结构"""
    location_type: str       # "paragraph" | "table_cell" | "header" | "footer"
    para_index: int           # 段落索引（1-based）
    cell_ref: tuple | None    # (table_idx, row, col) 表格单元格
    start_offset: int         # 段落/单元格内字符偏移（0-based）
    end_offset: int           # 段落/单元格内字符结束偏移
    issue_type: str           # "M1_模板残留" | "M2_一致性" | ...
    severity: str             # "致命" | "严重" | "一般"
    action: str               # "replace" | "delete" | "comment_only"
    original_text: str        # 原文（用于定位确认）
    suggested_text: str = ""   # 建议替换文本
    comment_text: str = ""     # 批注内容

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParagraphInfo:
    """段落信息"""
    text: str
    index: int         # 1-based
    style: str


@dataclass
class CellInfo:
    """表格单元格信息"""
    text: str
    row: int
    col: int
    table_idx: int


@dataclass
class DocContent:
    """文档内容结构化表示"""
    paragraphs: list[ParagraphInfo] = field(default_factory=list)
    tables: list[CellInfo] = field(default_factory=list)
    headers: list[ParagraphInfo] = field(default_factory=list)
    footers: list[ParagraphInfo] = field(default_factory=list)
    entity_index: dict[str, list[dict]] = field(default_factory=dict)
    raw_full_text: str = ""


# =============================================================================
# 模块级辅助函数（被所有 Writer 复用）
# =============================================================================

SEVERITY_ORDER = {"致命": 0, "严重": 1, "一般": 2}

# 标题行前缀标记：用基础字符 ●（U+25CF，所有字体都有），继承标题行颜色。
# 不用彩色 emoji（🔴🟡🟢）：🟡🟢 是 Emoji 12.0 新增，需彩色 emoji 字体；
# 给 run 设显式 font.color 后 Word 不再走彩色 emoji 回退，🟡🟢 在普通字体（宋体）里无字形会丢失。
SEVERITY_MARK = "●"

# 标题行配色（severity → RGB 元组）。OOXML 用 RGBColor，COM 转 Word BGR int。
# 致命=红 / 严重=橙 / 一般=蓝（信息性，不刺眼）
SEVERITY_COLOR_RGB = {
    "致命": (255, 0, 0),
    "严重": (255, 128, 0),
    "一般": (68, 114, 196),
}


def issue_type_label(issue_type: str) -> str:
    """issue_type 取中文标签：M2_一致性 → 一致性；无下划线原样返回。

    面向用户只显示中文（M2 等编码对用户无意义），完整 issue_type 仍保留在 Issue 对象供日志。
    """
    if "_" in issue_type:
        return issue_type.split("_", 1)[1]
    return issue_type


def normalize_cn_quotes(text: str) -> str:
    """各类引号 → 中文全角双弯引号 “”（成对转换）。

    中文法律文书引号一律 “”（SKILL.md 开发规范 1.3）。2026-09-07 起统一收敛为双弯引号：
    ASCII " → “/”（开/关交替）；ASCII ' → “/”（开/关交替）；
    弯单引号 ‘’ → “”（实测批注中出现过 ‘为维护…’ 式单弯引号，不符合规范）。
    用于批注正文/建议渲染前归一化，从源头杜绝直引号与单弯引号（AI/模块可能误写）。
    """
    if not text:
        return text
    out = []
    d_open = s_open = True
    for ch in text:
        if ch == '"':
            out.append("“" if d_open else "”")  # “ / ”
            d_open = not d_open
        elif ch == "'":
            out.append("“" if s_open else "”")  # ASCII 单引号也归一为双弯引号
            s_open = not s_open
        elif ch == "‘":
            out.append("“")
            s_open = True
        elif ch == "’":
            out.append("”")
            s_open = False
        else:
            out.append(ch)
    return "".join(out)


def severity_rgb_int(severity: str) -> int:
    """severity → Word Font.Color 的 BGR int（b*65536 + g*256 + r）。"""
    r, g, b = SEVERITY_COLOR_RGB.get(severity, (0, 0, 0))
    return b * 65536 + g * 256 + r


def merge_same_location(issues: list[Issue]) -> list[Issue]:
    """合并同位置的多个 Issue（模块级函数，被所有 Writer 复用）

    同一 (location_type, para_index, start_offset) 的多个 Issue 合并为一次写入：
    - 保留 severity 最高的 action
    - 合并所有 comment_text（用 " | " 分隔）
    """
    groups: dict[tuple, list[Issue]] = OrderedDict()
    for issue in issues:
        key = (issue.location_type, issue.para_index, issue.start_offset)
        groups.setdefault(key, []).append(issue)
    merged = []
    for issues_list in groups.values():
        issues_list.sort(key=lambda i: SEVERITY_ORDER.get(i.severity, 3))
        primary = issues_list[0]
        if len(issues_list) > 1:
            comments = [i.comment_text for i in issues_list if i.comment_text]
            if comments:
                primary.comment_text = " | ".join(comments)
        merged.append(primary)
    return merged


def format_comment(issue: Issue) -> list[str]:
    """生成结构化批注内容（多段落列表）。

    返回段落列表，OOXMLWriter 渲染为真实 <w:p>（标题行上色加粗），COMWriter 用 \\r 连接。

    结构：
      段1（标题行）: "● 致命 · 一致性"  ← 彩色●（继承标题色）+ severity + 中文类型（上色加粗）
      段2..N（正文）: comment_text 按换行拆分，完整不截断
      末段（可选）  : "→ 建议改为：xxx"  ← action=replace 且建议非空时附

    设计目标：醒目清楚；不截断（完整优先），靠模块/AI 用词简洁控制篇幅。
    标记用基础字符 ●（不用彩色 emoji，避免字体兼容问题），颜色由 severity 决定。
    """
    mark = SEVERITY_MARK
    label = issue_type_label(issue.issue_type)
    title = f"{mark} {issue.severity} · {label}"
    paragraphs = [title]

    # 正文：按换行拆分，完整渲染不截断；直引号归一化为中文弯引号
    body = (issue.comment_text or "").strip()
    if body:
        for line in body.split("\n"):
            line = line.strip()
            if line:
                paragraphs.append(normalize_cn_quotes(line))

    # 建议文本（action=replace 且 comment_text 未明显含建议时附，完整不截断）
    if issue.action == "replace" and issue.suggested_text:
        sug = normalize_cn_quotes(issue.suggested_text.replace("\n", " ").strip())
        if sug and sug not in body:
            paragraphs.append(f"→ 建议改为：{sug}")

    return paragraphs


def comment_text_for_com(issue: Issue) -> str:
    """COM Comments.Add 需要 string：段落用 \\r 连接"""
    return "\r".join(format_comment(issue))


# =============================================================================
# Step 1: DocReader
# =============================================================================

class DocReader:
    """使用 python-docx 读取 .docx，提取文本和位置映射"""

    # 实体提取正则
    RE_CASE_NO = re.compile(r'\(?\d{4}[^)]*?\d+(?:字|民|行|刑|知|商|行商|商初|民初|民终|民商|行初|行终|执)[^\)]*?号\)?')
    RE_DATE = re.compile(r'\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|[一二三四五六七八九十零〇]+年[一二三四五六七八九十零〇]+月[一二三四五六七八九十零〇]+日|\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}')
    RE_AMOUNT = re.compile(r'(?:[¥￥]\s*[\d,]+\.?\d*\s*(?:元|万元|亿)?|[\d,]+\.?\d*\s*(?:元|万元|亿)|人民币\s*[壹贰叁肆伍陆柒捌玖拾佰仟万亿零整]+元?)')
    RE_LAW_ARTICLE = re.compile(r'[《]?\s*[\u4e00-\u9fff]+(?:法|条例|规定|解释|细则)\s*》?\s*第[一二三四五六七八九十百千零〇\d]+条(?:第[一二三四五六七八九十百千零〇\d]+款(?:第[一二三四五六七八九十百千零〇\d]+项)?)?')
    RE_EVIDENCE = re.compile(r'证据[一二三四五六七八九十\d]+|附件[一二三四五六七八九十\d]+')
    RE_COURT = re.compile(r'\S+人民法院|\S+中级人民?法院|\S+基层人民?法院|\S+知识产权法院')

    def read(self, docx_path: str) -> DocContent:
        """读取 .docx 文件，返回结构化内容"""
        doc = docx.Document(docx_path)
        content = DocContent()

        # 提取正文段落
        for i, para in enumerate(doc.paragraphs, start=1):
            text = para.text.strip()
            if text:
                content.paragraphs.append(ParagraphInfo(text=text, index=i, style=para.style.name if para.style else ""))

        # 提取表格单元格
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    text = cell.text.strip()
                    if text:
                        content.tables.append(CellInfo(text=text, row=r_idx, col=c_idx, table_idx=t_idx))

        # 提取页眉页脚
        for s_idx, section in enumerate(doc.sections):
            if section.header:
                for p_idx, para in enumerate(section.header.paragraphs, start=1):
                    text = para.text.strip()
                    if text:
                        content.headers.append(ParagraphInfo(text=text, index=p_idx, style=f"header_s{s_idx}"))
            if section.footer:
                for p_idx, para in enumerate(section.footer.paragraphs, start=1):
                    text = para.text.strip()
                    if text:
                        content.footers.append(ParagraphInfo(text=text, index=p_idx, style=f"footer_s{s_idx}"))

        # 构建全文文本（用于实体提取和 LLM 分析）
        all_texts = []
        for p in content.paragraphs:
            all_texts.append(f"[§{p.index}] {p.text}")
        for c in content.tables:
            all_texts.append(f"[表{c.table_idx + 1}-R{c.row + 1}C{c.col + 1}] {c.text}")
        content.raw_full_text = "\n".join(all_texts)

        # 实体提取
        content.entity_index = self._extract_entities(content)

        logger.info(f"读取完成: {len(content.paragraphs)} 段落, {len(content.tables)} 表格单元格, "
                     f"{len(content.headers)} 页眉, {len(content.footers)} 页脚")
        return content

    def _extract_entities(self, content: DocContent) -> dict[str, list[dict]]:
        """从全文提取实体"""
        all_text = content.raw_full_text
        entities: dict[str, list[dict]] = {}

        # 按段落查找实体位置
        for para in content.paragraphs:
            paras = [{"index": para.index, "type": "paragraph"}]
            for cell in content.tables:
                paras.append({"index": cell.table_idx, "row": cell.row, "col": cell.col, "type": "table_cell"})

        # 从所有文本中提取
        self._extract_from_text(all_text, entities, "案号/编号", self.RE_CASE_NO)
        self._extract_from_text(all_text, entities, "日期", self.RE_DATE)
        self._extract_from_text(all_text, entities, "金额", self.RE_AMOUNT)
        self._extract_from_text(all_text, entities, "法条引用", self.RE_LAW_ARTICLE)
        self._extract_from_text(all_text, entities, "证据/附件", self.RE_EVIDENCE)
        self._extract_from_text(all_text, entities, "法院", self.RE_COURT)

        return entities

    def _extract_from_text(self, text: str, entities: dict, entity_type: str, pattern: re.Pattern):
        """使用正则提取实体并记录位置"""
        for m in pattern.finditer(text):
            value = m.group()
            # 计算所在段落
            before = text[:m.start()]
            para_num = before.count("[§") + 1
            location = {"value": value, "position": m.span(), "para": para_num}
            entities.setdefault(entity_type, []).append(location)


# =============================================================================
# Step 2: 机械性规则检查（仅 M3/M4/M6/M8 — 可被 Python 正则/计算确定的问题）
# =============================================================================

class MechanicalChecker:
    """机械性规则检查引擎，仅含可被代码确定的问题（M3/M4/M6/M8）。
    语义判断（M1/M2/M5/M7）由 AI Agent 在外部完成并传入 Issue JSON。
    """

    DEFAULT_MODULES = ["M3", "M4", "M6", "M8"]

    def __init__(self, enabled_modules: list[str] | None = None):
        self.enabled_modules = enabled_modules or list(self.DEFAULT_MODULES)

    def check(self, content: DocContent) -> list[Issue]:
        """执行启用的机械检查模块"""
        from rules import MECHANICAL_REGISTRY

        all_issues: list[Issue] = []
        for module_id in self.enabled_modules:
            entry = MECHANICAL_REGISTRY.get(module_id)
            if entry:
                _, check_fn = entry
                try:
                    issues = check_fn(content)
                    all_issues.extend(issues)
                    logger.info(f"{module_id}: 发现 {len(issues)} 个问题")
                except Exception as e:
                    logger.error(f"{module_id} 检查失败: {e}")
        return all_issues


# =============================================================================
# Step 4: COMWriter / FallbackWriter
# =============================================================================

class COMWriter:
    """使用 Word COM API 写入 Track Changes + Comments"""

    def __init__(self, author: str = "文书校对助手"):
        self.author = author
        self._word = None

    def write(self, docx_path: str, issues: list[Issue], output_path: str):
        """打开文档、写入修订、保存"""
        import win32com.client

        # 清理合并同位置问题
        merged = merge_same_location(issues)

        self._word = win32com.client.Dispatch("Word.Application")
        self._word.Visible = False
        self._word.DisplayAlerts = 0  # wdAlertsNone

        try:
            doc = self._word.Documents.Open(os.path.abspath(docx_path))
            doc.TrackRevisions = True

            # 按 para_index 降序修改（避免位置偏移）
            merged_sorted = sorted(merged, key=lambda i: (i.para_index, i.start_offset), reverse=True)

            for issue in merged_sorted:
                rng = self._locate_range(doc, issue)
                if rng is None:
                    logger.warning(f"无法定位: {issue.issue_type} @ para {issue.para_index}")
                    continue

                # 确认原文匹配（COM 全局段落编号含表格内段落，python-docx 编号不含，
                # 表格前置文档可能错位——不匹配时跳过修订只留批注，与 OOXML Writer 行为对齐，
                # 避免在整段/整格 Range 上误删）
                rng_text = rng.Text
                matched = bool(issue.original_text) and issue.original_text in rng_text
                if matched:
                    # 精确定位到原文位置
                    offset = rng_text.index(issue.original_text)
                    target = rng.Duplicate
                    target.Start = rng.Start + offset
                    target.End = target.Start + len(issue.original_text)
                    rng = target
                else:
                    if issue.action in ("replace", "delete"):
                        logger.warning(
                            f"原文不匹配，跳过修订仅留批注: {issue.issue_type} @ para {issue.para_index}")

                # 执行操作（原文不匹配时不做 replace/delete，防止整段误删）
                if matched and issue.action == "replace" and issue.suggested_text:
                    target = rng
                    target.Delete()
                    target.InsertAfter(issue.suggested_text)
                elif matched and issue.action == "delete":
                    rng.Delete()

                # 添加批注（结构化格式：标题行 + 分段正文 + 建议）
                if issue.comment_text or issue.suggested_text:
                    comment = rng.Comments.Add(rng, comment_text_for_com(issue))
                    # 标题行配色 + 加粗（首段，按 severity 上色）
                    try:
                        title_para = comment.Range.Paragraphs(1)
                        title_para.Range.Font.Color = severity_rgb_int(issue.severity)
                        title_para.Range.Font.Bold = True
                    except Exception as e:
                        logger.debug(f"COM 批注标题配色失败: {e}")

            doc.SaveAs2(os.path.abspath(output_path))
            doc.Close(False)
            logger.info(f"COM 写入完成: {len(merged_sorted)} 个问题已写入 {output_path}")
        finally:
            if self._word:
                self._word.Quit()

    def _locate_range(self, doc, issue: Issue):
        """根据 Issue 定位 Word Range"""
        try:
            if issue.location_type == "paragraph":
                return doc.Paragraphs(issue.para_index).Range
            elif issue.location_type == "table_cell" and issue.cell_ref:
                t, r, c = issue.cell_ref
                return doc.Tables(t + 1).Cell(r + 1, c + 1).Range
            elif issue.location_type == "header":
                return doc.Sections(1).Headers(1).Range.Paragraphs(issue.para_index).Range
            elif issue.location_type == "footer":
                return doc.Sections(1).Footers(1).Range.Paragraphs(issue.para_index).Range
        except Exception as e:
            logger.warning(f"定位失败 para={issue.para_index}: {e}")
            return None


class FallbackWriter:
    """末位降级方案：使用 docx-revisions 写入 Track Changes（无 Word 原生批注）

    仅当 COMWriter 与 OOXMLWriter 均不可用时启用。Comments 降级为汇总表。
    """

    def write(self, docx_path: str, issues: list[Issue], output_path: str):
        """使用 docx-revisions 写入 Track Changes，Comments 降级为汇总表"""
        try:
            from docx_revisions import Revision
            rev = Revision(docx_path)
            merged = merge_same_location(issues)

            for issue in reversed(merged):
                if issue.action in ("replace", "delete") and issue.original_text:
                    rev.replace_text(issue.original_text, issue.suggested_text or "")

            rev.save(output_path)
            logger.info(f"docx-revisions 写入完成: {output_path}")
        except ImportError:
            logger.warning("docx-revisions 未安装，跳过 Track Changes 写入")

        # 在文档末尾添加汇总表
        self._append_summary_table(docx_path, output_path, issues)

    def _append_summary_table(self, docx_path: str, output_path: str, issues: list[Issue]):
        """在文档末尾追加校对汇总表"""
        doc = docx.Document(docx_path)
        doc.add_paragraph("")  # 空行分隔
        doc.add_paragraph("=== 文书校对汇总表（降级模式）===")

        severity_order = {"致命": 0, "严重": 1, "一般": 2}
        sorted_issues = sorted(issues, key=lambda i: (severity_order.get(i.severity, 3), i.para_index))

        for i, issue in enumerate(sorted_issues, 1):
            p = doc.add_paragraph()
            p.add_run(f"P{i} [{issue.issue_type}] [{issue.severity}] §{issue.para_index}\n").bold = True
            p.add_run(f"  问题: {issue.original_text}\n")
            p.add_run(f"  建议: {issue.suggested_text}\n")
            p.add_run(f"  说明: {issue.comment_text}\n")

        doc.save(output_path)


# =============================================================================
# Step 4: OOXMLWriter（纯 Python，词级 Track Changes + 原生 Comments）
# =============================================================================

class OOXMLWriter:
    """纯 Python OOXML 写入：词级 Track Changes（<w:ins>/<w:del>）+ 原生 Comments。

    无需 Word COM / pywin32，跨平台可用。基于 python-docx 1.2.0+ 的 lxml 层
    直接操作段落 XML，实现跨 run 的词级精确修订；批注通过 python-docx 原生
    add_comment（自动处理 comments.xml + Content_Types + relationships）。

    Vaquill 12 条避坑清单的实现位置：
      #1 删除用 w:delText  → _wrap_run_as_deletion()
      #3 w:id 文档级唯一   → self._rev_id_counter 单计数器
      #4 w:date ISO8601+Z  → self._date_iso
      #5 全部用 qn()       → 所有 set/itag
      #7 保留 xml:space    → _split_run / _make_insertion_element
      #8 倒序应用          → write() 中 reverse=True
      #10 trackChanges     → _ensure_track_changes()
      #11 不设修订样式     → w:del/w:ins 内不添 rPr 颜色
    """

    def __init__(self, author: str = "文书校对助手", initials: str = "校对"):
        self.author = author
        self.initials = initials
        self._rev_id_counter = 1000  # 修订 ID 起点（避开批注 ID 区间）
        self._date_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def write(self, docx_path: str, issues: list[Issue], output_path: str):
        """打开文档、写入词级修订+批注、保存。"""
        import shutil
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        shutil.copy2(docx_path, output_path)
        doc = docx.Document(output_path)

        merged = merge_same_location(issues)
        # 按 (para_index, start_offset) 降序处理，避免位置偏移
        merged_sorted = sorted(
            merged,
            key=lambda i: (i.para_index, i.start_offset),
            reverse=True,
        )

        ok_count = 0
        for issue in merged_sorted:
            if self._process_issue(doc, issue):
                ok_count += 1

        # settings.xml 启用 trackChanges（保证 Word 中可 Accept/Reject）
        self._ensure_track_changes(doc)

        doc.save(output_path)
        logger.info(f"OOXML 写入完成: {ok_count}/{len(merged_sorted)} 个问题 -> {output_path}")

    # ---------------- 位置定位 ----------------

    def _locate_paragraph(self, doc, issue: Issue):
        """根据 Issue 定位 python-docx Paragraph 对象。返回 Paragraph 或 None。

        注：header/footer 取第 1 个 section（与 COMWriter 一致）。
        """
        try:
            if issue.location_type == "paragraph":
                paras = doc.paragraphs
                if 1 <= issue.para_index <= len(paras):
                    return paras[issue.para_index - 1]
            elif issue.location_type == "table_cell" and issue.cell_ref:
                t_idx, r_idx, c_idx = issue.cell_ref
                if t_idx < len(doc.tables):
                    table = doc.tables[t_idx]
                    if r_idx < len(table.rows):
                        cell = table.rows[r_idx].cells[c_idx]
                        if cell.paragraphs:
                            return cell.paragraphs[0]
            elif issue.location_type == "header":
                if doc.sections:
                    hdr = doc.sections[0].header
                    idx = issue.para_index - 1
                    if 0 <= idx < len(hdr.paragraphs):
                        return hdr.paragraphs[idx]
            elif issue.location_type == "footer":
                if doc.sections:
                    ftr = doc.sections[0].footer
                    idx = issue.para_index - 1
                    if 0 <= idx < len(ftr.paragraphs):
                        return ftr.paragraphs[idx]
        except Exception as e:
            logger.warning(f"OOXML 定位失败 para={issue.para_index}: {e}")
        return None

    # ---------------- Run 切分（词级精确定位基础） ----------------

    def _split_at(self, paragraph, offset: int):
        """在段落字符偏移 offset 处确保 run 边界（若落在 run 中部则切分该 run）。"""
        from docx.oxml.ns import qn
        cum = 0
        for run in paragraph.runs:
            rlen = len(run.text or "")
            if 0 < offset - cum < rlen:
                self._split_run(run, offset - cum)
                return
            cum += rlen

    def _split_run(self, run, local_offset: int):
        """将 run 在 local_offset 处一分为二。原 run 保留前半，新增 run 含后半。"""
        from docx.oxml.ns import qn
        r_el = run._r
        full_text = run.text or ""
        if local_offset <= 0 or local_offset >= len(full_text):
            return
        left, right = full_text[:local_offset], full_text[local_offset:]
        t_els = r_el.findall(qn("w:t"))
        if not t_els:
            return
        # 原 run 保留 left 文本，删除多余 w:t
        t_els[0].text = left
        t_els[0].set(qn("xml:space"), "preserve")
        for extra in t_els[1:]:
            r_el.remove(extra)
        # 新 run 携带 right 文本（deepcopy 保留 rPr 格式）
        if right:
            new_r = deepcopy(r_el)
            new_t_els = new_r.findall(qn("w:t"))
            new_t_els[0].text = right
            new_t_els[0].set(qn("xml:space"), "preserve")
            for extra in new_t_els[1:]:
                new_r.remove(extra)
            r_el.addnext(new_r)

    def _collect_covering_runs(self, paragraph, start_off: int, end_off: int) -> list:
        """收集 [start_off, end_off) 范围内的 run 列表（基于直接子 run 偏移）。"""
        covering = []
        cum = 0
        for run in paragraph.runs:
            rlen = len(run.text or "")
            r_start, r_end = cum, cum + rlen
            if r_start < end_off and r_end > start_off:
                covering.append(run)
            cum = r_end
        return covering

    # ---------------- Track Changes 元素构造 ----------------

    def _wrap_run_as_deletion(self, run):
        """将 run 包裹进 <w:del>，并把 <w:t> 转为 <w:delText>（坑 #1）。返回 w:del 元素。"""
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        r_el = run._r
        del_el = OxmlElement("w:del")
        self._rev_id_counter += 1
        del_el.set(qn("w:id"), str(self._rev_id_counter))
        del_el.set(qn("w:author"), self.author)
        del_el.set(qn("w:date"), self._date_iso)
        r_el.addprevious(del_el)
        del_el.append(r_el)
        # 删除必须用 w:delText，否则 Word 静默丢弃
        for t in r_el.findall(qn("w:t")):
            t.tag = qn("w:delText")
        return del_el

    def _make_insertion_element(self, text: str, rpr_source_r=None):
        """构造 <w:ins><w:r><w:t>text</w:t></w:r></w:ins>。可选继承 rPr 格式。"""
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        ins_el = OxmlElement("w:ins")
        self._rev_id_counter += 1
        ins_el.set(qn("w:id"), str(self._rev_id_counter))
        ins_el.set(qn("w:author"), self.author)
        ins_el.set(qn("w:date"), self._date_iso)
        r = OxmlElement("w:r")
        if rpr_source_r is not None:
            rpr = rpr_source_r.find(qn("w:rPr"))
            if rpr is not None:
                r.append(deepcopy(rpr))  # 保留格式（坑 #6/#11：不设颜色，Word 控制）
        t = OxmlElement("w:t")
        t.text = text
        t.set(qn("xml:space"), "preserve")
        r.append(t)
        ins_el.append(r)
        return ins_el

    # ---------------- 批注 ----------------

    def _add_comment(self, doc, issue: Issue, covering_runs: list):
        """通过 python-docx 原生 add_comment 添加结构化批注。

        批注仅支持 document part（paragraph / table_cell）；header/footer 跳过。
        多段落正文用 Comment.add_paragraph() 逐段添加。
        """
        if not covering_runs:
            return
        try:
            paras_text = format_comment(issue)
            title = paras_text[0] if paras_text else ""
            body_lines = paras_text[1:]
            comment = doc.add_comment(
                covering_runs,
                text=title,
                author=self.author,
                initials=self.initials,
            )
            try:
                comment.timestamp = self._date_iso
            except Exception:
                pass
            # 标题行配色 + 加粗（按 severity 上色，首段所有 run）
            rgb = SEVERITY_COLOR_RGB.get(issue.severity)
            if rgb and comment.paragraphs:
                from docx.shared import RGBColor
                for run in comment.paragraphs[0].runs:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(*rgb)
            for line in body_lines:
                comment.add_paragraph(line)
        except Exception as e:
            logger.warning(f"OOXML 批注添加失败 [{issue.issue_type}]: {e}")

    # ---------------- settings.xml ----------------

    def _ensure_track_changes(self, doc):
        """确保 settings.xml 含 <w:trackChanges/>（保证文件可 Accept/Reject）。"""
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        try:
            settings = doc.settings.element
            if settings.find(qn("w:trackChanges")) is None:
                settings.append(OxmlElement("w:trackChanges"))
        except Exception as e:
            logger.warning(f"trackChanges 设置失败: {e}")

    # ---------------- 单 Issue 处理 ----------------

    def _process_issue(self, doc, issue: Issue) -> bool:
        """处理单个 Issue：切分 run → 批注（先）→ Track Changes（后）。
        返回是否成功处理。"""
        para = self._locate_paragraph(doc, issue)
        if para is None:
            logger.warning(f"OOXML 无法定位: {issue.issue_type} @ para {issue.para_index}")
            return False

        # 切分 run，使 [start, end) 对齐 run 边界
        start_off, end_off = issue.start_offset, issue.end_offset
        if end_off > start_off:
            self._split_at(para, start_off)
            self._split_at(para, end_off)
        covering_runs = self._collect_covering_runs(para, start_off, end_off)

        # 原文校验：covering_runs 拼接文本应等于 original_text（避免偏移错位破坏文档）
        if issue.original_text and covering_runs:
            joined = "".join(r.text or "" for r in covering_runs)
            if joined != issue.original_text:
                logger.warning(
                    f"OOXML 原文不匹配，跳过修订 [{issue.issue_type}]: "
                    f"期望 {issue.original_text!r} / 实际 {joined!r}"
                )
                covering_runs = []  # 仅尝试批注，不修订

        # 批注优先（comment range 标记落在外层，避免嵌入 w:del 内部导致结构损坏）
        has_comment = bool(issue.comment_text or (issue.action == "replace" and issue.suggested_text))
        if has_comment and issue.location_type in ("paragraph", "table_cell"):
            anchor = covering_runs if covering_runs else list(para.runs)
            if anchor:
                self._add_comment(doc, issue, anchor)

        # Track Changes
        if issue.action in ("replace", "delete") and covering_runs and issue.original_text:
            last_del = None
            rpr_source = covering_runs[0]._r
            for run in covering_runs:
                last_del = self._wrap_run_as_deletion(run)
            if issue.action == "replace" and issue.suggested_text and last_del is not None:
                ins_el = self._make_insertion_element(issue.suggested_text, rpr_source)
                last_del.addnext(ins_el)

        return True


# =============================================================================
# Proofreader 主类
# =============================================================================

class Proofreader:
    """文书校对主入口

    工作流程：
    1. check_mechanical() — Python 机械检查（M3/M4/M6/M8）
    2. AI Agent 语义审查（M1/M2/M5/M7）— 外部完成，通过 JSON 传入
    3. check_full() — 合并机械 + 语义 Issue
    4. write_revisions() — COMWriter 写入 Track Changes + Comments
    """

    MECHANICAL_MODULES = ["M3", "M4", "M6", "M8"]
    SEMANTIC_MODULES = ["M1", "M2", "M5", "M7"]
    ALL_MODULES = MECHANICAL_MODULES + SEMANTIC_MODULES

    def __init__(self, config: dict | None = None):
        self.config = config or {
            "use_com": True,
            "comment_author": "文书校对助手",
            "include_module_summary": True,
        }
        self.reader = DocReader()
        self.mechanical_checker = MechanicalChecker(self.MECHANICAL_MODULES)

    def check_mechanical(self, docx_path: str) -> list[Issue]:
        """执行机械性检查（Step 1 + Step 2），返回 Issue 列表"""
        content = self.reader.read(docx_path)
        return self.mechanical_checker.check(content)

    def check_full(self, docx_path: str, ai_issues: list[Issue] | None = None,
                   ai_issues_json: str | None = None,
                   mech_issues_json: str | None = None) -> list[Issue]:
        """完整检查：机械检查 + AI Agent 语义审查

        Args:
            docx_path: 输入文件路径
            ai_issues: AI Agent 语义审查 Issue 列表（直接传入）
            ai_issues_json: AI Agent 语义审查结果 JSON 文件路径
            mech_issues_json: 预先导出的机械检查结果 JSON（2026-09-07 C2 新增：
                提供时跳过 Step 2 机械检查直接复用，配合 --mechanical-only --export-json 工作流）

        Returns:
            合并去重后的全部 Issue
        """
        if mech_issues_json:
            mech_issues = self.load_issues_from_json(mech_issues_json)
            logger.info(f"复用机械检查结果: {len(mech_issues)} 个 Issue 来自 {mech_issues_json}")
        else:
            mech_issues = self.check_mechanical(docx_path)

        semantic_issues: list[Issue] = []
        if ai_issues:
            semantic_issues = ai_issues
        elif ai_issues_json:
            semantic_issues = self.load_issues_from_json(ai_issues_json)

        all_issues = mech_issues + semantic_issues
        all_issues = self._deduplicate(all_issues)

        logger.info(f"校对完成: 机械 {len(mech_issues)} + 语义 {len(semantic_issues)} "
                     f"= 去重后 {len(all_issues)} 个问题")
        return all_issues

    def write_revisions(self, docx_path: str, issues: list[Issue], output_path: str | None = None):
        """按 config['write_mode'] 选择写入路径：com / ooxml / auto。

        - com：Word COM（失败直接抛异常）
        - ooxml：纯 Python OOXML（失败直接抛异常）
        - auto：OOXML → COM → FallbackWriter 三级降级
          （2026-09-07 倒置：实测 OOXML 写入约 0.19s，COM 因 Word 进程启动开销约 7.6s；
          OOXML 失败（结构异常/覆盖 runs 文本不匹配）才降级 COM。COM 降级保留作兜底与渲染验证。）
        """
        if output_path is None:
            p = Path(docx_path)
            output_path = str(p.parent / f"{p.stem}_校对{p.suffix}")

        mode = self.config.get("write_mode", "auto")
        author = self.config.get("comment_author", "文书校对助手")

        if mode in ("ooxml", "auto"):
            try:
                writer = OOXMLWriter(author=author)
                writer.write(docx_path, issues, output_path)
                return
            except Exception as e:
                if mode == "ooxml":
                    raise
                logger.warning(f"OOXML 路径失败，尝试 COM 降级: {e}")

        if mode in ("com", "auto"):
            try:
                writer = COMWriter(author=author)
                writer.write(docx_path, issues, output_path)
                return
            except Exception as e:
                if mode == "com":
                    raise
                logger.warning(f"COM 路径失败，尝试末位降级: {e}")

        # 末位降级：docx-revisions + 汇总表
        writer = FallbackWriter()
        writer.write(docx_path, issues, output_path)

    @staticmethod
    def load_issues_from_json(json_path: str) -> list[Issue]:
        """从 JSON 文件加载 AI Agent 语义审查 Issue 列表"""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        issues = []
        for item in data:
            issues.append(Issue(
                location_type=item.get("location_type", "paragraph"),
                para_index=item["para_index"],
                cell_ref=tuple(item["cell_ref"]) if item.get("cell_ref") else None,
                start_offset=item["start_offset"],
                end_offset=item["end_offset"],
                issue_type=item["issue_type"],
                severity=item["severity"],
                action=item["action"],
                original_text=item.get("original_text", ""),
                suggested_text=item.get("suggested_text", ""),
                comment_text=item.get("comment_text", ""),
            ))
        logger.info(f"加载 AI 语义审查结果: {len(issues)} 个 Issue 来自 {json_path}")
        return issues

    @staticmethod
    def save_issues_to_json(issues: list[Issue], json_path: str):
        """将 Issue 列表导出为 JSON（供 AI Agent 读取机械检查结果后追加语义 Issue）"""
        data = [i.to_dict() for i in issues]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Issue 列表已导出: {len(issues)} 条 → {json_path}")

    @staticmethod
    def _deduplicate(issues: list[Issue]) -> list[Issue]:
        """按位置+类型去重"""
        seen = set()
        result = []
        for issue in issues:
            key = (issue.location_type, issue.para_index, issue.start_offset, issue.issue_type)
            if key not in seen:
                seen.add(key)
                result.append(issue)
        return result


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="文书细节校对 v2")
    parser.add_argument("input", help="输入 .docx 文件路径")
    parser.add_argument("-o", "--output", help="输出文件路径（默认：原文件名_校对.docx）")
    parser.add_argument("--mechanical-only", action="store_true",
                        help="仅执行机械检查（M3/M4/M6/M8），跳过 AI 语义审查（默认不写文件，加 --write 生成修订文档）")
    parser.add_argument("--issues-json", help="AI Agent 语义审查结果 JSON 文件路径")
    parser.add_argument("--mech-json", help="复用预导出的机械检查结果 JSON，跳过 Step 2（配合 --mechanical-only --export-json 工作流）")
    parser.add_argument("--write", action="store_true",
                        help="机械检查模式下显式写出修订文件（默认不写，2026-09-07 行为变更）")
    parser.add_argument("--mode", choices=["com", "ooxml", "auto"], default="auto",
                        help="写入模式: com=Word COM, ooxml=纯Python词级修订, auto=自动降级(ooxml→com→汇总表)")
    parser.add_argument("--no-com", action="store_true",
                        help="（已弃用，等价于 --mode ooxml）禁用 Word COM")
    parser.add_argument("--author", default="文书校对助手", help="批注作者名称")
    parser.add_argument("--export-json", help="将机械检查结果导出为 JSON（供 AI Agent 参考）")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    # 模式解析：--no-com 兼容旧用法（等价 --mode ooxml）
    if args.no_com:
        write_mode = "ooxml"
    else:
        write_mode = args.mode

    proofreader = Proofreader(config={
        "write_mode": write_mode,
        "comment_author": args.author,
    })

    # 确定检查模式
    if args.issues_json and not args.mechanical_only:
        # 完整模式：机械 + AI 语义
        issues = proofreader.check_full(args.input, ai_issues_json=args.issues_json,
                                        mech_issues_json=args.mech_json)
    elif args.mechanical_only:
        # 仅机械检查
        issues = proofreader.check_mechanical(args.input)
        if args.export_json:
            Proofreader.save_issues_to_json(issues, args.export_json)
    else:
        # 默认：机械检查（无 AI 语义 Issue 时等同于 mechanical-only）
        logger.warning("未指定 --issues-json 或 --mechanical-only，默认执行机械检查")
        issues = proofreader.check_mechanical(args.input)

    # 输出摘要
    fatal = sum(1 for i in issues if i.severity == "致命")
    severe = sum(1 for i in issues if i.severity == "严重")
    normal = sum(1 for i in issues if i.severity == "一般")
    print(f"\n校对完成: 致命 {fatal} / 严重 {severe} / 一般 {normal}")

    if issues:
        for i, issue in enumerate(issues, 1):
            print(f"  P{i} [{issue.severity}][{issue.issue_type}] §{issue.para_index}: {issue.comment_text[:80]}")

    # 2026-09-07（B4）：机械检查模式默认不写文件（--write 显式开启）；
    # --export-json 与写文件解耦，导出 JSON 不再隐含生成 docx。
    mechanical_mode = args.mechanical_only or not args.issues_json
    if mechanical_mode and not args.write:
        print("\n机械检查模式未写修订文件（加 --write 可生成修订文档）")
        return

    proofreader.write_revisions(args.input, issues, args.output)
    print(f"\n修订文件已保存")


if __name__ == "__main__":
    main()
