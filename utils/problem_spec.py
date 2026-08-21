"""utils/problem_spec.py — 题目规格化（借鉴折叠桌 problem_spec 思想，原创实现）。

用规则引擎把题目拆成「可判分的要求」，精确知道每道题的答案必须长什么样：
  - goals：拆出多个子目标（命令词切分）
  - requirements：可判分要求（判断题必须有"是/否"、证明题必须有"因为"等）
  - risk_flags：风险标记（多目标/漏根/端点/双重计数等）
  - risk_score：风险评分，≥阈值触发更强验证
  - answer_frame：答案框架（句子/数学式，计数/概率/判断/年龄等）

全部零 LLM 成本（纯正则），供 candidate_scorer 与 critic 使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Requirement:
    """一条可判分的要求。matches() 判断答案是否满足。"""
    name: str
    pattern: str
    strict: bool = False  # strict=True 时缺失直接判错

    def matches(self, answer: str) -> bool:
        return bool(re.search(self.pattern, answer or "", re.IGNORECASE))


@dataclass
class ProblemSpec:
    problem: str
    goals: List[str] = field(default_factory=list)
    requirements: List[Requirement] = field(default_factory=list)
    required_terms: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    risk_score: int = 0
    answer_frame: str = "math"  # math / sentence / proof
    question_kind: str = "math"  # count / probability / truth / age / judgement


# ── 命令词（切分多子目标）──
_COMMAND = r"求|计算|判断|说明|证明|给出|验证|比较|写出|指出|列出|确定|prove|show|find|determine|solve|calculate|verify|compare"


def build_problem_spec(problem: str) -> ProblemSpec:
    text = str(problem or "").strip()
    spec = ProblemSpec(problem=text)
    spec.goals = _goals(text)
    spec.requirements = _requirements(text)
    spec.required_terms = _required_terms(text)
    spec.risk_flags = _risk_flags(text, len(spec.goals))
    spec.risk_score = _risk_score(text, spec.risk_flags, len(spec.goals))
    spec.answer_frame, spec.question_kind = _answer_frame(text)
    return spec


def _goals(text: str) -> List[str]:
    """命令词切分多子目标。"""
    pieces = [p.strip() for p in re.split(
        rf"[；;]\s*|(?:并且|并|且|以及|同时)(?=\s*(?:{_COMMAND}))",
        text, flags=re.IGNORECASE) if p.strip()]
    goals = [p for p in pieces if re.search(_COMMAND + r"|是否|whether", p, re.IGNORECASE)]
    return goals or [text]


def _required_terms(text: str) -> List[str]:
    """答案必须出现的术语。"""
    required = []
    lowered = text.lower()
    if "牛顿法" in text or "newton" in lowered:
        required.append("x_{n+1}")
        if "x_0" in text or "初值" in text:
            required.append("x_1")
    if "导数判据" in text or "contraction" in lowered:
        required.extend(["导数", "收敛"])
    if "逐点" in text and "极限" in text:
        required.append("逐点")
    if "积分" in text and ("极限" in text or "比较" in text):
        required.append("积分")
    if "交集" in text and "求" in text:
        required.append("交集")
    if "精确值" in text or "exact value" in lowered:
        required.append("精确")
    if "特征值" in text and "行列式" in text and "迹" in text:
        required.extend(["det", "tr"])
    if "主曲率" in text and "高斯曲率" in text:
        required.extend(["主曲率", "高斯曲率"])
    if "生成元" in text and ("所有" in text or "全部" in text):
        required.append("生成元")
    if "基变量" in text or "运输" in text:
        required.append("总运费")
    return list(dict.fromkeys(required))


def _requirements(text: str) -> List[Requirement]:
    """可判分要求（判断题必须有判断词、证明题必须有依据词等）。"""
    reqs = []
    if re.search(r"是否|能否|可否|真假|正确与否|判断.*是否|whether", text, re.IGNORECASE):
        reqs.append(Requirement(
            "judgement", r"是|否|可以|不可以|正确|错误|成立|不成立|收敛|发散|有解|无解", strict=True))
    if re.search(r"说明.*(?:理由|为何|原因)|证明|prove|show|explain", text, re.IGNORECASE):
        reqs.append(Requirement("reasoning", r"因为|由于|依据|根据|所以|故|因此|由|implies|because|since"))
    if re.search(r"牛顿法|newton", text, re.IGNORECASE):
        reqs.append(Requirement("iteration_formula", r"x\s*_\s*\{?n\+1|迭代公式"))
    if re.search(r"(?:计算|求).*积分|integral", text, re.IGNORECASE):
        reqs.append(Requirement("integral_value", r"积分.*(?:为|=)|∫.*=|integral.*=", strict=True))
    if re.search(r"交集|intersection", text, re.IGNORECASE):
        reqs.append(Requirement("intersection", r"交集|intersection|∩"))
    if re.search(r"置信区间|区间估计|预测区间", text):
        reqs.append(Requirement("interval", r"\[[^\]]*,[^\]]*\]|（[^）]*,[^）]*）", strict=True))
    if re.search(r"假设检验|显著性|拒绝|H0|H₀", text):
        reqs.append(Requirement("hypothesis_conclusion", r"拒绝|不拒绝|接受|显著|不显著"))
    return reqs


def _risk_flags(text: str, goal_count: int) -> List[str]:
    """风险标记。"""
    lowered = text.lower()
    flags = []
    if goal_count > 1:
        flags.append("multiple_goals")
    if re.search(r"方程|根|solve|root", lowered) and not re.search(r"微分", text):
        flags.append("missing_roots")
    if re.search(r"区间|domain|interval", lowered):
        flags.append("endpoint_error")
    if re.search(r"证明|prove|show", lowered):
        flags.append("theorem_scope")
    if re.search(r"组合|排列|计数|count|combin", lowered):
        flags.append("double_counting")
    if re.search(r"概率|probability", lowered):
        flags.append("probability_range")
    if re.search(r"构造|construct|example", lowered):
        flags.append("construction_validation")
    if re.search(r"模|F_2|F₂|Z/m|mod", lowered):
        flags.append("modular_structure")
    return flags


def _risk_score(text: str, flags: List[str], goal_count: int) -> int:
    score = 0
    if goal_count > 1:
        score += 2
    if re.search(r"证明|prove|show", text, re.IGNORECASE):
        score += 2
    if re.search(r"构造|construct", text, re.IGNORECASE):
        score += 2
    if re.search(r"牛顿法|二分法|欧拉法|迭代|近似|误差|newton|bisection|euler|iteration|approx", text, re.IGNORECASE):
        score += 2
    if any(f in flags for f in ("missing_roots", "endpoint_error", "double_counting")):
        score += 1
    return min(score, 8)


def _answer_frame(text: str) -> Tuple[str, str]:
    """答案框架：sentence（句子类，需主语/单位）或 math（数学式）。"""
    if re.search(r"证明|prove|show|explain|推导", text, re.IGNORECASE):
        return "proof", "proof"
    if re.search(r"(?:求|计算|问).*概率|概率.*(?:是多少|为|等于|多少|几)|(?:多少|几).*概率|probability", text, re.IGNORECASE):
        return "sentence", "probability"
    if re.search(r"是否|是不是|能否|可否|whether", text, re.IGNORECASE):
        return "sentence", "truth"
    if re.search(r"(?:多少|几)个|number of", text, re.IGNORECASE):
        return "sentence", "count"
    if re.search(r"岁|年龄|现年", text):
        return "sentence", "age"
    return "math", "math"
