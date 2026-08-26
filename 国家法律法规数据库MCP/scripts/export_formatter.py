"""国家法律法规数据库 MCP - Obsidian 导出格式转换

导出流程：flk_get_detail(元数据) → flk_download(docx URL) → pandoc(md) → 后处理 → 写入

格式对齐「批量导入法律法规到Obsidian」项目的 content_formatter.py 规范：
- YAML frontmatter：title / tags / 类型 / 公布日期 / 生效日期 / 状态 / 引用建立 / 来源 / 来源ID / 制定机关 / 历史沿革
- 元数据表格：发文机关 / 发布日期 / 生效日期 / 时效性（点分日期）
- 正文：pandoc 原始输出经清洗后（去目录、全角空格、题注 blockquote、章条标题转换）
- 文件名：含修正年份后缀，如「中华人民共和国专利法（2020修正）.md」
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Optional

from formatters import html_to_text

# ==================== 分类常量 ====================

LAW_DIR_MAP = {
    "专利": "001-专利",
    "商标": "002-商标",
    "著作权": "003-著作权",
    "商业秘密": "004-商业秘密",
    "植物新品种": "005-植物新品种",
    "反垄断": "006-反垄断",
    "知识产权综合": "007-知识产权综合",
    "民法": "008-民法",
    "刑法": "009-刑法",
    "行政法": "010-行政法",
    "商法": "011-商法",
    "保全执行": "012-保全执行",
    "组织法": "013-组织法",
}

DEFAULT_DIR = "014-其他"

# 分类关键词优先级（从高到低，对齐 batch_import_obsidian.py 的 CLASSIFICATIONS 顺序）
_CLASSIFY_RULES = [
    ("专利法", "专利"), ("专利代理", "专利"), ("专利权", "专利"),
    ("专利申请", "专利"), ("专利侵权", "专利"), ("专利纠纷", "专利"),
    ("专利授权", "专利"), ("专利复审", "专利"), ("实用新型专利", "专利"),
    ("发明专利", "专利"), ("外观设计专利", "专利"),
    ("集成电路", "专利"), ("技术进出口", "专利"), ("国防专利", "专利"),
    ("商标", "商标"),
    ("著作权", "著作权"), ("版权", "著作权"),
    ("计算机软件保护", "著作权"), ("信息网络传播权", "著作权"),
    ("商业秘密", "商业秘密"), ("技术秘密", "商业秘密"),
    ("植物新品种", "植物新品种"), ("种子法", "植物新品种"),
    ("反垄断", "反垄断"), ("垄断", "反垄断"),
    ("反不正当竞争", "商业秘密"), ("惩罚性赔偿", "商业秘密"),
    ("知识产权海关保护", "知识产权综合"), ("知识产权判决执行", "知识产权综合"),
    ("知识产权法庭", "知识产权综合"), ("知识产权法院", "知识产权综合"),
    ("知识产权民事", "知识产权综合"), ("知识产权刑事", "知识产权综合"),
    ("知识产权保全", "知识产权综合"), ("知识产权侵权", "知识产权综合"),
    ("知识产权合同", "知识产权综合"), ("知识产权滥用", "知识产权综合"),
    ("知识产权证据", "知识产权综合"), ("知识产权管辖", "知识产权综合"),
    ("知识产权执行", "知识产权综合"), ("知识产权三合一", "知识产权综合"),
    ("打击侵犯知识产权", "知识产权综合"), ("涉外知识产权", "知识产权综合"),
    ("知识产权协调", "知识产权综合"),
    ("民法典", "民法"), ("民事诉讼法", "民法"), ("民事诉讼证据", "民法"),
    ("刑法", "刑法"), ("刑事诉讼法", "刑法"), ("国际刑事司法协助", "刑法"),
    ("办理侵犯知识产权刑事", "刑法"),
    ("行政处罚法", "行政法"), ("行政强制法", "行政法"),
    ("行政诉讼法", "行政法"), ("国家赔偿法", "行政法"),
    ("保守国家秘密法", "行政法"), ("国家安全法", "行政法"),
    ("公司法", "商法"), ("合伙企业法", "商法"),
    ("广告法", "商法"), ("外商投资法", "商法"),
    ("执行工作", "保全执行"), ("财产保全", "保全执行"),
    ("查封", "保全执行"), ("冻结", "保全执行"),
    ("拍卖", "保全执行"), ("变卖", "保全执行"),
    ("网络司法拍卖", "保全执行"), ("财产调查", "保全执行"),
    ("执行程序", "保全执行"), ("执行异议", "保全执行"),
    ("人民法院组织法", "组织法"), ("律师法", "组织法"),
]

# ==================== sxx 映射（对齐 content_formatter.py / flk_api.py） ====================

SXX_MAP = {3: "生效中", 2: "被修订", 1: "已废止", 4: "未生效"}
SXX_TEXT_MAP = {3: "现行有效", 2: "已修改", 1: "已废止", 4: "尚未生效"}


def map_sxx(sxx) -> str:
    return SXX_MAP.get(int(sxx), "生效中")


def map_sxx_text(sxx) -> str:
    return SXX_TEXT_MAP.get(int(sxx), "现行有效")


# ==================== 分类 ====================

def classify_law_dir(text: str) -> str:
    text_lower = text.lower()
    for keyword, category in _CLASSIFY_RULES:
        if keyword in text_lower:
            return LAW_DIR_MAP.get(category, DEFAULT_DIR)
    return DEFAULT_DIR


# ==================== 标题与文件名 ====================

def build_title_with_version(detail: dict) -> str:
    """构造含修正年份的标题

    从 lsyg 中找到当前版本（highLight=true）的 gbrq，
    拼接为「法律名称（YYYY修正）」格式。
    如果没有修正记录或仅一条记录，返回原始 title。
    """
    title = detail.get("title", "")
    clean_title = html_to_text(title) if "<" in title else title
    lsyg = detail.get("lsyg", [])

    if not lsyg or len(lsyg) <= 1:
        return clean_title

    for v in lsyg:
        if v.get("highLight"):
            year = v.get("gbrq", "")[:4]
            if year:
                return f"{clean_title}（{year}修正）"

    return clean_title


def sanitize_filename(title: str, max_len: int = 80) -> str:
    clean = html_to_text(title) if "<" in title else title
    clean = re.sub(r'[<>:"/\\|?*]', "", clean)
    clean = clean.strip()
    clean = re.sub(r"\s+", " ", clean)
    if len(clean) > max_len:
        clean = clean[: max_len - 3] + "..."
    return clean + ".md" if not clean.endswith(".md") else clean


# ==================== pandoc 转换 ====================

# pandoc 路径
PANDOC_PATH = os.path.join(
    os.path.expanduser("~"),
    "AppData/Roaming/Python/Python314/site-packages/pypandoc/files/pandoc.exe",
)
if not os.path.exists(PANDOC_PATH):
    PANDOC_PATH = "pandoc"  # fallback to PATH


def run_pandoc(docx_path: str) -> Optional[str]:
    """用 pandoc 将 DOCX 转为 Markdown"""
    try:
        result = subprocess.run(
            [PANDOC_PATH, docx_path, "-t", "markdown", "--wrap=none"],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode("utf-8", errors="replace")
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


# ==================== pandoc 输出后处理（对齐 content_formatter.py） ====================

CHAPTER_RE = re.compile(r'^第[一二三四五六七八九十百千]+章\s')
ARTICLE_RE = re.compile(r'^(第[一二三四五六七八九十百千]+条)\s*(.*)')
SECTION_RE = re.compile(r'^第[一二三四五六七八九十百千]+节\s')


def _is_toc_header(line: str) -> bool:
    stripped = line.strip()
    return '目' in stripped and '录' in stripped and not stripped.startswith('>')


def _has_chapter_structure(detail: dict) -> bool:
    content = detail.get("content", {})
    if isinstance(content, dict):
        for child in content.get("children", []):
            title = child.get("title", "")
            if title.startswith("第") and "章" in title:
                return True
    return False


def clean_pandoc_output(raw_md: str, detail: dict) -> str:
    """清洗 pandoc 原始输出为 Obsidian 格式正文

    处理步骤（对齐 content_formatter.clean_pandoc_output）：
    1. 跳过目录部分
    2. 清理全角空格
    3. 去除题注 blockquote
    4. 跳过首行法律名称
    5. 章标题 → H1 粗体
    6. 节标题 → H2 粗体（有章结构时）
    7. 条标题拆分 → H2 粗体 + 另起段
    """
    lines = raw_md.strip().split('\n')
    output = []
    in_toc = False
    has_chapters = _has_chapter_structure(detail)
    title = detail.get("title", "")

    for line in lines:
        # 1. 跳过目录部分
        if _is_toc_header(line):
            in_toc = True
            continue
        if in_toc:
            if line.startswith('>') or line.strip() == '':
                continue
            in_toc = False

        # 2. 清理全角空格 + 压缩连续空格
        line = line.replace('　', ' ')
        while '  ' in line:
            line = line.replace('  ', ' ')
        line = line.rstrip()

        # 3. 去除题注 blockquote
        if line.startswith('> '):
            line = line[2:]
        elif line == '>':
            continue

        # 4. 跳过首行（法律名称，后面由 H1 替代）
        stripped = line.strip()
        if stripped == title:
            continue

        # 5. 章标题转换
        if CHAPTER_RE.match(stripped):
            stripped = f'# **{stripped}**'
            output.append(stripped)
            continue

        # 6. 节标题转换（有章结构时，节为 H2）
        if has_chapters and SECTION_RE.match(stripped):
            stripped = f'## **{stripped}**'
            output.append(stripped)
            continue

        # 7. 条标题拆分
        m = ARTICLE_RE.match(stripped)
        if m:
            art_num = m.group(1)
            art_content = m.group(2).strip()
            prefix = '##'  # 统一 H2
            if art_content:
                output.append(f'{prefix} **{art_num}**')
                output.append('')
                output.append(art_content)
            else:
                output.append(f'{prefix} **{art_num}**')
            continue

        output.append(stripped)

    # 合并并清理多余空行
    body = '\n'.join(output)
    body = re.sub(r'\n{4,}', '\n\n\n', body)
    return body.strip()


# ==================== YAML frontmatter 与元数据表格 ====================

def build_lsyg_yaml(detail: dict) -> str:
    """构造历史沿革 YAML（wikilink 格式）"""
    lsyg = detail.get("lsyg", [])
    lines = []
    for v in lsyg:
        if v.get("highLight"):
            continue
        year = v.get("gbrq", "")[:4]
        title = v.get("title", "")
        if year and title:
            lines.append(f'  - "[[{title}（{year}修正）]]"')
    return '\n'.join(lines) if lines else '  - 无'


def build_frontmatter(detail: dict, title: str) -> str:
    """生成 YAML frontmatter（对齐 content_formatter.build_frontmatter）"""
    category = classify_law_dir(title)
    tag = category.split("-", 1)[1] if "-" in category else category
    flxz = detail.get("flxz", "法律")
    gbrq = detail.get("gbrq", "")
    sxrq = detail.get("sxrq", "")
    sxx = detail.get("sxx", 3)
    bbbs = detail.get("bbbs", "")
    zdjg = detail.get("zdjgName", "")
    lsyg_yaml = build_lsyg_yaml(detail)

    return f"""---
title: {title}
tags: ["{tag}"]
类型: [{flxz}]
公布日期: {gbrq}
生效日期: {sxrq}
状态: [{map_sxx(sxx)}]
引用建立: [否]
来源: flk
来源ID: "{bbbs}"
制定机关: {zdjg}
历史沿革:
{lsyg_yaml}
---"""


def build_metadata_table(detail: dict) -> str:
    """生成元数据 GFM 表格（对齐 content_formatter.build_metadata_table）"""
    zdjg = detail.get("zdjgName", "")
    gbrq = detail.get("gbrq", "").replace("-", ".")
    sxrq = detail.get("sxrq", "").replace("-", ".")
    sxx_text = map_sxx_text(detail.get("sxx", 3))

    return f"|**发文机关**|{zdjg}|\n| -| --------------------------|\n|**发布日期**|{gbrq}|\n|**生效日期**|{sxrq}|\n|**时效性**|{sxx_text}|"


def assemble_obsidian_md(detail: dict, body: str, title: str) -> str:
    """组装完整 Obsidian MD 文件"""
    fm = build_frontmatter(detail, title)
    h1 = f'# {title}'
    table = build_metadata_table(detail)
    return f'{fm}\n{h1}\n\n{table}\n\n{body}\n'


# ==================== 导出入口函数 ====================

def format_obsidian_law(detail_data: dict) -> tuple[str, str, str]:
    """骨架导出（仅元数据 + 目录树标题，不含条文正文）

    降级方案：当 docx 下载失败时使用。
    返回 (file_content, filename, subdir)
    """
    title = build_title_with_version(detail_data)
    sxx = detail_data.get("sxx", 3)
    sxx_label = map_sxx(sxx)
    zdjg = detail_data.get("zdjgName", "")
    gbrq = detail_data.get("gbrq", "") or ""
    sxrq = detail_data.get("sxrq", "") or ""
    flxz = detail_data.get("flxz", "")
    bbbs = detail_data.get("bbbs", "")

    # 分类
    classify_text = f"{title} {zdjg} {flxz}"
    subdir = classify_law_dir(classify_text)

    # Frontmatter（骨架版，不含历史沿革的 docx 版本字段）
    category = subdir.split("-", 1)[1] if "-" in subdir else subdir
    lsyg_yaml = build_lsyg_yaml(detail_data)

    fm_lines = ["---"]
    fm_lines.append(f"title: {title}")
    fm_lines.append(f'tags: ["{category}"]')
    fm_lines.append(f"类型: [{flxz}]" if flxz else "类型: [其他]")
    fm_lines.append(f"状态: [{sxx_label}]")
    fm_lines.append("引用建立: [否]")
    fm_lines.append("来源: flk")
    fm_lines.append(f'来源ID: "{bbbs}"')
    if zdjg:
        fm_lines.append(f"制定机关: {zdjg}")
    fm_lines.append("历史沿革:")
    fm_lines.append(lsyg_yaml)
    fm_lines.append("---")

    # Body
    body_lines = [f"# {title}", ""]

    # 元数据表格
    gbrq_dot = gbrq.replace("-", ".")
    sxrq_dot = sxrq.replace("-", ".")
    sxx_text = map_sxx_text(sxx)
    body_lines.append(f"|**发文机关**|{zdjg}|")
    body_lines.append("| -| --------------------------|")
    body_lines.append(f"|**发布日期**|{gbrq_dot}|")
    body_lines.append(f"|**生效日期**|{sxrq_dot}|")
    body_lines.append(f"|**时效性**|{sxx_text}|")
    body_lines.append("")

    # 目录树内容（骨架）
    content = detail_data.get("content")
    if content and isinstance(content, dict):
        body_lines.append("")
        _render_content_tree(content, body_lines)

    body_lines.append("")
    body_lines.append("> ⚠️ 本文件为目录骨架导出，不含条文正文。")

    file_content = "\n".join(fm_lines) + "\n\n" + "\n".join(body_lines)
    filename = sanitize_filename(title)

    return file_content, filename, subdir


def format_obsidian_law_full(detail_data: dict, body_md: str) -> tuple[str, str, str]:
    """完整导出（元数据 + pandoc 转换的条文全文）

    返回 (file_content, filename, subdir)
    """
    title = build_title_with_version(detail_data)

    # 分类
    zdjg = detail_data.get("zdjgName", "")
    flxz = detail_data.get("flxz", "")
    classify_text = f"{title} {zdjg} {flxz}"
    subdir = classify_law_dir(classify_text)

    file_content = assemble_obsidian_md(detail_data, body_md, title)
    filename = sanitize_filename(title)

    return file_content, filename, subdir


def _render_content_tree(node: dict, lines: list, depth: int = 0):
    title = node.get("title", "")
    children = node.get("children", [])

    if depth == 0:
        for c in children:
            _render_content_tree(c, lines, depth + 1)
        return

    is_chapter = any(k in title for k in ["章", "编"])
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
