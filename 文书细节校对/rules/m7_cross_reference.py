"""M7: 交叉引用完整性

检查证据/附件引用是否在全文中有对应定义，引用链是否完整。
规则详见 references/07-cross-reference.md
"""

from __future__ import annotations

import re


def check(content) -> list:
    """
    执行 M7 交叉引用完整性检查。

    Args:
        content: DocContent 对象

    Returns:
        list[Issue]
    """
    from checker import Issue

    issues = []
    issues.extend(_check_evidence_refs(content))
    issues.extend(_check_attachment_refs(content))
    issues.extend(_check_orphan_evidence(content))
    return issues


def _check_evidence_refs(content) -> list:
    """检查证据引用是否都有定义"""
    issues = []
    from checker import Issue

    # 提取证据引用：证据一、证据二、证据1、证据2 等
    ref_pattern = re.compile(r'证据[一二三四五六七八九十\d]+')
    # 提取证据定义：证据X：/证据X：/证据X为
    def_pattern = re.compile(r'证据[一二三四五六七八九十\d]+\s*[：:为]')

    refs = set()      # 被引用的证据
    defs = set()       # 有定义的证据

    for para in content.paragraphs:
        # 收集定义
        for m in def_pattern.finditer(para.text):
            defs.add(m.group().rstrip('：:为').rstrip())

        # 收集引用（排除定义行本身）
        lines = para.text.split('\n')
        for line in lines:
            is_def_line = bool(def_pattern.search(line))
            for m in ref_pattern.finditer(line):
                ref_name = m.group()
                if not is_def_line:
                    refs.add(ref_name)

    # 找出被引用但未定义的证据
    undefined = refs - defs
    for ref_name in undefined:
        for para in content.paragraphs:
            if ref_name in para.text:
                idx = para.text.index(ref_name)
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=idx,
                    end_offset=idx + len(ref_name),
                    issue_type="M7_证据引用",
                    severity="严重",
                    action="comment_only",
                    original_text=ref_name,
                    comment_text=f"[M7] 引用了未定义的证据：'{ref_name}'。全文中未找到该证据的描述或定义，请核实。",
                ))
                break  # 每个未定义证据只报一次

    return issues


def _check_attachment_refs(content) -> list:
    """检查附件引用是否在附件清单中有对应项"""
    issues = []
    from checker import Issue

    att_ref_pattern = re.compile(r'附件[一二三四五六七八九十\d]+')
    att_def_pattern = re.compile(r'附件[一二三四五六七八九十\d]+\s*[：:为]')

    refs = set()
    defs = set()

    for para in content.paragraphs:
        for m in att_def_pattern.finditer(para.text):
            defs.add(m.group().rstrip('：:为').rstrip())

        lines = para.text.split('\n')
        for line in lines:
            is_def_line = bool(att_def_pattern.search(line))
            for m in att_ref_pattern.finditer(line):
                ref_name = m.group()
                if not is_def_line:
                    refs.add(ref_name)

    # "详见附件"但无附件清单
    has_generic_ref = any(
        re.search(r'(?:详见|见|另附|附后)\s*附件(?![一二三四五六七八九十\d])', para.text)
        for para in content.paragraphs
    )
    if has_generic_ref and not defs:
        issues.append(Issue(
            location_type="paragraph",
            para_index=1,
            cell_ref=None,
            start_offset=0,
            end_offset=0,
            issue_type="M7_附件缺失",
            severity="严重",
            action="comment_only",
            original_text="",
            comment_text="[M7] 正文中引用了附件但全文无附件清单。请核实是否遗漏附件。",
        ))
        return issues

    undefined = refs - defs
    for ref_name in undefined:
        for para in content.paragraphs:
            if ref_name in para.text:
                idx = para.text.index(ref_name)
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=idx,
                    end_offset=idx + len(ref_name),
                    issue_type="M7_附件引用",
                    severity="严重",
                    action="comment_only",
                    original_text=ref_name,
                    comment_text=f"[M7] 引用了附件清单中不存在的附件：'{ref_name}'。附件清单中未找到该项，请核实。",
                ))
                break

    return issues


def _check_orphan_evidence(content) -> list:
    """检查证据清单中有定义但正文从未引用的证据"""
    issues = []
    from checker import Issue

    def_pattern = re.compile(r'证据[一二三四五六七八九十\d]+\s*[：:为]')
    ref_pattern = re.compile(r'证据[一二三四五六七八九十\d]+')

    defs = set()
    for para in content.paragraphs:
        for m in def_pattern.finditer(para.text):
            defs.add(m.group().rstrip('：:为').rstrip())

    # 统计每个证据定义的引用次数
    ref_counts = {d: 0 for d in defs}
    for para in content.paragraphs:
        for d in defs:
            if re.search(re.escape(d), para.text):
                ref_counts[d] += 1

    # 定义出现≥2次算已引用（定义本身+正文引用）
    orphaned = [d for d, count in ref_counts.items() if count <= 1]
    if orphaned and len(defs) > 2:
        names = "、".join(orphaned[:5])
        suffix = "等" if len(orphaned) > 5 else ""
        issues.append(Issue(
            location_type="paragraph",
            para_index=1,
            cell_ref=None,
            start_offset=0,
            end_offset=0,
            issue_type="M7_未引用证据",
            severity="一般",
            action="comment_only",
            original_text="",
            comment_text=f"[M7] 证据清单中有 {len(orphaned)} 项证据未被正文引用（{names}{suffix}），请核实是否遗漏。",
        ))

    return issues
