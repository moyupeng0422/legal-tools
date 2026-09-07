"""M5: 法律术语/错别字

检测易混法律术语误用、常见错别字、律师文书常见语病。
规则详见 references/05-legal-terms.md

纯规则部分（错别字/术语）在此执行，语病检测需 LLM 辅助。
"""

from __future__ import annotations

import re


# 术语替换表：(错误用法, 正确用法, 严重等级, 说明)
TERM_PAIRS = [
    ("定金", "", "严重", "请确认此处'定金'（担保性质，违约适用定金罚则）是否为'订金'（预付款性质），二者法律后果完全不同"),
    ("法人代表", "法定代表人", "严重", "法人指组织本身，法定代表人是自然人"),
    ("抵押物权", "抵押权", "严重", "动产和权利应使用'质押'"),
    ("专利权人", "专利申请人", "严重", "权利人可能不是申请人"),
    ("执行异议之诉", "执行异议", "严重", "前者是诉讼，后者是程序行为"),
]

# 错别字表：(错误, 正确)
TYPO_PAIRS = [
    ("赔尝", "赔偿"),
    ("委拖", "委托"),
    ("起述", "起诉"),
]


def check(content) -> list:
    """
    执行 M5 法律术语/错别字检查。

    Args:
        content: DocContent 对象

    Returns:
        list[Issue]
    """
    from checker import Issue

    issues = []
    issues.extend(_check_terms(content))
    issues.extend(_check_typos(content))
    return issues


def _check_terms(content) -> list[Issue]:
    """检查法律术语误用"""
    issues = []
    for para in content.paragraphs:
        for wrong, right, severity, desc in TERM_PAIRS:
            if wrong in para.text:
                idx = para.text.index(wrong)
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=idx,
                    end_offset=idx + len(wrong),
                    issue_type="M5_术语",
                    severity=severity,
                    action="comment_only",
                    original_text=wrong,
                    suggested_text="",
                    comment_text=f"[M5] 疑似术语问题：'{wrong}'——{desc}",
                ))
    return issues


def _check_typos(content) -> list[Issue]:
    """检查错别字"""
    issues = []
    for para in content.paragraphs:
        for wrong, right in TYPO_PAIRS:
            if wrong in para.text:
                idx = para.text.index(wrong)
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=idx,
                    end_offset=idx + len(wrong),
                    issue_type="M5_错别字",
                    severity="严重",
                    action="replace",
                    original_text=wrong,
                    suggested_text=right,
                    comment_text=f"[M5] 错别字：'{wrong}'→'{right}'",
                ))
    return issues
