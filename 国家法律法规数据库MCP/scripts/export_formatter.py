"""国家法律法规数据库 MCP - Obsidian 导出格式转换"""

from __future__ import annotations

import re

from formatters import html_to_text, SXX_LABELS

LAW_DIR_MAP = {
    "专利": "001-专利",
    "商标": "002-商标",
    "著作权": "003-著作权",
    "商业秘密": "004-商业秘密",
    "植物新品种": "005-植物新品种",
    "反垄断": "006-反垄断",
    "不正当竞争": "004-商业秘密",
    "集成电路": "001-专利",
    "知识产权综合": "007-知识产权综合",
    "民法": "008-民法",
    "刑法": "009-刑法",
    "行政法": "010-行政法",
    "商法": "011-商法",
    "保全执行": "012-保全执行",
    "组织法": "013-组织法",
}

DEFAULT_DIR = "014-其他"

# 分类关键词优先级（从高到低）
_CLASSIFY_RULES = [
    ("专利", "专利"),
    ("商标", "商标"),
    ("著作权", "著作权"),
    ("版权", "著作权"),
    ("计算机软件", "著作权"),
    ("商业秘密", "商业秘密"),
    ("技术秘密", "商业秘密"),
    ("植物新品种", "植物新品种"),
    ("反垄断", "反垄断"),
    ("垄断", "反垄断"),
    ("不正当竞争", "不正当竞争"),
    ("集成电路", "集成电路"),
    ("民法", "民法"),
    ("民法典", "民法"),
    ("刑法", "刑法"),
    ("行政", "行政法"),
    ("商法", "商法"),
    ("公司", "商法"),
    ("保全", "保全执行"),
    ("执行", "保全执行"),
    ("组织法", "组织法"),
]


def classify_law_dir(text: str) -> str:
    text_lower = text.lower()
    for keyword, category in _CLASSIFY_RULES:
        if keyword in text_lower:
            return LAW_DIR_MAP.get(category, DEFAULT_DIR)
    return DEFAULT_DIR


def sanitize_filename(title: str, max_len: int = 80) -> str:
    clean = html_to_text(title) if "<" in title else title
    clean = re.sub(r'[<>:"/\\|?*]', "", clean)
    clean = clean.strip()
    clean = re.sub(r"\s+", " ", clean)
    if len(clean) > max_len:
        clean = clean[: max_len - 3] + "..."
    return clean + ".md" if not clean.endswith(".md") else clean


def format_obsidian_law(detail_data: dict) -> tuple[str, str, str]:
    title = detail_data.get("title", "无标题")
    clean_title = html_to_text(title) if "<" in title else title

    sxx = detail_data.get("sxx", 3)
    sxx_label = SXX_LABELS.get(sxx, "未知")
    sxx_table = "现行有效" if sxx == 3 else ("已废止" if sxx == 1 else ("已被修订" if sxx == 2 else "尚未生效"))

    zdjg = detail_data.get("zdjgName", "")
    gbrq = detail_data.get("gbrq", "") or ""
    sxrq = detail_data.get("sxrq", "") or ""
    flxz = detail_data.get("flxz", "")

    # 分类
    classify_text = f"{clean_title} {zdjg} {flxz}"
    subdir = classify_law_dir(classify_text)

    # tags 简单生成
    tag = _generate_tag(clean_title, flxz)

    # Frontmatter
    fm_lines = ["---"]
    fm_lines.append(f"title: {clean_title}")
    fm_lines.append(f"tags: [{tag}]")
    fm_lines.append(f"类型: [{flxz}]" if flxz else "类型: [其他]")
    fm_lines.append(f"状态: [{sxx_label}]")
    if zdjg:
        fm_lines.append(f"制定机关: {zdjg}")
    fm_lines.append(f"引用建立: [否]")
    fm_lines.append(f"来源: 国家法律法规数据库")
    if gbrq:
        fm_lines.append(f"公布日期: {gbrq}")
    if sxrq:
        fm_lines.append(f"生效日期: {sxrq}")
    fm_lines.append("---")

    # Body
    body_lines = [f"# {clean_title}", ""]

    # 元数据表格
    table_lines = []
    if zdjg:
        table_lines.append(f"| 发文机关 | {zdjg} |")
        table_lines.append("| :--- | :--- |")
    if gbrq:
        table_lines.append(f"| 发布日期 | {gbrq.replace('-', '.')} |")
    if sxrq:
        table_lines.append(f"| 生效日期 | {sxrq.replace('-', '.')} |")
    table_lines.append(f"| 时效性 | {sxx_table} |")
    body_lines.extend(table_lines)
    body_lines.append("")

    # 目录树内容
    content = detail_data.get("content")
    if content and isinstance(content, dict):
        body_lines.append("")
        _render_content_tree(content, body_lines)

    file_content = "\n".join(fm_lines) + "\n\n" + "\n".join(body_lines)
    filename = sanitize_filename(clean_title)

    return file_content, filename, subdir


def _generate_tag(title: str, flxz: str) -> str:
    for keyword in ["专利", "商标", "著作权", "商业秘密", "植物新品种", "反垄断",
                     "不正当竞争", "集成电路", "民法", "刑法", "行政"]:
        if keyword in title:
            return keyword
    return "综合"


def _render_content_tree(node: dict, lines: list, depth: int = 0):
    title = node.get("title", "")
    children = node.get("children", [])

    if depth == 0:
        # Root node — just render children
        for c in children:
            _render_content_tree(c, lines, depth + 1)
        return

    # 判断层级：章/编用 # ，条/款用 ##
    is_chapter = any(k in title for k in ["第", "章", "编", "节", "部分", "总则", "附则"])
    is_article = title.startswith("第") and ("条" in title[:10])

    if is_chapter and not is_article:
        lines.append(f"# **{title}**")
        lines.append("")
    elif is_article:
        lines.append(f"## **{title}**")
        lines.append("")
    else:
        lines.append(f"## **{title}**")
        lines.append("")

    for c in children:
        _render_content_tree(c, lines, depth + 1)
