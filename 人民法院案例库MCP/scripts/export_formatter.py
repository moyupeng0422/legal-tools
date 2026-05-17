"""导出格式转换：rmfyalk API 数据 → Obsidian 司法案例数据库格式"""

from __future__ import annotations

import re
from formatters import html_to_text

# --- IP 类型分类 ---

IP_KEYWORDS = [
    ("专利", ["专利"]),
    ("商标", ["商标"]),
    ("著作权", ["著作权", "计算机软件"]),
    ("商业秘密", ["商业秘密", "技术秘密"]),
    ("植物新品种", ["植物新品种"]),
    ("反垄断", ["垄断"]),
    ("不正当竞争", ["不正当竞争", "虚假宣传", "仿冒", "混淆", "商业诋毁", "擅自使用"]),
    ("集成电路", ["集成电路"]),
    ("数据权益", ["数据"]),
]

IP_DIR_MAP = {
    "专利": "001-专利",
    "商标": "002-商标",
    "著作权": "003-著作权",
    "商业秘密": "004-商业秘密",
    "不正当竞争": "004-商业秘密",
    "植物新品种": "005-植物新品种",
    "反垄断": "006-反垄断",
    "集成电路": "001-专利",
    "数据权益": "007-知识产权综合",
}

DEFAULT_DIR = "007-知识产权综合"

CASE_TYPE_LABELS = {
    "01": "指导性案例",
    "02": "参考案例",
}


def classify_ip_type(text: str) -> tuple[str, str]:
    """根据案由+标题+裁判要点文本判断 IP 类型和目标目录"""
    lower = text.lower()
    for ip_type, keywords in IP_KEYWORDS:
        for kw in keywords:
            if kw in lower:
                return ip_type, IP_DIR_MAP.get(ip_type, DEFAULT_DIR)
    return "综合", DEFAULT_DIR


# --- 标题处理 ---

def extract_case_number(title: str) -> int | None:
    """从标题中提取案例编号，如'指导性案例30号'→30"""
    m = re.search(r'指导性案例[第]?(\d+)号', title)
    if m:
        return int(m.group(1))
    m = re.search(r'第(\d+)号', title)
    if m:
        return int(m.group(1))
    return None


def sanitize_filename(title: str, max_len: int = 50) -> str:
    """清理标题为安全文件名"""
    # 去除 "——" 及之后内容
    title = re.split(r'——', title)[0].strip()
    # 删除非法字符
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    # 截断
    if len(title) > max_len:
        title = title[:max_len - 3] + "…"
    return title


# --- Obsidian 格式生成 ---

def format_obsidian_case(case_data: dict) -> tuple[str, str, str]:
    """将 rmfyalk 详情 API 的 data 字段转为 Obsidian 格式

    Returns:
        (file_content, filename, subdirectory)
    """
    title = case_data.get("cpws_al_title", "")
    case_type_code = case_data.get("cpws_al_type", "")
    case_type_label = CASE_TYPE_LABELS.get(case_type_code, "参考案例")
    is_guiding = case_type_code == "01"

    # 去掉标题中的案例编号前缀（frontmatter 和文件名标题部分共用）
    clean_title_for_fm = re.sub(r'^指导性案例\d+号\s*', '', title)
    clean_title_for_fm = re.sub(r'^参考案例\s*', '', clean_title_for_fm)
    if not clean_title_for_fm:
        clean_title_for_fm = title

    # IP 类型分类
    sort_name = case_data.get("cpws_al_sort_name", "")
    cpyz_text = html_to_text(case_data.get("cpws_al_cpyz", ""))
    classify_text = f"{sort_name} {title} {cpyz_text}"
    ip_type, subdirectory = classify_ip_type(classify_text)

    # 文件名
    case_num = extract_case_number(title) if is_guiding else None
    if case_num is not None:
        prefix = f"指导性案例{case_num}号 "
    else:
        prefix = f"{case_type_label} "
    short_title = re.split(r'——', clean_title_for_fm)[0].strip()
    clean_title = sanitize_filename(short_title)
    filename = f"{prefix}{clean_title}.md"

    # Frontmatter
    fm_lines = ["---"]

    fm_lines.append(f'title: "{_escape_yaml(clean_title_for_fm)}"')

    if case_num is not None:
        fm_lines.append(f"案例编号: {case_num}")

    fm_lines.append(f'案例类型: "{case_type_label}"')
    fm_lines.append('发布机关: "最高人民法院"')

    court = case_data.get("cpws_al_slfy_sf_name", "")
    if court:
        fm_lines.append(f'审理法院: "{_escape_yaml(court)}"')

    ajzh = case_data.get("cpws_al_ajzh", "")
    if ajzh:
        fm_lines.append(f'案号: "{_escape_yaml(ajzh)}"')

    date = case_data.get("cpws_al_zs_date", "")
    if date:
        fm_lines.append(f"裁判日期: {date}")

    if sort_name:
        fm_lines.append(f'案由: "{_escape_yaml(sort_name)}"')

    fm_lines.append(f'IP类型: "{ip_type}"')
    fm_lines.append("tags: []")
    fm_lines.append('引用建立: "[否]"')
    fm_lines.append("---")

    # Body 章节顺序
    sections = []

    # 关键词
    keywords = case_data.get("cpws_al_keyword", [])
    if keywords:
        sections.append(("关键词", " ".join(keywords)))

    # 裁判要点/要旨
    yz_label = "裁判要点" if is_guiding else "裁判要旨"
    if cpyz_text:
        sections.append((yz_label, cpyz_text))

    # 相关法条
    glsy = html_to_text(case_data.get("cpws_al_glsy", ""))
    if glsy:
        sections.append(("相关法条", glsy))

    # 基本案情
    jbaq = html_to_text(case_data.get("cpws_al_jbaq", ""))
    if jbaq:
        sections.append(("基本案情", jbaq))

    # 裁判结果
    cpjg = html_to_text(case_data.get("cpws_al_cpjg", ""))
    if cpjg:
        sections.append(("裁判结果", cpjg))

    # 裁判理由
    cply = html_to_text(case_data.get("cpws_al_cply", ""))
    if cply:
        sections.append(("裁判理由", cply))

    body_lines = []
    for label, content in sections:
        body_lines.append(f"## {label}")
        body_lines.append("")
        body_lines.append(content)
        body_lines.append("")

    file_content = "\n".join(fm_lines) + "\n\n" + "\n".join(body_lines)
    return file_content, filename, subdirectory


def _escape_yaml(text: str) -> str:
    """转义 YAML 字符串中的特殊字符"""
    return text.replace('"', '\\"')
