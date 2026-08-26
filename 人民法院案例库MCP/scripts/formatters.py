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
    type_data: list | dict,       # cpwsAlTypeNextLeftCluster
    sort_data: list | dict,       # sortNextLeftCluster
    keyword_data: list | dict,    # keywordNextLeftCluster
    fyjb_data: list | dict,       # fyjbNextLeftCluster（法院级别）
    slfy_data: list | dict,       # slfyNextLeftCluster（受理法院）
    slcx_data: list | dict,       # slcxNextLeftCluster（审理程序）
    year_data: list | dict,       # yearNextLeftCluster
) -> str:
    """格式化 6 维度统计信息为 Markdown"""
    lines = ["## 案例库多维度统计\n"]

    def _items(data):
        """统一提取列表，兼容 list 和 dict 格式"""
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "error" not in data:
            return data.get("data", data)
        return []

    def _show_table(title: str, items: list, key_label: str, limit: int = 10):
        """通用表格渲染"""
        items = _items(items)
        if not items:
            return
        lines.append(f"### {title}\n")
        lines.append(f"| {key_label} | 数量 |")
        lines.append("|" + "---|" * 2)
        for item in items[:limit]:
            k = item.get("value", item.get("key", item.get("id", "-")))
            c = item.get("intCount", item.get("count", 0))
            lines.append(f"| {k} | {c} |")
        lines.append("")

    _show_table("案例类型", type_data, "类型", 5)
    _show_table("关键词聚类", keyword_data, "关键词", 15)
    _show_table("年份分布", year_data, "年份", 12)
    _show_table("法院级别", fyjb_data, "级别", 8)
    _show_table("审理法院", slfy_data, "法院", 12)
    _show_table("审理程序", slcx_data, "程序", 8)
    _show_table("案由/罪名分布", sort_data, "案由", 15)

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
