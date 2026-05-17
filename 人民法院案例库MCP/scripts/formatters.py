"""API 响应格式化工具"""

from __future__ import annotations

import re
from typing import Any


TYPE_LABELS = {
    "01": "指导性案例",
    "02": "参考案例",
    "04": "特色案事例",
}

STATUS_LABELS = {
    "01": "有效",
    "02": "失效",
}


def html_to_text(html: str | None) -> str:
    """将 API 返回的 HTML 转为纯文本"""
    if not html:
        return ""
    text = html
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</?p[^>]*>', '\n', text)
    text = re.sub(r'<em>(.*?)</em>', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace(' ', ' ')  # &nbsp;
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def format_search_results(data: dict[str, Any]) -> str:
    """格式化搜索结果为 Markdown"""
    total = data.get("totalCount", 0)
    items = data.get("datas", [])

    if not items:
        return "未检索到匹配的案例。"

    lines = [f"共检索到 **{total}** 条案例\n"]

    for i, item in enumerate(items, 1):
        title = _clean_title(item.get("cpws_al_title", "无标题"))
        type_label = TYPE_LABELS.get(item.get("cpws_al_type", ""), "")
        status = item.get("cpws_al_status", "")
        status_tag = " [已失效]" if status == "02" else ""

        lines.append(f"### {i}. {title}{status_tag}")
        if type_label:
            lines.append(f"- **类型**: {type_label}")
        lines.append(f"- **案号**: {item.get('cpws_al_ajzh', '-')}")
        lines.append(f"- **案由**: {item.get('cpws_al_sort_name', '-') or item.get('cpws_al_case_sort_name', '-')}")
        lines.append(f"- **法院**: {item.get('cpws_al_slfy_name', '-')}")
        lines.append(f"- **裁判日期**: {item.get('cpws_al_zs_date', '-')}")
        lines.append(f"- **程序**: {item.get('cpws_al_slcx_name', '-')}")
        lines.append(f"- **案例ID**: `{item.get('cpws_al_id', '')}`")

        cpyz = html_to_text(item.get("cpws_al_cpyz", ""))
        if cpyz:
            preview = cpyz[:200] + ("..." if len(cpyz) > 200 else "")
            yz_label = _get_yz_label(item)
            lines.append(f"- **{yz_label}**: {preview}")
        lines.append("")

    return "\n".join(lines)


def format_case_detail(data: dict[str, Any], sections: list[str] | None = None) -> str:
    """格式化案例详情为 Markdown"""
    case_data = data.get("data", {})
    if not case_data:
        return "未获取到案例详情。"

    title = case_data.get("cpws_al_title", "")
    type_label = TYPE_LABELS.get(case_data.get("cpws_al_type", ""), "")
    status = case_data.get("cpws_al_status", "")
    status_tag = " [已失效]" if status == "02" else ""

    lines = [f"# {title}{status_tag}\n"]

    # 元数据
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 类型 | {type_label} |")
    lines.append(f"| 案号 | {case_data.get('cpws_al_ajzh', '-')} |")
    lines.append(f"| 裁判日期 | {case_data.get('cpws_al_zs_date', '-')} |")
    lines.append(f"| 法院 | {case_data.get('cpws_al_slfy_sf_name', '-')} |")
    lines.append(f"| 案例编号 | {case_data.get('cpws_al_no', '-')} |")

    keywords = case_data.get("cpws_al_keyword", [])
    if keywords:
        lines.append(f"| 关键词 | {', '.join(keywords)} |")
    lines.append("")

    # 章节内容
    section_map = {
        "key_points": ("裁判要点" if case_data.get("cpws_al_type") == "01" else "裁判要旨", "cpws_al_cpyz"),
        "case_facts": ("基本案情", "cpws_al_jbaq"),
        "judgment": ("裁判结果", "cpws_al_cpjg"),
        "reasoning": ("裁判理由", "cpws_al_cply"),
        "laws": ("关联法条", "cpws_al_glsy"),
    }

    target_sections = sections or list(section_map.keys())

    for sec_key in target_sections:
        if sec_key in section_map:
            label, field = section_map[sec_key]
            content = html_to_text(case_data.get(field, ""))
            if content:
                lines.append(f"## {label}\n")
                lines.append(content)
                lines.append("")

    return "\n".join(lines)


def format_statistics(
    total_data: dict[str, Any],
    keyword_data: list | None = None,
    year_data: list | None = None,
) -> str:
    """格式化统计信息为 Markdown"""
    lines = ["## 案例库统计\n"]

    # 类型分布
    type_items = total_data.get("data", [])
    if type_items:
        lines.append("### 类型分布\n")
        lines.append("| 类型 | 数量 |")
        lines.append("|------|------|")
        total = 0
        for item in type_items:
            label = TYPE_LABELS.get(item.get("key", ""), item.get("value", ""))
            count = item.get("intCount", 0)
            lines.append(f"| {label} | {count} |")
            total += count
        lines.append(f"| **合计** | **{total}** |")
        lines.append("")

    # 关键词聚类
    if keyword_data:
        lines.append("### 关键词分布（Top 10）\n")
        lines.append("| 关键词 | 数量 |")
        lines.append("|--------|------|")
        for item in keyword_data[:10]:
            lines.append(f"| {item.get('value', '-')} | {item.get('intCount', item.get('count', '-'))} |")
        lines.append("")

    # 年份聚类
    if year_data:
        lines.append("### 审判年份分布\n")
        lines.append("| 年份 | 数量 |")
        lines.append("|------|------|")
        for item in year_data[:10]:
            lines.append(f"| {item.get('value', '-')} | {item.get('intCount', item.get('count', '-'))} |")
        lines.append("")

    return "\n".join(lines)


def _clean_title(title: str) -> str:
    """去除搜索结果标题中的 <em> 高亮标签"""
    return re.sub(r'</?em>', '', title)


def _get_yz_label(item: dict) -> str:
    """获取裁判要点/要旨的标签"""
    case_type = item.get("cpws_al_type", "")
    case_sort_ids = item.get("cpws_al_case_sort_id", [])

    if isinstance(case_sort_ids, list):
        if "A06" in case_sort_ids:
            return "调解指引"
        if "A0501" in case_sort_ids:
            if case_type == "02":
                return "执行要旨"
            if case_type == "01":
                return "执行实施要点"

    return "裁判要点" if case_type == "01" else "裁判要旨"
