"""utils/answer_cleanliness.py — 答案清洗与噪声检测。

判分正确性的关键：模型输出的「答案」可能被 CoT 前缀污染、截断成
LaTeX 残片、或是纯引导语（"答案如下所示"而没有实际结论）。
本模块提供零成本的检测与剥离，让"算对了但被判错"不再发生。
"""

from __future__ import annotations

import re

# ── CoT 前缀剥离 ──

_COT_HEADERS = [
    "thinking process", "thinking", "thought", "reasoning process",
    "思考过程", "推理过程", "推理草稿", "思路", "思考", "分析过程",
]

_COT_PATTERNS = [
    r"<think>.*?</think>",                      # think 标签
    r"<thinking>.*?</thinking>",
    r"<\s*thinking\s*>.*",                       # 未闭合 think 标签
]


def strip_cot_prefix(text: str) -> str:
    """剥离模型输出的 CoT 前缀（思考过程标记 / think 标签）。"""
    if not text:
        return ""
    s = text

    # 去掉 <think>...</think> 标签对（含内容）
    for pat in _COT_PATTERNS:
        s = re.sub(pat, "", s, flags=re.DOTALL | re.IGNORECASE)

    # 去掉 "Thinking Process:" / "思考过程：" 等开头的思考段落
    # 形式：标记行 + 内容，直到出现真正的章节标题
    for header in _COT_HEADERS:
        pat = re.compile(
            rf"^\s*{re.escape(header)}\s*[：:]\s*(.*?)(?=^\s*##|\Z)",
            re.DOTALL | re.IGNORECASE | re.MULTILINE)
        m = pat.search(s)
        if m and "##" not in m.group(1):
            s = pat.sub("", s, count=1)

    return s.strip()


# ── 噪声答案检测 ──

_PLACEHOLDERS = (
    "[result]", "[answer]", "[答案]", "答案", "略", "无", "none", "null",
    "占位", "待填", "todo", "n/a", "...",
)

_NOISE_PATTERNS = [
    # 纯引导语：没有实际答案内容（长词在前，避免被短词前缀抢先匹配）
    r"^\s*(?:答案如下所示|答案如下|参考答案|解答如下|结果如下|具体如下|详见如下)[：:，。]?\s*$",
    r"^\s*(?:答案为|答案是|结果是|答案为|求解得|计算得)[：:，。]?\s*$",
    r"^\s*(?:答案|解答|结果|如下|具体)[：:，。]?\s*$",
    r"^\s*(?:请|参见|见|详见)[^\n]{0,20}?$",
    r"^\s*(?:这里|下面|以下)[^\n]{0,10}?$",
]


def is_placeholder_answer(text: str) -> bool:
    """占位符/空答案检测。"""
    t = (text or "").strip().lower()
    if not t:
        return True
    return t in _PLACEHOLDERS


def is_noise_answer(text: str) -> bool:
    """检测纯引导语/元叙述碎片（没有实质答案内容）。"""
    t = (text or "").strip()
    if not t:
        return True
    for pat in _NOISE_PATTERNS:
        if re.match(pat, t, re.IGNORECASE):
            return True
    return False


def looks_like_latex_fragment(text: str) -> bool:
    """检测 LaTeX 残片（截断的 \\frac、未闭合的 $、命令残片）。"""
    t = (text or "").strip()
    if not t:
        return False
    # 未闭合的 $（奇数个）
    if t.count("$") % 2 == 1:
        return True
    # 花括号不配对
    if t.count("{") != t.count("}"):
        return True
    # 结尾是反斜杠命令残片（如 \frac、\alpha 无闭合）
    if re.search(r"\\[a-zA-Z]+$", t):
        return True
    # 常见的截断残片（\frac 后面没有完整参数）
    if re.search(r"\\frac\s*\{[^}]*$", t):
        return True
    return False


def looks_incomplete_answer(text: str) -> bool:
    """检测明显不完整的答案（结尾是等号/逗号/冒号/开括号）。"""
    t = (text or "").rstrip()
    if not t:
        return True
    # 结尾是未完标记
    if re.search(r"[-:：,，、=＝（(]\s*$", t):
        return True
    # 结尾是 "答案是" 之类引导语
    if re.search(r"(?:答案|结果|answer|result)[是为：:]\s*$", t, re.IGNORECASE):
        return True
    return False


def clean_answer(text: str) -> str:
    """综合清洗：剥离 CoT + 检测噪声/残片/不完整，返回干净答案或空串。"""
    t = strip_cot_prefix(text)
    if is_placeholder_answer(t) or is_noise_answer(t) \
            or looks_like_latex_fragment(t) or looks_incomplete_answer(t):
        return ""
    return t


def validate_structure(answer: str) -> list:
    """综合结构校验（借鉴折叠桌 Finalizer，检测多种污染）。

    返回问题列表（空 = 结构合法）。
    """
    value = (answer or "").strip()
    reasons = []
    if not value:
        return ["empty"]
    if is_placeholder_answer(value):
        reasons.append("placeholder")
    # 未闭合代码块
    if value.count("```") % 2:
        reasons.append("unclosed_code_fence")
    # 未闭合内联数学
    if value.count("$") % 2:
        reasons.append("unclosed_inline_math")
    if value.count(r"\(") != value.count(r"\)"):
        reasons.append("unclosed_inline_latex")
    if value.count(r"\[") != value.count(r"\]"):
        reasons.append("unclosed_display_latex")
    # 未闭合 LaTeX 环境
    for env in re.findall(r"\\begin\{([^}]+)\}", value):
        if len(re.findall(rf"\\end\{{{re.escape(env)}\}}", value)) < len(
                re.findall(rf"\\begin\{{{re.escape(env)}\}}", value)):
            reasons.append("unclosed_latex_environment")
            break
    # 未闭合花括号（转义感知）
    depth, escaped = 0, False
    for ch in value:
        if ch == "\\" and not escaped:
            escaped = True
            continue
        if ch == "{" and not escaped:
            depth += 1
        elif ch == "}" and not escaped:
            depth -= 1
            if depth < 0:
                reasons.append("unclosed_latex_brace")
                break
        escaped = False
    if depth != 0 and "unclosed_latex_brace" not in reasons:
        reasons.append("unclosed_latex_brace")
    # HTML/markup 碎片
    if re.search(r"</?[A-Za-z][A-Za-z0-9_-]*(?:\s+[^<>]*)?>", value):
        reasons.append("markup_fragment")
    # 控制字符
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value):
        reasons.append("control_character")
    # 元叙述文本
    if re.search(r"\b(?:this|that) (?:looks|seems) like\b|\bthe (?:prompt|instruction|user|task)\b|让我(?:验证|确认|组织)|我(?:需要|应该)|提示词", value, re.IGNORECASE):
        reasons.append("meta_text")
    # 无意义碎片（只有标点/空白）
    if not re.search(r"[\w\u4e00-\u9fff=+\-*/^\\]", value):
        reasons.append("meaningless_fragment")
    return reasons
