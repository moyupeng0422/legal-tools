"""M4: 金额计算校验

检查金额相关错误：加总、大小写对应、单位一致性。
规则详见 references/04-amount-calculation.md
"""

from __future__ import annotations

import re


def check(content) -> list:
    """
    执行 M4 金额计算校验。

    Args:
        content: DocContent 对象

    Returns:
        list[Issue]
    """
    from checker import Issue

    issues = []
    issues.extend(_check_totals(content))
    issues.extend(_check_table_totals(content))
    issues.extend(_check_upper_lower(content))
    issues.extend(_check_unit_consistency(content))
    return issues


# ---------------------------------------------------------------------------
# 表格分项加总（2026-09-07 新增，P0-2）
# 旧版 _check_totals 只遍历 content.paragraphs，表格单元格存 content.tables，
# 表格合计结构性不可达。本函数按表分组做分项加总比对。
# ---------------------------------------------------------------------------

RE_CELL_AMOUNT = re.compile(r'^\s*[¥￥]?\s*([\d,，]+(?:\.\d+)?)\s*(万元|元)?\s*$')
RE_TOTAL_LABEL = re.compile(r'(合计|总计|共计)')
RE_AMOUNT_INNER = re.compile(r'[¥￥]?\s*([\d,，]+(?:\.\d+)?)\s*(万元|元)?')


def _parse_amount(text: str) -> tuple[float, str] | None:
    """单元格纯金额解析（含千分位逗号/全角逗号），非纯金额返回 None。"""
    m = RE_CELL_AMOUNT.match(text)
    if not m:
        return None
    num = float(m.group(1).replace(',', '').replace('，', ''))
    return num, (m.group(2) or '')


def _check_table_totals(content) -> list[Issue]:
    """检查表格中分项加总是否等于合计行。"""
    from checker import Issue

    issues = []
    by_table: dict[int, list] = {}
    for cell in content.tables:
        by_table.setdefault(cell.table_idx, []).append(cell)

    for t_idx, cells in by_table.items():
        # 定位合计行（取首个含合计字样的行）
        total_rows = sorted({c.row for c in cells if RE_TOTAL_LABEL.search(c.text)})
        if not total_rows:
            continue
        total_row = total_rows[0]

        # 分项：合计行之前所有行的纯金额单元格
        items: list[tuple[float, str]] = []
        for c in cells:
            if c.row >= total_row:
                continue
            parsed = _parse_amount(c.text)
            if parsed:
                items.append(parsed)

        # 合计值：合计行中的金额（标签单元格内嵌金额 + 独立金额单元格）
        totals: list[tuple[float, str, int, str, int, int]] = []  # (数值, 单位, 列, 原文逐字串, start, end)
        for c in cells:
            if c.row != total_row:
                continue
            raw_m = RE_AMOUNT_INNER.search(c.text) if RE_TOTAL_LABEL.search(c.text) else RE_CELL_AMOUNT.match(c.text)
            if raw_m:
                raw = raw_m.group(0).strip()
                num = float(raw_m.group(1).replace(',', '').replace('，', ''))
                # offset 相对单元格首段文本（Writer 取 cell.paragraphs[0]）；错位由 Writer 原文校验兜底
                start = c.text.find(raw)
                totals.append((num, raw_m.group(2) or '', c.col, raw, start, start + len(raw)))
        if not totals:
            continue
        total, total_unit, total_col, total_raw, total_start, total_end = totals[0]

        # 单位归一：元/无单位视为同口径；出现"万元"与其他口径混用则不比对
        units = {u for _, u in items} | {total_unit}
        if '万元' in units and len(units) > 1:
            issues.append(Issue(
                location_type="table_cell",
                para_index=0,
                cell_ref=(t_idx, total_row, total_col),
                start_offset=0,
                end_offset=0,
                issue_type="M4_表格单位",
                severity="严重",
                action="comment_only",
                original_text="",
                comment_text=f"[M4] 表{t_idx + 1}中分项与合计的金额单位混用（元/万元），无法自动比对加总，请人工核对。",
            ))
            continue

        item_sum = sum(num for num, _ in items)
        if items and abs(item_sum - total) > 0.01 * max(total, 1):
            diff = abs(item_sum - total)
            severity = "致命" if diff > 100 else "严重"
            issues.append(Issue(
                location_type="table_cell",
                para_index=0,
                cell_ref=(t_idx, total_row, total_col),
                start_offset=total_start,
                end_offset=total_end,
                issue_type="M4_表格加总",
                severity=severity,
                action="replace",
                # original_text 必须从原文逐字截取（Writer 原文校验要求，2026-09-07 修复：
                # 旧版 f"{total:,.2f}" 强制加 .00，与单元格原文 "105,000" 不一致，修订永远被跳过）
                original_text=total_raw,
                suggested_text=f"{item_sum:,.2f}{total_unit}",  # 建议值保留原单位，避免替换后丢"元/万元"
                comment_text=(
                    f"[M4] 表{t_idx + 1}金额加总错误：分项合计 {item_sum:,.2f} ≠ 合计 {total:,.2f}，"
                    f"差异 {diff:,.2f}，请核实。"
                ),
            ))

    return issues


def _check_totals(content) -> list[Issue]:
    """检查分项加总是否等于合计"""
    from checker import Issue
    issues = []

    for para in content.paragraphs:
        # 查找合计行
        sum_match = re.search(r'(?:合计|共计|总计)\s*[：:]?\s*[¥￥]?\s*([\d,]+\.?\d*)\s*(元|万元)?', para.text)
        if not sum_match:
            continue

        total = float(sum_match.group(1).replace(',', ''))
        unit = sum_match.group(2) or "元"

        # 查找同一行或前几行的分项
        items = re.findall(r'(?:\(\d+)\)|（\d+）)\s*[、，,]\s*[¥￥]?\s*([\d,]+\.?\d*)\s*(?:元|万元)?', para.text)
        if not items:
            continue

        item_sum = sum(float(item.replace(',', '')) for item in items)
        if abs(item_sum - total) > 0.01 * max(total, 1):
            diff = abs(item_sum - total)
            severity = "致命" if diff > 100 else "严重"
            issues.append(Issue(
                location_type="paragraph",
                para_index=para.index,
                cell_ref=None,
                start_offset=sum_match.start(),
                end_offset=sum_match.end(),
                issue_type="M4_金额计算",
                severity=severity,
                action="replace",
                original_text=f"{sum_match.group(1)}{total:,.2f}{unit}",
                suggested_text=f"{item_sum:,.2f}{unit}",
                comment_text=(
                    f"[M4] 金额加总错误：分项合计 {item_sum:,.2f}{unit} ≠ 合计 {total:,.2f}{unit}，"
                    f"差异 {diff:,.2f}{unit}"
                ),
            ))

    return issues


def _check_upper_lower(content) -> list[Issue]:
    """检查大写金额与小写金额是否对应（就近配对，2026-09-07 修复全交叉误报）"""
    from checker import Issue
    issues = []

    # 小写金额：排除紧跟 年/月/日/条/款/项/号/期 的数字（日期/法条/案号非金额）；万元单位换算
    num_pattern = re.compile(r'([\d,]+(?:\.\d+)?)\s*(万元|元)?(?!年|月|日|条|款|项|号|期)')
    # 前置 lookbehind 排除"5万元""1.5万元"式小写+单位组合中的"万元"被误抓为大写金额（2026-09-07 实测噪声源）
    cn_pattern = re.compile(r'(?<![\d.,%￥¥])(?:人民币)?([零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+(?:元整|元|整)?)')

    for para in content.paragraphs:
        num_amounts = []
        for m in num_pattern.finditer(para.text):
            value = float(m.group(1).replace(',', ''))
            if m.group(2) == "万元":
                value *= 10000
            num_amounts.append((value, m.start(), m.end()))

        cn_matches = [(m.group(1), m.start(), m.end()) for m in cn_pattern.finditer(para.text)]
        if not cn_matches:
            continue

        used: set[int] = set()
        for cn_val, cn_start, cn_end in cn_matches:
            cn_number = _cn_to_number(cn_val)
            if cn_number is None:
                # 大写金额存在但无法解析：独立提示，不静默跳过也不按 0 误判
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=cn_start,
                    end_offset=cn_end,
                    issue_type="M4_大写无法解析",
                    severity="一般",
                    action="comment_only",
                    original_text=cn_val,
                    comment_text=(
                        f"[M4] 大写金额'{cn_val}'无法自动解析，"
                        f"请人工核对其与小写金额是否一致。"
                    ),
                ))
                continue

            # 就近贪婪配对：每个大写金额配距离最近且未被占用的小写金额
            cn_center = (cn_start + cn_end) / 2
            candidates = [i for i in range(len(num_amounts)) if i not in used]
            if not candidates:
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=cn_start,
                    end_offset=cn_end,
                    issue_type="M4_大小写缺对应",
                    severity="一般",
                    action="comment_only",
                    original_text=cn_val,
                    comment_text=f"[M4] 大写金额'{cn_val}'（{cn_number:,.2f}元）同段未找到对应小写金额，请核实。",
                ))
                continue
            best = min(candidates,
                       key=lambda i: abs((num_amounts[i][1] + num_amounts[i][2]) / 2 - cn_center))
            used.add(best)
            num_number = num_amounts[best][0]

            if abs(cn_number - num_number) > 0.01:
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=cn_start,
                    end_offset=cn_end,
                    issue_type="M4_大小写",
                    severity="严重",
                    action="comment_only",
                    original_text=cn_val,
                    comment_text=(
                        f"[M4] 大写金额'{cn_val}'（{cn_number:,.2f}元）"
                        f"与就近小写金额（{num_number:,.2f}元）不一致，请核实。"
                    ),
                ))

    return issues


def _check_unit_consistency(content) -> list[Issue]:
    """检查全文金额单位是否一致"""
    from checker import Issue
    issues = []
    units_found = set()
    for para in content.paragraphs:
        for m in re.finditer(r'([\d,]+\.?\d*)\s*(元|万元)', para.text):
            units_found.add(m.group(2))

    if "元" in units_found and "万元" in units_found:
        # 同时出现元和万元，检查具体位置
        for para in content.paragraphs:
            if re.search(r'\d+\.?\d*\s*万元', para.text) and re.search(r'\d+\.?\d*\s*元(?![万])', para.text):
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=para.index,
                    cell_ref=None,
                    start_offset=0,
                    end_offset=0,
                    issue_type="M4_单位",
                    severity="严重",
                    action="comment_only",
                    original_text="",
                    comment_text="[M4] 同一段落中同时使用'元'和'万元'作为金额单位，可能导致理解歧义。",
                ))

    return issues


_CN_DIGIT = {"零": 0, "壹": 1, "贰": 2, "叁": 3, "肆": 4, "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9}
_CN_UNIT = {"拾": 10, "佰": 100, "仟": 1000}
_CN_BIG = {"万": 10 ** 4, "亿": 10 ** 8}


def _cn_to_number(cn_str: str) -> float | None:
    """中文大写金额转数字：支持 零壹贰叁…玖/拾佰仟/万亿 全组合。

    例：壹拾万→100000，拾伍万→150000（省略一），壹拾万零伍佰→100500，壹亿贰仟万→120000000。
    解析失败返回 None（调用方输出"无法解析"独立提示，不再按 0 误判）。
    """
    s = cn_str
    for suffix in ("元整", "元", "整", "正"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    s = s.strip("零")
    if not s:
        return None

    total = 0      # 已完成的万/亿大节
    section = 0    # 当前大节内累计值
    value = 0      # 当前待乘单位系数的数字
    seen_digit = False
    for ch in s:
        if ch in _CN_DIGIT:
            value = _CN_DIGIT[ch]
            seen_digit = True
        elif ch in _CN_UNIT:
            section += (value if value else 1) * _CN_UNIT[ch]  # "拾伍"式省略一按 1 处理
            value = 0
        elif ch in _CN_BIG:
            section = (section + value) * _CN_BIG[ch]
            total += section
            section = value = 0
        elif ch == "零":
            continue
        else:
            return None

    result = total + section + value
    if not seen_digit and result == 0:
        return None
    return float(result)
