"""
M1-M8 规则检查模块注册表

职责分工：
- MECHANICAL_REGISTRY：可由 Python 正则/计算确定（被 MechanicalChecker 调用）
- SEMANTIC_MODULES：需 AI Agent 语义理解（在 SKILL.md Step 3 中由 AI Agent 执行）
"""

from .m1_template import check as check_m1
from .m2_consistency import check as check_m2
from .m3_law_articles import check as check_m3
from .m4_amount import check as check_m4
from .m5_legal_terms import check as check_m5
from .m6_date_logic import check as check_m6
from .m7_cross_reference import check as check_m7
from .m8_format import check as check_m8

# 机械性检查模块（Python 可确定，被 MechanicalChecker 调用）
MECHANICAL_REGISTRY = {
    "M3": ("法条格式校验", check_m3),
    "M4": ("金额计算校验", check_m4),
    "M6": ("日期逻辑矛盾", check_m6),
    "M8": ("格式规范", check_m8),
}

# 语义审查模块（需 AI Agent 语义理解，在 SKILL.md Step 3 中执行）
# 保留 check 函数引用以便手动调用，但 MechanicalChecker 不会自动执行
SEMANTIC_MODULES = {
    "M1": ("模板残留检测", check_m1),
    "M2": ("全文一致性", check_m2),
    "M5": ("法律术语/错别字", check_m5),
    "M7": ("交叉引用完整性", check_m7),
}

# 兼容旧代码（仅返回机械检查子集）
MODULE_REGISTRY = MECHANICAL_REGISTRY.copy()

# 完整注册表（如需手动执行全部 8 个模块）
FULL_REGISTRY = {**MECHANICAL_REGISTRY, **SEMANTIC_MODULES}
