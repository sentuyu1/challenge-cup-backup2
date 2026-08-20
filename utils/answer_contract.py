"""utils/answer_contract.py — 答案契约检查（确定性）。

判分正确性的关键：题面问多个问项/字段时，答案漏答任何一项都算错。
本模块用纯规则（零成本）检测答案是否覆盖题面全部要求，供 critic 审计使用。
"""

from __future__ import annotations

import re


def _multi_part_count(problem: str) -> int:
    """检测题面有几个小问（(1)(2)(3) 或 ①②③ 等）。"""
    parts = re.findall(r"[(（]\s*([1-9])\s*[)）]", problem)
    circled = re.findall(r"[①②③④⑤⑥⑦⑧]", problem)
    if parts:
        return max(int(p) for p in parts)
    return len(circled)


def _requires_interval(problem: str) -> bool:
    """是否需要置信区间（双端点）。"""
    return any(k in problem for k in ("置信区间", "区间估计", "预测区间"))


def _requires_hypothesis(problem: str) -> bool:
    """是否需要假设检验结论。"""
    return any(k in problem for k in ("假设检验", "显著性", "拒绝", "H0", "H₀"))


def _requires_enumeration(problem: str) -> bool:
    """是否需要枚举全部对象。"""
    return any(k in problem for k in ("所有", "全部", "列举", "枚举", "互不同构"))


def missing_components(problem: str, answer: str) -> list:
    """返回答案缺失的组件列表（空 = 无缺失）。"""
    missing = []
    answer = answer or ""

    # 多问漏答
    n = _multi_part_count(problem)
    if n >= 2:
        # 答案里应出现对应数量的结论（按分号/换行/编号粗略计数）
        separators = len(re.findall(r"[；;]", answer)) + 1
        if separators < n:
            missing.append(f"题面有 {n} 个问项，答案可能只答了 {separators} 项")

    # 置信区间双端点
    if _requires_interval(problem):
        has_interval = bool(re.search(r"\[[^\]]*,[^\]]*\]", answer)) or \
                       bool(re.search(r"[（(][^,，]+[,，][^)）]*[)）]", answer))
        if not has_interval:
            missing.append("置信区间需同时给下限和上限")

    # 假设检验结论
    if _requires_hypothesis(problem):
        has_conclusion = any(k in answer for k in ("拒绝", "不拒绝", "接受", "显著", "不显著"))
        if not has_conclusion:
            missing.append("假设检验需给出拒绝/不拒绝结论")

    # 枚举全对象
    if _requires_enumeration(problem):
        has_count = bool(re.search(r"[共总]\s*\d+|共 \d+ 个|\d+ 个|\d+ 种", answer))
        if not has_count:
            missing.append("枚举题需列出全部对象并给总数")

    return missing
