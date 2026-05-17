"""国家法律法规数据库 MCP - 响应格式化"""

from __future__ import annotations

import re
from typing import Any


SXX_LABELS = {1: "已废止", 2: "被修订", 3: "生效中", 4: "未生效"}


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"<p[^>]*>", "\n", text)
    text = text.replace("</p>", "")
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_highlight(title: str) -> str:
    return re.sub(r"<em[^>]*>|</em>", "", title)


def format_search_results(data: dict) -> str:
    total = data.get("total", 0)
    rows = data.get("rows", [])

    if not rows:
        return "未检索到匹配的法律法规。"

    lines = [f"## 搜索结果（共 {total} 条，显示 {len(rows)} 条）\n"]

    for i, row in enumerate(rows, 1):
        title = clean_highlight(row.get("title", "无标题"))
        sxx = SXX_LABELS.get(row.get("sxx"), "未知")
        zdjg = row.get("zdjgName", "")
        gbrq = row.get("gbrq", "") or ""
        sxrq = row.get("sxrq", "") or ""
        flxz = row.get("flxz", "")
        bbbs = row.get("bbbs", "")

        lines.append(f"### {i}. {title}")
        lines.append(f"- **ID**: `{bbbs}`")
        lines.append(f"- **状态**: {sxx}")
        if zdjg:
            lines.append(f"- **制定机关**: {zdjg}")
        if gbrq:
            lines.append(f"- **公布日期**: {gbrq}")
        if sxrq:
            lines.append(f"- **生效日期**: {sxrq}")
        if flxz:
            lines.append(f"- **法律性质**: {flxz}")
        lines.append("")

    return "\n".join(lines)


def format_law_detail(data: dict) -> str:
    if not data:
        return "未获取到法律法规详情。"

    title = data.get("title", "无标题")
    sxx = SXX_LABELS.get(data.get("sxx"), "未知")
    zdjg = data.get("zdjgName", "")
    gbrq = data.get("gbrq", "") or ""
    sxrq = data.get("sxrq", "") or ""
    flxz = data.get("flxz", "")
    bbbs = data.get("bbbs", "")

    lines = [f"# {title}\n"]
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| ID | `{bbbs}` |")
    if zdjg:
        lines.append(f"| 制定机关 | {zdjg} |")
    if gbrq:
        lines.append(f"| 公布日期 | {gbrq} |")
    if sxrq:
        lines.append(f"| 生效日期 | {sxrq} |")
    lines.append(f"| 时效性 | {sxx} |")
    if flxz:
        lines.append(f"| 法律性质 | {flxz} |")
    lines.append("")

    # 目录树
    content = data.get("content")
    if content and isinstance(content, dict):
        lines.append("## 目录结构\n")
        _render_tree(content, lines, depth=0)
        lines.append("")

    # 历史版本
    lsyg = data.get("lsyg")
    if lsyg and isinstance(lsyg, list) and lsyg:
        lines.append("## 历史版本\n")
        for v in lsyg:
            vt = v.get("title", "")
            hl = " ← 当前" if v.get("highLight") else ""
            lines.append(f"- {vt}{hl}")
        lines.append("")

    # 相关文件
    xgwj = data.get("xgwj")
    if xgwj and isinstance(xgwj, list) and xgwj:
        lines.append("## 相关文件\n")
        for f in xgwj[:10]:
            ft = f.get("title", "")
            lines.append(f"- {ft}")
        lines.append("")

    # OSS 文件
    oss = data.get("ossFile")
    if oss and isinstance(oss, dict):
        lines.append("## 文件信息\n")
        if oss.get("ossWordPath"):
            lines.append(f"- Word: {oss['ossWordPath']}")
        if oss.get("ossWordOfdPath"):
            lines.append(f"- OFD: {oss['ossWordOfdPath']}")
        lines.append("")

    return "\n".join(lines)


def _render_tree(node: dict, lines: list, depth: int):
    title = node.get("title", "")
    idx = node.get("index", "")
    children = node.get("children", [])

    if depth > 0:
        prefix = "  " * min(depth - 1, 4)
        bullet = "- " if depth > 1 else ""
        lines.append(f"{prefix}{bullet}{idx} {title}" if idx else f"{prefix}{bullet}{title}")

    for c in children[:30]:
        _render_tree(c, lines, depth + 1)


def format_hit_display(data: dict, keyword: str) -> str:
    hits = data.get("contentHitDisplay", [])
    if not hits:
        return f"未找到包含「{keyword}」的法条片段。"

    lines = [f"## 命中展示（关键词：{keyword}，共 {len(hits)} 处）\n"]

    for i, hit in enumerate(hits, 1):
        clean = html_to_text(hit)
        bold = re.sub(r"（高亮）", "", clean)
        lines.append(f"**{i}.** {bold}")
        lines.append("")

    return "\n".join(lines)


def format_enum_data(data: dict, category: str) -> str:
    if not data:
        return "未获取到分类数据。"

    cat_name = "法律分类" if category == "flfgfl" else "制定机关"
    lines = [f"## {cat_name}\n"]

    items = data if isinstance(data, list) else data.get("children", data.get("list", []))

    if isinstance(items, list):
        for item in items:
            _render_enum_node(item, lines, depth=0)
    elif isinstance(items, dict):
        _render_enum_node(items, lines, depth=0)

    return "\n".join(lines)


def _render_enum_node(node: dict, lines: list, depth: int):
    name = node.get("name", node.get("title", ""))
    code_id = node.get("codeId", node.get("id", ""))
    children = node.get("children", [])

    prefix = "  " * depth
    child_info = f" → {len(children)} 个子项" if children else ""
    lines.append(f"{prefix}- `{code_id}` — {name}{child_info}")

    for c in children:
        _render_enum_node(c, lines, depth + 1)


def format_suggestions(data: Any) -> str:
    if not data:
        return "无搜索建议。"

    if isinstance(data, list):
        if not data:
            return "无搜索建议。"
        lines = ["## 搜索建议\n"]
        for item in data:
            if isinstance(item, str):
                lines.append(f"- {item}")
            elif isinstance(item, dict):
                lines.append(f"- {item.get('title', item.get('name', str(item)))}")
        return "\n".join(lines)

    return str(data)


def format_related(data: Any) -> str:
    if not data:
        return "无相关法律法规。"

    if isinstance(data, list):
        if not data:
            return "无相关法律法规。"
        lines = ["## 相关法律法规\n"]
        for item in data:
            if isinstance(item, dict):
                title = item.get("title", "")
                sxx = SXX_LABELS.get(item.get("sxx"), "")
                lines.append(f"- **{title}**（{sxx}）")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)

    return str(data)


def format_download(data: dict) -> str:
    if not data:
        return "未获取到下载信息。"

    lines = ["## 下载链接\n"]
    url = data.get("url", data.get("urlIn", ""))
    if url:
        lines.append(f"下载地址: {url}")
    else:
        lines.append("未获取到有效下载链接。")

    return "\n".join(lines)


FIELD_LABELS = {
    "title": "法律标题",
    "content": "法律全文",
    "xgzl.title": "相关资料标题",
    "xgzl.content": "相关资料全文",
    "gbrq": "公布日期",
    "sxrq": "施行日期",
    "flfg_code_id": "法律分类",
    "zdjg_code_id": "制定机关",
    "sxx": "时效性",
}

LINK_LABELS = {0: "并且", 1: "或者", 2: "不含"}


def format_high_search_results(data: dict, conditions: list[dict]) -> str:
    total = data.get("total", 0)
    rows = data.get("rows", [])

    if not rows:
        return "未检索到匹配的法律法规。"

    cond_desc = "；".join(
        f"{FIELD_LABELS.get(c.get('fieldName', ''), c.get('fieldName', ''))}"
        f"({'精确' if c.get('searchType') == 1 else '模糊'})={c.get('values', [])}"
        for c in conditions
    )

    lines = [f"## 高级检索结果（共 {total} 条，显示 {len(rows)} 条）\n"]
    lines.append(f"**检索条件**: {cond_desc}\n")

    for i, row in enumerate(rows, 1):
        title = clean_highlight(row.get("title", "无标题"))
        sxx = SXX_LABELS.get(row.get("sxx"), "未知")
        zdjg = row.get("zdjgName", "")
        gbrq = row.get("gbrq", "") or ""
        sxrq = row.get("sxrq", "") or ""
        flxz = row.get("flxz", "")
        bbbs = row.get("bbbs", "")

        lines.append(f"### {i}. {title}")
        lines.append(f"- **ID**: `{bbbs}`")
        lines.append(f"- **状态**: {sxx}")
        if zdjg:
            lines.append(f"- **制定机关**: {zdjg}")
        if gbrq:
            lines.append(f"- **公布日期**: {gbrq}")
        if sxrq:
            lines.append(f"- **生效日期**: {sxrq}")
        if flxz:
            lines.append(f"- **法律性质**: {flxz}")
        lines.append("")

    return "\n".join(lines)


def format_high_xgzl(data: dict) -> str:
    xgzl_list = data.get("xgzlList", [])
    if not xgzl_list:
        return "无相关资料。"

    lines = [f"## 相关资料（共 {len(xgzl_list)} 条）\n"]

    for i, item in enumerate(xgzl_list, 1):
        title = clean_highlight(item.get("title", ""))
        lines.append(f"{i}. {title}")

    return "\n".join(lines)
