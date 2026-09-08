"""M8: 格式规范

检查案号格式、法院名称完整性、序号连续性、称谓一致性。
规则详见 references/08-format-spec.md
"""

from __future__ import annotations

import re


def check(content) -> list:
    """
    执行 M8 格式规范检查。

    Args:
        content: DocContent 对象

    Returns:
        list[Issue]
    """
    from checker import Issue

    issues = []
    issues.extend(_check_case_number_format(content))
    issues.extend(_check_court_name(content))
    issues.extend(_check_numbering_continuity(content))
    issues.extend(_check_title_consistency(content))
    return issues


def _check_case_number_format(content) -> list:
    """检查案号格式

    2026-09-08 缺陷修复（芭迪实测，discussions/2026-09-08-实测新缺陷两则.md 缺陷二）：
    旧版第三条 bad_patterns 从 (\\d{4}) 起匹配、(\\S+?) 贪吞 ")浙0106"，把半角括号
    案号 (2025) 误诊为"缺括号"；匹配起点落在 "(" 之后导致批注锚点截断；且正确示例
    自身用半角括号——用户照改后仍命中，形成误报死循环。

    现改为：匹配完整案号形态（括号字符入捕获组）后按括号形态四态分支——
      全角配对 （2025）→ 规范，不报
      半角配对 (2025)  → 应改为全角
      完全无括号 2025  → 补括号
      左右不配对       → 报错
    original_text 取 m.group() 全量（含左括号），保证批注锚点完整。
    """
    issues = []
    from checker import Issue

    # 示范文本必须自身合规：案号年份括号规范为全角
    EXAMPLE = "（2025）浙01民初123号"

    # 全角括号案号带多余"第"/"字第"（维持原有两条，仅全角形态）
    bad_patterns = [
        (re.compile(r'（(\d{4})）(\S+?)第(\d+)号'), "案号中不应有'第'字"),
        (re.compile(r'（(\d{4})）(\S+?)字第(\d+)号'), "案号中不应有'字第'"),
    ]

    # 完整案号形态：[左括号] YYYY [右括号] 法院代字 类型字 程序字 编号 号
    _RE_CASE_NO_SHAPE = re.compile(
        r'([（(]?)(\d{4})([)）]?)(\S+?)(民|行|刑|商|执)(初|终|再|监|恢)(\d+)号'
    )

    for para in content.paragraphs:
        for pattern, desc in bad_patterns:
            for m in pattern.finditer(para.text):
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=m.start(),
                    end_offset=m.end(),
                    issue_type="M8_案号格式",
                    severity="严重",
                    action="comment_only",
                    original_text=m.group(),
                    comment_text=f"[M8] 案号格式疑似错误：'{m.group()}'——{desc}。正确格式示例：{EXAMPLE}",
                ))

        # 四态分支检测
        for m in _RE_CASE_NO_SHAPE.finditer(para.text):
            left, right = m.group(1), m.group(3)
            if left == "（" and right == "）":
                continue  # 全角配对：规范形态，通过
            whole = m.group()
            suggested = f"（{m.group(2)}）{m.group(4)}{m.group(5)}{m.group(6)}{m.group(7)}号"
            if left and right:
                # 半角配对 (2025)
                desc = f"案号年份括号使用了半角括号，应改为全角：{suggested}"
            elif not left and not right:
                # 完全无括号
                desc = f"案号缺少年份括号，应为：{suggested}"
            else:
                # 左右不配对（含只有一侧）
                desc = "案号年份括号左右不配对，请核实（应为一对全角括号）"
            issues.append(Issue(
                location_type="paragraph",
                para_index=para.index,
                cell_ref=None,
                start_offset=m.start(),
                end_offset=m.end(),
                issue_type="M8_案号格式",
                severity="严重",
                action="comment_only",
                original_text=whole,
                comment_text=f"[M8] 案号格式疑似错误：'{whole}'——{desc}。正确格式示例：{EXAMPLE}",
            ))

    return issues


# 直辖市（中级法院全称须含"市"+序号）
MUNICIPALITIES = {"北京", "上海", "天津", "重庆"}
# 缩写序号字（"一中院""知识产权法院"等中的序号部分）
_SEQ_CHARS = "第一二三四五六七八九十"
# 常见介词/动词前缀（"向杭州中院""本案由北京一中院"等句式粘连）
_LEADING_PARTICLES = "向由在从对被和与经诉至到让令责"

_RE_ZH_BEFORE_ZHONGYUAN = re.compile(r'([一-鿿]{1,6})中院')


def _extract_court_abbrev(raw: str) -> tuple[str, str] | None:
    """从粘连串中提取 (地名, 序号)。

    输入形如"向杭州""本案由北京""特向杭州"（正则贪婪捕获的前缀+地名+可能序号）。
    先从尾部剥离序号字；再从尾部尝试 2-4 字后缀作为地名——若后缀的前一字符
    是粘连介词/动词（"向杭州"的"向"、"特向杭州"的"向"），则后缀即地名。
    地名不足 2 字返回 None（信息不足，不猜）。
    """
    seq = ""
    s = raw
    while s and s[-1] in _SEQ_CHARS:
        seq = s[-1] + seq
        s = s[:-1]
    if len(s) < 2:
        return None
    # 尾部裁剪：后缀前一字符是粘连介词 → 后缀为地名（解决"特向杭州""原告向绍兴"式粘连）
    for k in (4, 3, 2):
        if len(s) > k and s[-k - 1] in _LEADING_PARTICLES:
            return s[-k:], seq
    return s, seq


def _check_court_name(content) -> list:
    """检查法院名称完整性"""
    issues = []
    from checker import Issue

    for para in content.paragraphs:
        for m in _RE_ZH_BEFORE_ZHONGYUAN.finditer(para.text):
            extracted = _extract_court_abbrev(m.group(1))
            if extracted is None:
                continue
            city, seq = extracted
            # 2026-09-07 修复：旧版直接拼 group(1)+"中级人民法院"——既丢"市"（杭州中院→杭州中级人民法院），
            # 又把句式粘连前缀（"向/由/本案由"）和序号（"北京一中院"的"一"）拼进全称。
            # 提取结果干净（剥介词后 2-4 字）才给具体建议全称；粘连复杂时退化为通用提示，不猜全称。
            if city in MUNICIPALITIES:
                seq_hint = f"第{seq}" if seq else "第○"
                full = f"{city}市{seq_hint}中级人民法院"
                comment = (
                    f"[M8] 法院名称疑似缩写：'{m.group(0)}'，推测全称为'{full}'（请人工确认序号）。"
                    f"起诉状首部需使用全称。"
                )
            elif len(city) <= 4:
                full = city if city.endswith("市") else city + "市"
                full += "中级人民法院"
                comment = (
                    f"[M8] 法院名称疑似缩写：'{m.group(0)}'，推测全称为'{full}'（请人工确认）。"
                    f"起诉状首部需使用全称。"
                )
            else:
                comment = (
                    f"[M8] 法院名称疑似缩写：'{m.group(0)}'。中级法院全称须含'市'"
                    f"（如'XX市中级人民法院'），请核实后改用全称。"
                )
            issues.append(Issue(
                location_type="paragraph",
                para_index=para.index,
                cell_ref=None,
                start_offset=m.start(),
                end_offset=m.end(),
                issue_type="M8_法院名称",
                severity="一般",
                action="comment_only",
                original_text=m.group(0),
                comment_text=comment,
            ))

    return issues


def _check_numbering_continuity(content) -> list:
    """检查序号连续性"""
    issues = []
    from checker import Issue

    # 中文数字序号：一、二、三……
    cn_nums = "一二三四五六七八九十"
    cn_pattern = re.compile(r'([一二三四五六七八九十]+)[、．.]')

    # 阿拉伯数字序号：1. 2. 3. 或 (1) (2) (3)
    ar_pattern = re.compile(r'(?:^|\s)(\d+)\s*[、．.)](?!\d)')

    # 证据编号：证据一、证据二……
    ev_pattern = re.compile(r'证据([一二三四五六七八九十\d]+)\s*[：:]')

    for para in content.paragraphs:
        # 检查中文数字序号连续性
        cn_matches = list(cn_pattern.finditer(para.text))
        if len(cn_matches) >= 3:
            nums = []
            for m in cn_matches:
                num_str = m.group(1)
                num = _cn_to_int(num_str)
                nums.append((num, m))
            gaps = _find_gaps(nums)
            for missing, after_match in gaps:
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=after_match.start(),
                    end_offset=after_match.end(),
                    issue_type="M8_序号跳号",
                    severity="严重",
                    action="comment_only",
                    original_text=after_match.group(),
                    comment_text=f"[M8] 中文序号不连续：'{after_match.group()}'前缺少序号'{missing}'，请核实是否遗漏。",
                ))

        # 检查证据编号连续性
        ev_matches = list(ev_pattern.finditer(para.text))
        if len(ev_matches) >= 3:
            ev_nums = []
            for m in ev_matches:
                num_str = m.group(1)
                num = _cn_to_int(num_str)
                ev_nums.append((num, m))
            gaps = _find_gaps(ev_nums)
            for missing, after_match in gaps:
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=after_match.start(),
                    end_offset=after_match.end(),
                    issue_type="M8_证据编号",
                    severity="严重",
                    action="comment_only",
                    original_text=after_match.group(),
                    comment_text=f"[M8] 证据编号不连续：'{after_match.group()}'前缺少'{missing}'，请核实是否遗漏证据。",
                ))

    return issues


def _check_title_consistency(content) -> list:
    """检查称谓一致性"""
    issues = []
    from checker import Issue

    # 当事人称谓变体
    party_titles = ["原告", "被告", "申请人", "被申请人", "上诉人", "被上诉人", "第三人"]
    court_titles = ["本院", "贵院", "法院"]

    party_usage = {}  # title → [(para_index, text_excerpt)]
    for para in content.paragraphs:
        for title in party_titles:
            if title in para.text:
                party_usage.setdefault(title, []).append(para.index)

    court_usage = {}
    for para in content.paragraphs:
        for title in court_titles:
            if title in para.text:
                court_usage.setdefault(title, []).append(para.index)

    # 检查是否有多个当事人称谓在混用（可能需要统一）
    used_party_titles = {t for t, locs in party_usage.items() if len(locs) >= 2}
    if len(used_party_titles) >= 3:
        # 检查文档开头是否定义了简称映射
        has_abbrev_def = any(
            re.search(r'(?:以下简称|简称)', para.text)
            for para in content.paragraphs[:5]
        )
        if not has_abbrev_def:
            titles_str = "、".join(sorted(used_party_titles))
            issues.append(Issue(
                location_type="paragraph",
                para_index=1,
                cell_ref=None,
                start_offset=0,
                end_offset=0,
                issue_type="M8_称谓一致",
                severity="一般",
                action="comment_only",
                original_text="",
                comment_text=f"[M8] 当事人称谓混用：全文中使用了'{titles_str}'等多种称谓，且未发现简称定义。如为同一主体请统一称谓。",
            ))

    return issues


def _cn_to_int(cn: str) -> int:
    """中文数字转整数（支持一到九十九）"""
    cn_map = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    }

    if cn.isdigit():
        return int(cn)

    result = 0
    for i, ch in enumerate(cn):
        val = cn_map.get(ch, 0)
        if ch == "十":
            if i == 0:
                result += 10
            else:
                result += val
        else:
            result += val
    return result


def _int_to_cn(n: int) -> str:
    """整数转中文数字"""
    cn_chars = "零一二三四五六七八九十"
    if n <= 10:
        return cn_chars[n]
    if n < 20:
        return "十" + (cn_chars[n - 10] if n % 10 else "")
    return str(n)


def _find_gaps(nums: list[tuple]) -> list:
    """检查序号列表是否有跳号，返回 (缺失序号, 对应的match)"""
    gaps = []
    if len(nums) < 2:
        return gaps

    # 检查是否为递增序列（允许独立章节重启）
    # 找连续递增子段
    segments = []
    current_seg = [nums[0]]
    for i in range(1, len(nums)):
        if nums[i][0] > nums[i - 1][0]:
            current_seg.append(nums[i])
        else:
            if len(current_seg) >= 3:
                segments.append(current_seg)
            current_seg = [nums[i]]
    if len(current_seg) >= 3:
        segments.append(current_seg)

    for seg in segments:
        for i in range(1, len(seg)):
            expected = seg[i - 1][0] + 1
            actual = seg[i][0]
            if actual > expected:
                missing = _int_to_cn(expected) if expected <= 99 else str(expected)
                gaps.append((missing, seg[i][1]))

    return gaps
