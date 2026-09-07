"""M2: 全文一致性（含企业名称核验）

检查同一实体在全文各处的表述是否一致。
规则详见 references/02-consistency.md
"""

from __future__ import annotations

import re


def check(content) -> list:
    """
    执行 M2 全文一致性检查。

    分两步：
    2a 文内一致性（纯文本）：字符级别比对
    2b 企业名称核验：需外部 MCP（占位，返回需核验的企业列表）

    Args:
        content: DocContent 对象

    Returns:
        list[Issue]
    """
    from checker import Issue

    issues = []
    entity_index = content.entity_index

    for entity_type in ["当事人名称", "案号/编号", "日期", "法院", "金额", "法条引用", "证据/附件"]:
        locations = entity_index.get(entity_type, [])
        if len(locations) < 2:
            continue

        # 提取唯一值
        value_groups = {}
        for loc in locations:
            value = loc["value"]
            value_groups.setdefault(value, []).append(loc)

        unique_values = list(value_groups.keys())
        if len(unique_values) <= 1:
            continue  # 完全一致

        # 日期特殊处理：不同格式但同一日期不算不一致
        if entity_type == "日期":
            normalized = {}
            for v in unique_values:
                norm = _normalize_date(v)
                normalized.setdefault(norm, []).append(v)
            if len(normalized) <= 1:
                continue
            unique_values = list(normalized.keys())

        # 取最常出现（出现次数最多的）作为基准
        base_value = max(unique_values, key=lambda v: len(value_groups[v]))

        for variant in unique_values:
            if variant == base_value:
                continue

            # 判断是否为合法变体
            if _is_legal_variant(content, entity_type, base_value, variant):
                continue

            severity = _get_severity(entity_type)
            action = "replace" if entity_type not in ("证据/附件",) else "comment_only"

            suggested = base_value if action == "replace" else ""
            for loc in value_groups[variant]:
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=loc.get("para", 0),
                    cell_ref=loc.get("cell_ref"),
                    start_offset=0,
                    end_offset=len(variant),
                    issue_type=f"M2_一致性",
                    severity=severity,
                    action=action,
                    original_text=variant,
                    suggested_text=suggested,
                    comment_text=(
                        f"[M2] {entity_type}表述不一致：此处为'{variant}'，其他位置为'{base_value}'。请统一。"
                    ),
                ))

    return issues


def _normalize_date(date_str: str) -> str:
    """将日期标准化为 YYYY-MM-DD"""
    patterns = [
        (re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日'), r'\1-\2-\3'),
        (re.compile(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})'), r'\1-\2-\3'),
    ]
    for pattern, fmt in patterns:
        m = pattern.search(date_str)
        if m:
            return fmt.replace(r'\2', m.group(2).zfill(2)).replace(r'\3', m.group(3).zfill(2))
    return date_str


def _is_legal_variant(content, entity_type: str, base: str, variant: str) -> bool:
    """判断变体是否为合法"""
    # 简称模式：文档中定义了简称
    abbrev = re.search(
        rf'(?:以下简称|简称|以下称)[\'""]({re.escape(variant)}|{re.escape(base[:4])}[^\'"\'"]+)[\'""]',
        content.raw_full_text
    )
    if abbrev:
        return True

    # 法律名称标准简称
    law_abbrevs = {
        "中华人民共和国民法典": "民法典",
        "中华人民共和国专利法": "专利法",
        "中华人民共和国商标法": "商标法",
        "中华人民共和国著作权法": "著作权法",
        "中华人民共和国民事诉讼法": "民事诉讼法",
    }
    if base in law_abbrevs and variant == law_abbrevs[base]:
        return True

    return False


def _get_severity(entity_type: str) -> str:
    """根据实体类型确定严重等级"""
    high_severity = ("案号/编号", "当事人名称", "法院")
    medium_severity = ("金额", "法条引用")
    return "严重" if entity_type in high_severity else "严重"
