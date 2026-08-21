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


def _compact(value: str) -> str:
    return re.sub(r"[\s{}()\[\]\\,，。；;：:_]", "", str(value or "").lower()).replace("−", "-")


def required_terms(problem: str) -> list:
    """识别答案必须出现的术语（对齐折叠桌 problem_spec 思想）。

    某些题目的判分要求答案必须含特定术语/字段，缺失即判错。
    """
    required = []
    text = (problem or "").lower()
    if "牛顿法" in problem or "newton" in text:
        required.append("x_{n+1}")
        if "x_0" in problem or "初值" in problem:
            required.append("x_1")
    if "导数判据" in problem or "contraction" in text:
        required.extend(["导数", "收敛"])
    if "逐点" in problem and "极限" in problem:
        required.append("逐点")
    if "积分" in problem and ("极限" in problem or "比较" in problem):
        required.append("积分")
    if "交集" in problem and "求" in problem:
        required.append("交集")
    if "精确值" in problem or "exact value" in text:
        required.append("精确")
    if "特征值" in problem and "行列式" in problem and "迹" in problem:
        required.extend(["det", "tr"])
    if "主曲率" in problem and "高斯曲率" in problem:
        required.extend(["主曲率", "高斯曲率"])
    if "生成元" in problem and ("所有" in problem or "全部" in problem):
        required.append("生成元")
    if "基变量" in problem or "运输问题" in problem:
        required.append("总运费")
    return list(dict.fromkeys(required))


def missing_required_terms(answer: str, terms: list) -> list:
    """返回答案缺失的必须术语。"""
    compact = _compact(answer)
    missing = []
    for term in terms:
        t = _compact(term)
        if t and t not in compact:
            missing.append(term)
    return missing


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
