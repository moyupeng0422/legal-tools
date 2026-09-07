"""M3: 法条校验

检查法条引用格式规范性和内容准确性。
规则详见 references/03-law-articles.md

3a 格式校验（纯文本）
3b 内容校验（需法律法规库 MCP）
"""

from __future__ import annotations

import re


def check(content) -> list:
    """
    执行 M3 法条校验。

    Args:
        content: DocContent 对象

    Returns:
        list[Issue]
    """
    from checker import Issue

    issues = []
    issues.extend(_check_format(content))
    # 3b 内容校验需要外部 MCP，暂仅做格式校验
    return issues


def _check_format(content) -> list[Issue]:
    """3a 格式校验"""
    from checker import Issue
    issues = []

    # 法律名称不完整（首次引用）
    full_name_required = {
        "专利法": "中华人民共和国专利法",
        "商标法": "中华人民共和国商标法",
        "著作权法": "中华人民共和国著作权法",
        "民法典": "中华人民共和国民法典",
        "民事诉讼法": "中华人民共和国民事诉讼法",
        "行政诉讼法": "中华人民共和国行政诉讼法",
        "刑法": "中华人民共和国刑法",
    }

    first_use_checked = set()
    for para in content.paragraphs:
        for short_name, full_name in full_name_required.items():
            pattern = re.compile(re.escape(short_name))
            for m in pattern.finditer(para.text):
                if short_name not in first_use_checked:
                    # 检查是否已有全称出现
                    full_found = full_name in content.raw_full_text
                    if not full_found and short_name in para.text:
                        issues.append(Issue(
                            location_type="paragraph",
                            para_index=para.index,
                            cell_ref=None,
                            start_offset=m.start(),
                            end_offset=m.start() + len(short_name),
                            issue_type="M3_法条格式",
                            severity="一般",
                            action="comment_only",
                            original_text=short_name,
                            suggested_text=full_name,
                            comment_text=f"[M3] 首次引用未使用法律全称：'{short_name}'应为'{full_name}'。",
                        ))
                    first_use_checked.add(short_name)

    # 条文编号格式：阿拉伯数字应为中文数字
    bad_format = re.compile(r'(?:第|条款第)\s*(\d+)\s*(?:条|款|项)')
    for para in content.paragraphs:
        for m in bad_format.finditer(para.text):
            num = int(m.group(1))
            chinese = _to_chinese_num(num)
            issues.append(Issue(
                location_type="paragraph",
                para_index=para.index,
                cell_ref=None,
                start_offset=m.start(),
                end_offset=m.start() + len(m.group()),
                issue_type="M3_法条格式",
                severity="严重",
                action="comment_only",
                original_text=m.group(),
                comment_text=f"[M3] 条文编号应使用中文数字：'{m.group()}'→'第{chinese}条'",
            ))

    return issues


def _to_chinese_num(n: int) -> str:
    """将阿拉伯数字转为中文数字（支持一至九百九十九）"""
    if n <= 0:
        return "零"
    if n <= 10:
        return "零一二三四五六七八九十"[n]
    if n < 20:
        return "十" + ("零一二三四五六七八九"[n % 10] if n % 10 else "")
    if n < 100:
        tens = n // 10
        ones = n % 10
        return f"{'零一二三四五六七八九'[tens]}十{'零一二三四五六七八九'[ones] if ones else ''}"
    if n < 1000:
        hundreds = n // 100
        rest = n % 100
        rest_str = _to_chinese_num(rest) if rest else ""
        rest_str = "零" + rest_str if rest and rest < 10 else rest_str
        return f"{'零一二三四五六七八九'[hundreds]}百{rest_str}"
    return str(n)
