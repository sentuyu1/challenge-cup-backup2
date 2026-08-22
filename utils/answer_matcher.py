"""utils/answer_matcher.py — 答案符号等价匹配。

判分正确性的关键：`πie` 与 `E*I*pi`、`2*sqrt(2)*pi` 与 `2π√2`、
`\\frac{a}{b}` 与 `a/b` 在数学上等价，但逐字比对判为不同。
本模块用 sympy 做符号等价判定，避免"算对了但被判错"。
"""

from __future__ import annotations

import re

from utils.structured_answer import compare_structured

# unicode 常量归一化
_UNICODE_REPLACEMENTS = [
    ("−", "-"), ("–", "-"), ("—", "-"), ("×", "*"), ("·", "*"), ("⋅", "*"),
    ("÷", "/"), ("²", "**2"), ("³", "**3"), ("½", "(1/2)"), ("∞", "oo"),
]


def _latex_to_text(s: str) -> str:
    """LaTeX 转 sympy 可解析文本（\\frac → 除法、\\sqrt → sqrt、\\pi → pi）。"""
    s = s.replace("$$", " ").replace("$", " ")
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")

    # \frac{a}{b} → ((a)/(b))，支持嵌套花括号
    def conv_frac(txt: str) -> str:
        out, i = [], 0
        while True:
            p = txt.find("\\frac", i)
            if p == -1:
                out.append(txt[i:])
                return "".join(out)
            out.append(txt[i:p])
            cursor = p + len("\\frac")
            while cursor < len(txt) and txt[cursor].isspace():
                cursor += 1
            if cursor >= len(txt) or txt[cursor] != "{":
                out.append(txt[p:p + len("\\frac")])
                i = cursor
                continue
            depth, num_start, j = 0, cursor + 1, cursor
            while j < len(txt):
                if txt[j] == "{":
                    depth += 1
                elif txt[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            numerator = txt[num_start:j]
            cursor = j + 1
            while cursor < len(txt) and txt[cursor].isspace():
                cursor += 1
            if cursor >= len(txt) or txt[cursor] != "{":
                out.append(txt[p:cursor])
                i = cursor
                continue
            depth, den_start, k = 0, cursor + 1, cursor
            while k < len(txt):
                if txt[k] == "{":
                    depth += 1
                elif txt[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            denominator = txt[den_start:k]
            out.append(f"(({conv_frac(numerator)})/({conv_frac(denominator)}))")
            i = k + 1

    s = conv_frac(s)
    # \sqrt[n]{x} → (x)**(1/n)，\sqrt{x} → sqrt(x)
    s = re.sub(r"\\sqrt\s*\[\s*([^\[\]]+)\s*\]\s*\{([^{}]*)\}", r"((\2)**(1/(\1)))", s)
    for _ in range(4):
        new = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"(sqrt(\1))", s)
        if new == s:
            break
        s = new
    s = re.sub(r"\\sqrt\s*(\d+)", r"(sqrt(\1))", s)
    for cmd in ("operatorname", "mathrm", "text", "mathbf", "boldsymbol"):
        s = re.sub(r"\\%s\s*\{([^{}]*)\}" % cmd, r"\1", s)
    s = (s.replace("\\pi", " pi ").replace("\\cdot", "*").replace("\\times", "*")
         .replace("\\div", "/").replace("\\infty", "oo"))
    s = re.sub(r"\\(sin|cos|tan|cot|sec|csc|log|ln|exp|sinh|cosh|tanh|arcsin|arccos|arctan)\b", r"\1", s)
    if "\\" not in s:
        s = s.replace("{", "(").replace("}", ")")
    return s


def _normalize_expr_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"^(?:最终答案|答案|结论)\s*[：:]\s*", "", s)
    s = s.strip().rstrip("。.，,；;")
    for src, dst in _UNICODE_REPLACEMENTS:
        s = s.replace(src, dst)
    s = re.sub(r"√\s*\(([^()]*)\)", r"(sqrt(\1))", s)
    s = re.sub(r"√\s*(\d+(?:\.\d+)?|[a-zA-Z])", r"(sqrt(\1))", s)
    if "\\" in s or "$" in s:
        s = _latex_to_text(s)
    s = s.replace("π", "(pi)")
    return s.strip()


def _const_product_to_expr(s: str) -> str:
    """紧凑常量乘积（πie、2π√2）→ 可解析文本 (pi)(I)(E)、2(pi)sqrt(2)。"""
    out = []
    for ch in s:
        if ch == "π":
            out.append("(pi)")
        elif ch in "iI":
            out.append("(I)")
        elif ch in "eE":
            out.append("(E)")
        elif ch == "^":
            out.append("**")
        else:
            out.append(ch)
    return "".join(out)


def _try_parse_expr(text: str):
    """尽力把答案文本解析成 sympy 表达式，失败返回 None。"""
    import sympy as sp
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
        implicit_multiplication_application, convert_xor)

    raw = (text or "").strip()
    if not raw or len(raw) > 400:
        return None

    candidates = []
    # normalize 优先：正确处理 √/π/LaTeX（含括号包裹）
    candidates.append(_normalize_expr_text(raw))
    # 紧凑常量乘积（πie）兜底（√ 已由 normalize 处理，此处不再翻译 √）
    if re.match(r"^[0-9πiIeE√+\-*/^(). ]{1,40}$", raw) and re.search(r"[πiIeE]", raw):
        candidates.append(_const_product_to_expr(raw))
    candidates.append(raw)

    transformations = standard_transformations + (implicit_multiplication_application, convert_xor)
    local_dict = {"pi": sp.pi, "e": sp.E, "E": sp.E, "i": sp.I, "I": sp.I, "oo": sp.oo}
    for cand in candidates:
        cand = (cand or "").strip()
        if not cand:
            continue
        # 优先 parse_expr：正确识别 sqrt/sin 等函数与隐式乘法。
        # sympify 会把 sqrt 误拆成 s*q*r*t 四个符号，仅作兜底。
        try:
            return parse_expr(cand, transformations=transformations, local_dict=local_dict)
        except Exception:
            pass
        try:
            return sp.sympify(cand)
        except Exception:
            continue
    return None


def _sample_equivalent(e1, e2, tolerance: float, max_symbols: int = 4):
    """自由符号表达式用固定代表点采样判等价。"""
    import sympy as sp

    symbols = sorted(e1.free_symbols | e2.free_symbols, key=str)
    if not symbols or e1.free_symbols != e2.free_symbols:
        return None
    if len(symbols) > max_symbols:
        return None

    base_points = [
        sp.Rational(37, 100), sp.Rational(153, 100), sp.Rational(271, 100),
        sp.Rational(-89, 100), sp.Rational(457, 100),
        sp.Rational(61, 100) + sp.Rational(43, 100) * sp.I,
    ]
    evaluated = 0
    for point in base_points:
        substitution = {sym: point + sp.Rational(i, 17) for i, sym in enumerate(symbols)}
        try:
            v1 = complex(sp.N(e1.subs(substitution), 30, chop=True))
            v2 = complex(sp.N(e2.subs(substitution), 30, chop=True))
        except Exception:
            continue
        if any(abs(v) == float("inf") or v != v for v in (v1.real, v1.imag, v2.real, v2.imag)):
            continue
        scale = max(1.0, abs(v1), abs(v2))
        if abs(v1 - v2) > max(tolerance, 1e-9) * scale:
            return False
        evaluated += 1
    return True if evaluated >= 3 else None


def sympy_equivalent(a1: str, a2: str, tolerance: float = 1e-6, simplify_timeout: int = 8):
    """True=等价 / False=确定不等价 / None=无法判定。"""
    import sympy as sp

    e1, e2 = _try_parse_expr(a1), _try_parse_expr(a2)
    if e1 is None or e2 is None:
        return None
    # 多值答案（如 "2026, 2030"）会被 parse_expr 解析成 tuple，跳过符号等价
    if not (hasattr(e1, "free_symbols") and hasattr(e2, "free_symbols")):
        return None

    # 矩阵
    is_m1, is_m2 = isinstance(e1, sp.MatrixBase), isinstance(e2, sp.MatrixBase)
    if is_m1 or is_m2:
        if is_m1 and is_m2:
            if e1.shape != e2.shape:
                return False
            try:
                return bool(sp.simplify(e1 - e2).is_zero_matrix)
            except Exception:
                return None
        mat, scalar = (e1, e2) if is_m1 else (e2, e1)
        if mat.shape == (1, 1):
            e1, e2 = mat[0, 0], scalar
        else:
            return False

    # simplify 差为零（限时）
    try:
        import signal
        diff = sp.simplify(e1 - e2)
        if diff == 0:
            return True
    except Exception:
        diff = None

    # 数值比较
    try:
        c1 = complex(sp.N(e1, 30, chop=True))
        c2 = complex(sp.N(e2, 30, chop=True))
        scale = max(1.0, abs(c1), abs(c2))
        return abs(c1 - c2) <= max(tolerance, 1e-9 * scale)
    except Exception:
        pass

    # 自由符号采样
    return _sample_equivalent(e1, e2, tolerance)


def _string_similarity(a: str, b: str) -> float:
    try:
        from Levenshtein import ratio
        return ratio(a, b)
    except Exception:
        if not a or not b:
            return 0.0
        return sum(1 for c in a if c in b) / max(len(a), len(b))


def is_placeholder_answer(answer: str) -> bool:
    t = (answer or "").strip().lower()
    if not t:
        return True
    return t in ("[result]", "[answer]", "答案", "略", "无", "none", "null", "占位")


def match_computation(a1: str, a2: str, tolerance: float = 1e-6):
    """两个计算题答案匹配，返回 (is_match, confidence, reason, method)。"""
    a1, a2 = (a1 or "").strip(), (a2 or "").strip()
    if is_placeholder_answer(a1) or is_placeholder_answer(a2):
        return False, 0.0, "占位符或空答案", "placeholder"

    # 逐字相同
    if a1 == a2:
        return True, 1.0, "字符串完全匹配", "exact"

    # 数值比较
    try:
        v1, v2 = float(a1), float(a2)
        diff = abs(v1 - v2)
        if diff < 1e-10:
            return True, 1.0, "数值完全匹配", "numeric"
        if diff < tolerance:
            return True, 0.95, f"数值近似匹配 误差{diff:.2e}", "numeric"
        return False, 0.8, f"数值差异过大 {diff:.2e}", "numeric"
    except Exception:
        pass

    # 结构化多字段比较（多问答案逐字段等价）
    applicable, s_verdict, s_cov, s_matched, s_mismatched = compare_structured(
        a1, a2, sympy_equivalent, tolerance)
    if applicable:
        if s_verdict is True:
            return True, 0.96, f"多字段等价（覆盖 {len(s_matched)}/{max(len(s_matched)+len(s_mismatched),1)}）", "structured_symbolic"
        if s_verdict is False:
            return False, 0.85, f"多字段存在不等价（{len(s_mismatched)} 个字段不匹配）", "structured_symbolic"

    # 符号等价
    eq = sympy_equivalent(a1, a2, tolerance)
    if eq is True:
        return True, 0.98, "符号等价", "symbolic"
    if eq is False:
        return False, 0.8, "符号不等价", "symbolic"

    # 字符串相似度兜底
    sim = _string_similarity(a1, a2)
    if sim > 0.9:
        return True, sim, f"高度相似({sim:.2f})", "text"
    if sim > 0.7:
        return False, sim, f"部分相似({sim:.2f})", "text"
    return False, sim, f"明显不同({sim:.2f})", "text"
