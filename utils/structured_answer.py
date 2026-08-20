"""utils/structured_answer.py — 结构化多字段答案比较。

多问答案（如 `f_Z(z)=...; P(Z>1)=1/2`）字段顺序不同、部分字段对
部分字段错时，整体 sympy 等价会误判。本模块按分号/换行拆分字段，
逐字段等价比较，返回字段覆盖度。
"""

from __future__ import annotations

import re
from typing import Callable, List, Tuple


def split_fields(answer: str) -> List[str]:
    """按分号（首选）或换行拆分多字段答案。"""
    a = (answer or "").strip()
    if not a:
        return []
    parts = re.split(r"[；;]", a)
    if len(parts) == 1:
        parts = re.split(r"\n", a)
    return [p.strip() for p in parts if p.strip()]


def _strip_label(field: str) -> str:
    """剥离字段标签（`f_Z(z) = ...` 或 `x_11=3` → 值部分）。"""
    return re.sub(r"^[A-Za-z][\w]*(?:\([^()]*\)|_\{\w+\})?\s*=\s*", "", field.strip())


def compare_structured(
    a1: str, a2: str, sympy_equiv: Callable, tolerance: float = 1e-6
) -> Tuple[bool, bool | None, float, List[str], List[str]]:
    """结构化字段比较。

    返回 (applicable, verdict, coverage, matched_fields, mismatched_fields)。
    verdict: True=等价 / False=不等价 / None=无法判定。
    applicable: 两个答案是否都是多字段（≥2 字段）。
    """
    f1, f2 = split_fields(a1), split_fields(a2)
    if len(f1) < 2 and len(f2) < 2:
        return False, None, 0.0, [], []

    matched, mismatched = [], []
    # 贪心匹配：每个字段找另一侧第一个等价的
    used = set()
    for i, f in enumerate(f1):
        found = False
        for j, g in enumerate(f2):
            if j in used:
                continue
            eq = sympy_equiv(_strip_label(f), _strip_label(g), tolerance)
            if eq is True:
                matched.append(f)
                used.add(j)
                found = True
                break
        if not found:
            mismatched.append(f)

    total = max(len(f1), len(f2))
    coverage = len(matched) / total if total else 0.0
    if len(mismatched) == 0 and len(f1) == len(f2) and coverage >= 0.99:
        return True, True, coverage, matched, mismatched
    if len(mismatched) > 0 and coverage < 0.5:
        return True, False, coverage, matched, mismatched
    return True, None, coverage, matched, mismatched
