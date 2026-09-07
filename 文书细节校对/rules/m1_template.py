"""M1: 模板残留检测

检测以旧文件为模板修改时未替换或删除的内容。
规则详见 references/01-template-residue.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TemplateResidueSignal:
    """模板残留信号"""
    signal_type: str
    description: str
    confidence: str  # "高" | "中"
    severity: str     # "致命" | "严重"


SIGNALS = [
    TemplateResidueSignal(
        signal_type="名称不一致",
        description="当事人名称在当事人列表和事实描述中出现不同版本",
        confidence="高",
        severity="致命",
    ),
    TemplateResidueSignal(
        signal_type="日期年份不匹配",
        description="日期年份与案号年份不匹配",
        confidence="高",
        severity="严重",
    ),
    TemplateResidueSignal(
        signal_type="孤立金额",
        description="金额仅出现一次且与其他金额无计算关系",
        confidence="中",
        severity="严重",
    ),
    TemplateResidueSignal(
        signal_type="无关名称片段",
        description="存在其他常见当事人名称的字样片段",
        confidence="中",
        severity="严重",
    ),
    TemplateResidueSignal(
        signal_type="无关日期",
        description="文中有签订日期但与本案无逻辑关联",
        confidence="中",
        severity="严重",
    ),
]


def check(content) -> list:
    """
    执行 M1 模板残留检测。

    Args:
        content: DocContent 对象

    Returns:
        list[Issue]
    """
    from checker import Issue

    issues = []
    entity_index = content.entity_index

    # 1. 从当事人定义中提取基准名称
    party_names = _extract_party_names(content)
    if not party_names:
        return issues

    # 2. 在全文中查找基准名称的变体
    for canonical_name, canonical_locations in party_names.items():
        variants = _find_name_variants(content, canonical_name)
        if not variants:
            continue

        for variant in variants:
            if variant == canonical_name:
                continue  # 跳过完全一致的

            # 检查是否为合法简称
            if _is_legitimate_abbreviation(content, canonical_name, variant):
                continue

            # 发现不一致
            for loc in _find_variant_locations(content, variant):
                severity = "致命" if len(canonical_name) > 6 else "严重"
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=loc["para"],
                    cell_ref=loc.get("cell_ref"),
                    start_offset=loc.get("start", 0),
                    end_offset=loc.get("end", len(variant)),
                    issue_type="M1_模板残留",
                    severity=severity,
                    action="comment_only",
                    original_text=variant,
                    suggested_text=canonical_name,
                    comment_text=(
                        f"[M1] 疑似模板残留：当事人名称不一致。"
                        f"此处为'{variant}'，首部定义为'{canonical_name}'。"
                        f"请核实是否为旧模板未替换。"
                    ),
                ))

    # 3. 检查日期年份与案号年份
    case_years = _extract_case_years(content)
    dates = entity_index.get("日期", [])
    for date_loc in dates:
        year = _extract_year(date_loc["value"])
        if year and case_years:
            for case_year in case_years:
                if abs(year - case_year) >= 3 and year < case_year:
                    issues.append(Issue(
                        location_type="paragraph",
                        para_index=date_loc.get("para", 0),
                        cell_ref=None,
                        start_offset=0,
                        end_offset=0,
                        issue_type="M1_模板残留",
                        severity="严重",
                        action="comment_only",
                        original_text=date_loc["value"],
                        comment_text=(
                            f"[M1] 疑似旧日期残留：日期{year}年与案号年份{case_year}年相差较大，"
                            f"且日期早于案号年份。请核实是否为旧模板日期。"
                        ),
                    ))

    return issues


def _extract_party_names(content) -> dict[str, list]:
    """从文档首部提取当事人名称定义"""
    names = {}
    patterns = [
        re.compile(r'(?:原告|申请人|上诉人|申诉人|甲方|原告方|申请执行人)[：:]\s*(.{4,30})(?:\s*（.*?）)?\s*$'),
        re.compile(r'(?:被告|被申请人|被上诉人|被申诉人|乙方|被告方)[：:]\s*(.{4,30})(?:\s*（.*?）)?\s*$'),
    ]
    for para in content.paragraphs[:15]:
        for pattern in patterns:
            m = pattern.match(para.text.strip())
            if m:
                name = m.group(1).strip().rstrip("，。,.")
                names.setdefault(name, []).append({"para": para.index, "text": para.text[:100]})
    return names


def _find_name_variants(content, base_name: str) -> list[str]:
    """查找基准名称在全文中的变体"""
    # 提取核心关键词（去掉常见后缀）
    core = re.sub(r'(有限公司|有限责任公司|股份有限公司|集团)', '', base_name)
    if len(core) < 4:
        return []

    variants = set()
    # 搜索包含核心关键词的段落
    for para in content.paragraphs:
        if core in para.text:
            # 提取该段落中所有可能的名称
            name_pattern = re.compile(r'[\u4e00-\u9fff（）()]{4,30}')
            for m in name_pattern.finditer(para.text):
                candidate = m.group().strip()
                if core in candidate and candidate != base_name:
                    variants.add(candidate)
    return list(variants)[:10]  # 限制变体数量


def _is_legitimate_abbreviation(content, full_name: str, variant: str) -> bool:
    """检查变体是否为合法简称（如首次定义的简称）"""
    # 检查文档中是否有"以下简称'XXX'"的定义
    abbrev_pattern = re.compile(r"(?:以下简称|简称|以下称)[\u2018\u201c\u2018\u0027\u0022]([^\u2019\u201d\u2019\u0027\u0022]+)[\u2019\u201d\u2019\u0027\u0022]")
    for para in content.paragraphs:
        m = abbrev_pattern.search(para.text)
        if m and m.group(1) in variant:
            return True

    # 检查是否为标准法律简称
    standard_abbrevs = ["最高人民法院", "最高法院", "国知局", "知识产权局"]
    if variant in standard_abbrevs:
        return True

    return False


def _find_variant_locations(content, variant: str) -> list[dict]:
    """查找变体在文档中的出现位置"""
    locations = []
    for para in content.paragraphs:
        idx = para.text.find(variant)
        if idx >= 0:
            locations.append({"para": para.index, "start": idx, "end": idx + len(variant)})
    # 也检查表格
    for cell in content.tables:
        idx = cell.text.find(variant)
        if idx >= 0:
            locations.append({"para": 0, "cell_ref": (cell.table_idx, cell.row, cell.col), "start": idx, "end": idx + len(variant)})
    return locations


def _extract_case_years(content) -> list[int]:
    """从实体索引中提取案号年份"""
    years = []
    for loc in content.entity_index.get("案号/编号", []):
        m = re.search(r'\((\d{4})\)', loc["value"])
        if m:
            years.append(int(m.group(1)))
    return years


def _extract_year(date_str: str) -> int | None:
    """从日期字符串提取年份"""
    m = re.search(r'(\d{4})', date_str)
    return int(m.group(1)) if m else None
