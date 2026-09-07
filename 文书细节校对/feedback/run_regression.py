"""
回归测试：用漏检案例样本验证机械检查模块（M3/M4/M6/M8）不退化。

样本格式：feedback/tests/*.json，每个文件一个案例：
{
  "id": "2026-08-19-01",
  "module": "M5",                      // 期望命中的模块（机械模块才可回归；M1/M2/M5/M7 为语义模块，跳过并提示）
  "text": "…原文片段…",                 // 待检查文本（作为单个段落构造 DocContent）
  "paragraphs": ["段1", "段2"],         // 可选：多段落样本，与 text 二选一（2026-09-07 A0 新增，M6 阶段对矛盾需要跨段落）
  "table": {"rows": [["甲", "50,000"], ["合计", "105,000"]]},
                                       // 可选：表格样本，构造 CellInfo 注入 content.tables（2026-09-07 A0 新增，M4 表格加总）
  "expect_issue_type": "M5_术语",       // 期望出现的 issue_type（前缀匹配）
  "expect_original_text": "订金",       // 可选：期望 Issue 的 original_text 包含此子串
  "expect_absent": true,                // 可选：反向样本——期望 NOT 命中 expect_issue_type（防误报回归）
  "description": "定金/订金漏检"
}

用法：
    python feedback/run_regression.py            # 跑全部样本
    python feedback/run_regression.py 2026-08-19-01  # 跑指定样本

规则：改 rules/*.py 后必须跑一次，全部 PASS 才算改完。
"""
import importlib
import json
import sys
from pathlib import Path

# Windows 控制台默认 GBK，强制 UTF-8 输出防中文乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 项目根目录加入 sys.path（脚本位于 feedback/ 下）
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checker import DocContent, ParagraphInfo, MechanicalChecker  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent / "tests"
SEMANTIC_MODULES = {"M1", "M2", "M5", "M7"}


def load_samples() -> list[dict]:
    if not TESTS_DIR.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(TESTS_DIR.glob("*.json"))]


def smoke_import() -> tuple[bool, str]:
    """import 冒烟测试：遍历 rules 全模块 + checker，任何 ImportError/NameError 直接 FAIL。

    背景：2026-09-07 WorkBuddy 实测发现 rules/ 8 个模块缺 `from __future__ import annotations`，
    Python >=3.13 下 `list[Issue]` 注解在模块加载期求值，import 即 NameError——skill 整体不可运行。
    本冒烟防止同类回归再次静默炸掉整个 skill。
    """
    targets = ["checker"] + sorted(
        f"rules.{p.stem}" for p in (ROOT / "rules").glob("m*.py")
    )
    for name in targets:
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001——冒烟测试需捕获一切加载期异常
            return False, f"import {name} 失败: {type(e).__name__}: {e}"
    return True, f"import 冒烟通过（{len(targets)} 个模块: {'/'.join(targets)}）"


def _build_content(sample: dict) -> DocContent:
    """按样本格式构造 DocContent（支持 text / paragraphs / table 三种载体，可组合）。"""
    paragraphs = []
    if "paragraphs" in sample:
        texts = sample["paragraphs"]
    elif "text" in sample:
        texts = [sample["text"]]
    else:
        texts = []  # 纯表格样本
    for idx, text in enumerate(texts, start=1):
        paragraphs.append(ParagraphInfo(text=text, index=idx, style="Normal"))

    tables = []
    if "table" in sample:
        from checker import CellInfo
        for r_idx, row in enumerate(sample["table"]["rows"]):
            for c_idx, text in enumerate(row):
                tables.append(CellInfo(text=text, row=r_idx, col=c_idx, table_idx=0))

    return DocContent(paragraphs=paragraphs, tables=tables)


def run_sample(sample: dict) -> tuple[bool, str]:
    """跑单个样本，返回 (通过, 说明)。"""
    if sample["module"] in SEMANTIC_MODULES:
        return False, (f"语义模块 {sample['module']} 无法机械回归——请人工对照 "
                       f"references/ 规则或 LESSONS.md 验证")

    content = _build_content(sample)
    checker = MechanicalChecker()
    issues = checker.check(content)

    matched = [i for i in issues if i.issue_type.startswith(sample["expect_issue_type"])]

    # 反向样本：期望 NOT 命中（防误报回归）
    if sample.get("expect_absent"):
        if matched:
            return False, (f"期望不命中 {sample['expect_issue_type']}，"
                           f"实际命中 {len(matched)} 条（疑似误报）")
        return True, "确认无误报"

    if not matched:
        return False, f"未命中 {sample['expect_issue_type']}（实际检出：{[i.issue_type for i in issues] or '无'}）"

    expect_text = sample.get("expect_original_text")
    if expect_text and not any(expect_text in i.original_text for i in matched):
        return False, f"命中 {sample['expect_issue_type']} 但 original_text 均不含「{expect_text}」"

    return True, f"命中 {len(matched)} 条 {sample['expect_issue_type']}"


def main():
    ok, msg = smoke_import()
    print(f"[{'PASS' if ok else 'FAIL'}] import 冒烟: {msg}")
    if not ok:
        return 1

    only_id = sys.argv[1] if len(sys.argv) > 1 else None
    samples = load_samples()
    if only_id:
        samples = [s for s in samples if s["id"] == only_id]
        if not samples:
            print(f"未找到样本 {only_id}"); return 1
    if not samples:
        print("无测试样本（feedback/tests/ 为空）"); return 0

    failed = skipped = 0
    for s in samples:
        ok, msg = run_sample(s)
        tag = "PASS" if ok else ("SKIP" if "语义模块" in msg else "FAIL")
        if not ok and tag == "FAIL":
            failed += 1
        if tag == "SKIP":
            skipped += 1
        print(f"[{tag}] {s['id']} ({s.get('description', '')}): {msg}")

    print(f"\n合计 {len(samples)} 个样本：{len(samples) - failed - skipped} 通过 / {failed} 失败 / {skipped} 跳过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
