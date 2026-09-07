# -*- coding: utf-8 -*-
"""verify_locate.py —— locate_issues.py 回归验证（DUPLICATE 检测上线后新增）

覆盖 4 个场景（对应 2026-09-07 locate 落地验收 + 三文书实测改进点）：
  A. 8 条验收样本  → 退出码 0，输出 8 条（定位零失误基线）
  B. 边界用例      → 退出码 1（AMBIGUOUS/NOT_FOUND/INVALID 行为保持）
  C. 重复条目样本  → 退出码 1 且报告含 DUPLICATE、不写输出文件
  D. occurrence 1/2 正常消歧 → 退出码 0，全 OK
  E. 唯一命中 + occurrence=2 越界 → 退出码 0 但报告含"超出命中数"警告（2026-09-07 芭迪复核发现）

用法：python feedback/tests/locate/verify_locate.py
依赖：场景 A/B/D 需要自备测试文书资产（含表格/页眉/歧义串的 docx 及其 loose JSON），
     通过环境变量 PROOFREAD_TEST_ASSETS 指向资产根目录后启用；未设置时自动 SKIP（不判 FAIL）。
     场景 C/E 的资产（dup_probe docx + loose 样本）随本仓库分发，无需额外配置。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent          # feedback/tests/locate/
PROJECT = HERE.parent.parent.parent   # 文书细节校对/
LOCATE = PROJECT / "locate_issues.py"
_ASSETS = os.environ.get("PROOFREAD_TEST_ASSETS", "")
WB_ASSETS = Path(_ASSETS) if _ASSETS else None
WB_MULTI = WB_ASSETS / "multi" if WB_ASSETS else None

CASES = [
    ("A: 8条验收样本→全OK",
     WB_ASSETS / "测试文书_技术服务合同纠纷起诉状.docx" if WB_ASSETS else None,
     HERE / "loose_issues_8条样本.json", 0, None),
    ("B: 边界用例→失败路径",
     WB_ASSETS / "测试文书_技术服务合同纠纷起诉状.docx" if WB_ASSETS else None,
     HERE / "loose_issues_边界用例.json", 1, None),
    ("C: 重复条目→DUPLICATE",
     HERE / "dup_probe_重复条目场景.docx",
     HERE / "loose_issues_重复条目_应报DUPLICATE.json", 1, "DUPLICATE"),
    ("D: occurrence消歧→全OK",
     WB_MULTI / "劳动仲裁申请书.docx" if WB_MULTI else None,
     WB_MULTI / "loose_劳动仲裁申请书.json" if WB_MULTI else None,
     0, None),
    ("E: 唯一命中+occurrence越界→警告",
     HERE / "dup_probe_重复条目场景.docx",
     HERE / "loose_issues_occurrence越界唯一命中_应警告.json", 0, "超出命中数"),
]


def run_case(name, docx, loose, want_exit, want_marker):
    if docx is None or loose is None or not docx.exists() or not loose.exists():
        missing = "(未设置 PROOFREAD_TEST_ASSETS)" if docx is None or loose is None else (
            docx.name if not docx.exists() else loose.name)
        print(f"[SKIP] {name}（资产缺失：{missing}）")
        return None
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.json"
        report = Path(td) / "report.md"
        p = subprocess.run(
            [sys.executable, str(LOCATE), str(docx), str(loose),
             "-o", str(out), "--report", str(report)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT))
        ok = p.returncode == want_exit
        marker_ok = True
        if want_marker:
            marker_ok = report.exists() and want_marker in report.read_text(encoding="utf-8")
        wrote = out.exists()
        # 失败场景必须不写输出文件
        no_write_ok = (want_exit == 0) or not wrote
        passed = ok and marker_ok and no_write_ok
        print(f"[{'PASS' if passed else 'FAIL'}] {name}（exit={p.returncode} 期望={want_exit} "
              f"marker={want_marker and marker_ok} 未写文件={no_write_ok}）")
        if not passed and p.stderr:
            print("  stderr:", p.stderr.strip()[:300])
        return passed


def main():
    results = [run_case(*c) for c in CASES]
    real = [r for r in results if r is not None]
    if not real:
        print("全部 SKIP：测试资产不存在")
        return 0
    failed = real.count(False)
    print(f"合计 {len(real)} 场景：{len(real) - failed} 通过 / {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
