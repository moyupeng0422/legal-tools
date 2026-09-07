"""M6: 日期逻辑矛盾

从实体索引提取所有日期（解析为 datetime.date 全粒度），检查阶段对顺序矛盾与未来日期。
规则详见 references/06-date-logic.md

2026-09-07 重写（P0-1）：旧版三层缺陷——比较只有年份粒度（同年月日颠倒不触发）、
lambda 配对失效（date_key_func 对所有日期返回常量元组）、规则覆盖窄。重写后：
  1. 日期解析为 date 对象，全粒度比较；解析失败报 M6_日期非法
  2. 阶段对规则表（早/晚关键词集），按日期所在段落上下文归侧
  3. 未来日期检测（落款日锚点，找不到锚点跳过）
"""

from __future__ import annotations

import datetime
import re

# ---------------------------------------------------------------------------
# 日期提取
# ---------------------------------------------------------------------------

# 三种格式：年月日 / 数字分隔 / 中文数字年月日
RE_DATE_CN = re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日')
RE_DATE_SEP = re.compile(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})')
RE_DATE_HAN = re.compile(
    r'([〇零一二三四五六七八九]{2,4})年([一二三四五六七八九十〇零]{1,3})月([一二三四五六七八九十〇零]{1,3})日'
)

_HAN_DIGIT = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _han_num_to_int(s: str) -> int | None:
    """中文数字（1-99，月/日范围）转 int：一/十/十二/二十一/三十一。"""
    if not s:
        return None
    if all(c in _HAN_DIGIT for c in s):  # 全数字式：二〇二五
        return int("".join(str(_HAN_DIGIT[c]) for c in s))
    # 含"十"的组合式
    if "十" not in s:
        return None
    try:
        tens, _, ones = s.partition("十")
        t = _HAN_DIGIT.get(tens, 1) if tens else 1
        o = _HAN_DIGIT.get(ones, 0) if ones else 0
        return t * 10 + o
    except (ValueError, TypeError):
        return None


def _extract_dates_with_context(content) -> list[dict]:
    """提取日期并解析为 date 对象，标注所在段落上下文全文。"""
    dates = []
    for para in content.paragraphs:
        text = para.text
        matches = []  # (start, end, y, m, d, raw)

        for m in RE_DATE_CN.finditer(text):
            matches.append((m.start(), m.end(), int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group()))
        for m in RE_DATE_SEP.finditer(text):
            matches.append((m.start(), m.end(), int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group()))
        for m in RE_DATE_HAN.finditer(text):
            y = _han_num_to_int(m.group(1))
            mo = _han_num_to_int(m.group(2))
            d = _han_num_to_int(m.group(3))
            if y is not None and mo is not None and d is not None:
                matches.append((m.start(), m.end(), y, mo, d, m.group()))

        for start, end, y, mo, d, raw in matches:
            # 2026-09-07 实测修正：上下文用"所在句子"而非整段——同段内多个日期
            # 分属不同阶段（如 §13 同段含验收日与提交日）只有句子级才能区分归侧
            sentence = _sentence_of(text, start)
            try:
                dt = datetime.date(y, mo, d)
            except ValueError:
                dates.append({"raw": raw, "para": para.index, "dt": None,
                              "start": start, "end": end, "context": sentence})
                continue
            dates.append({"raw": raw, "para": para.index, "dt": dt,
                          "start": start, "end": end, "context": sentence})
    return dates


_SENT_SPLIT = re.compile(r'[。；！？\n]')
_NEGATION_WORDS = ("未", "尚未", "没有", "无")


def _sentence_of(text: str, pos: int) -> str:
    """返回 pos 所在句子（以 。；！？换行 为界）。"""
    start = 0
    for m in _SENT_SPLIT.finditer(text, 0, pos + 1):
        start = m.end()
    end_m = _SENT_SPLIT.search(text, pos)
    end = end_m.start() if end_m else len(text)
    return text[start:end]


def _has_keyword(sentence: str, kw: str) -> bool:
    """句子含阶段关键词；紧邻否定词（未/尚未/没有/无）的不计数。

    背景："合同尚未签订，原告即于2025年2月20日支付订金"——否定语境的"签订"
    不能把付款日归入签订侧（2026-09-07 实测漏检根因之一）。
    """
    i = sentence.find(kw)
    while i != -1:
        prefix = sentence[max(0, i - 3):i]
        if not any(neg in prefix for neg in _NEGATION_WORDS):
            return True
        i = sentence.find(kw, i + 1)
    return False


# ---------------------------------------------------------------------------
# 阶段对规则
# ---------------------------------------------------------------------------

# (早阶段关键词集, 晚阶段关键词集, 说明, severity)
STAGE_PAIRS = [
    ({"起诉"}, {"立案"}, "起诉日不得晚于立案日", "致命"),
    ({"签订", "订立"}, {"履行", "生效"}, "合同签订日不得晚于履行/生效起算日", "严重"),
    ({"提交"}, {"验收", "审核"}, "成果提交日不得晚于验收/审核日", "严重"),
    ({"签订", "订立"}, {"付款", "支付"}, "合同签订日不得晚于首笔付款日", "严重"),
    ({"侵权"}, {"起诉"}, "侵权行为日不得晚于起诉日", "严重"),
    ({"申请"}, {"侵权"}, "专利申请日不得晚于侵权行为日", "致命"),
]

# 落款语境关键词（用于未来日期检测的锚点定位）
CLOSING_KEYWORDS = ("此致", "具状人", "起诉人", "上诉人", "申请人", "落款")


def _check_stage_pairs(dates: list[dict]) -> list[tuple]:
    """对每条阶段对规则，收集矛盾 (早侧日期, 晚侧日期, 规则说明, severity)。

    归侧依据：日期所在段落上下文含对应阶段关键词。
    同一段落同时含两侧关键词 → 该段日期对此规则不归侧（指向不明，防误报）。
    """
    violations = []
    seen: set[tuple] = set()

    for early_kws, late_kws, desc, severity in STAGE_PAIRS:
        early_side, late_side = [], []
        for d in dates:
            if d["dt"] is None:
                continue
            has_early = any(_has_keyword(d["context"], kw) for kw in early_kws)
            has_late = any(_has_keyword(d["context"], kw) for kw in late_kws)
            if has_early and has_late:
                continue  # 两侧关键词同段，指向不明
            if has_early:
                early_side.append(d)
            elif has_late:
                late_side.append(d)

        for e in early_side:
            for l in late_side:
                if e["dt"] > l["dt"]:
                    key = (e["raw"], l["raw"], desc)
                    if key not in seen:
                        seen.add(key)
                        violations.append((e, l, desc, severity))

    return violations


def _check_future_dates(dates: list[dict]) -> list[tuple]:
    """未来日期检测：晚于落款日的日期。

    锚点：优先取含落款语境关键词的段落中的日期（取最后一个），否则跳过整项检查
    （无可靠锚点不猜测，避免误报）。
    """
    anchor = None
    for d in dates:
        if d["dt"] is not None and any(kw in d["context"] for kw in CLOSING_KEYWORDS):
            anchor = d  # 循环自然取最后一个匹配段落
    if anchor is None:
        # 退化锚点（2026-09-07 实测修正：落款日期常单独成段、无落款关键词）：
        # 取最后一个非期限语境日期。"至/止/前"表述的是期限终点（如"履行期至2026年12月31日止"），
        # 不能作为"文书不晚于该日"的锚点。
        for d in reversed(dates):
            if d["dt"] is None:
                continue
            if any(w in d["context"] for w in ("至", "止", "为止", "之前", "以前")):
                continue
            anchor = d
            break
    if anchor is None:
        return []

    return [(d, anchor) for d in dates
            if d["dt"] is not None and d is not anchor and d["dt"] > anchor["dt"]]


def check(content) -> list:
    """
    执行 M6 日期逻辑检查。

    Args:
        content: DocContent 对象

    Returns:
        list[Issue]
    """
    from checker import Issue

    issues = []
    dates = _extract_dates_with_context(content)

    # 非法日期（如 2025年13月40日）
    for d in dates:
        if d["dt"] is None:
            issues.append(Issue(
                location_type="paragraph",
                para_index=d["para"],
                cell_ref=None,
                start_offset=d["start"],
                end_offset=d["end"],
                issue_type="M6_日期非法",
                severity="严重",
                action="comment_only",
                original_text=d["raw"],
                comment_text=f"[M6] 日期'{d['raw']}'不是有效日期（月/日超出范围），请核实是否笔误。",
            ))

    # 阶段对顺序矛盾
    for early, late, desc, severity in _check_stage_pairs(dates):
        issues.append(Issue(
            location_type="paragraph",
            para_index=late["para"],
            cell_ref=None,
            start_offset=late["start"],
            end_offset=late["end"],
            issue_type="M6_日期逻辑",
            severity=severity,
            action="comment_only",
            # original_text 只取晚侧日期原文：组合式"A vs B"无法通过 Writer 的原文匹配
            # （防御性跳过修订只留批注，但会产生 warning 噪音）；早侧日期已在 comment 正文中
            original_text=late["raw"],
            comment_text=(
                f"[M6] 日期逻辑矛盾：{desc}。"
                f"'{early['raw']}'（§{early['para']}）晚于'{late['raw']}'（§{late['para']}），请核实。"
            ),
        ))

    # 未来日期（晚于落款日）
    for d, anchor in _check_future_dates(dates):
        issues.append(Issue(
            location_type="paragraph",
            para_index=d["para"],
            cell_ref=None,
            start_offset=d["start"],
            end_offset=d["end"],
            issue_type="M6_未来日期",
            severity="严重",
            action="comment_only",
            original_text=d["raw"],
            comment_text=(
                f"[M6] 日期'{d['raw']}'晚于文书落款日'{anchor['raw']}'，"
                f"请核实是否笔误或确属未来事项。"
            ),
        ))

    # 检查同一事件在不同段落中的日期不一致
    issues.extend(_check_duplicate_date_issues(content, dates))

    return issues


def _check_duplicate_date_issues(content, dates: list[dict]) -> list:
    """检查同一事件在不同段落中的日期不一致"""
    issues = []
    from checker import Issue

    # 按年份分组
    by_year: dict[int, list] = {}
    for d in dates:
        if d["dt"] is None:
            continue
        by_year.setdefault(d["dt"].year, []).append(d)

    # 检查同一事件是否有多个日期
    for year, year_dates in by_year.items():
        if len(year_dates) > 5:
            # 过多相同年份日期，检查是否有同一事件的重复引用
            date_values = [d["raw"] for d in year_dates]
            if len(set(date_values)) < len(date_values) * 0.7:
                issues.append(Issue(
                    location_type="paragraph",
                    para_index=1,
                    cell_ref=None,
                    start_offset=0,
                    end_offset=0,
                    issue_type="M6_重复日期",
                    severity="一般",
                    action="comment_only",
                    original_text="",
                    comment_text=f"[M6] {year}年出现 {len(date_values)} 次日期引用（{len(set(date_values))} 个不同值），请核实是否存在同一事件日期不一致。",
                ))

    return issues
