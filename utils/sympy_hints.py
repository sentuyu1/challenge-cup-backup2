"""utils/sympy_hints.py — sympy 本地确定性计算（借鉴折叠桌 hints_for 思想）。

对题目中「可机器解析的初等子问题」（算术/同余/模幂/方程/导数/积分/极限/矩阵）
用 sympy 直接算，作为「证据」注入 prompt。零 LLM 成本、快、准确。
解析不了的题留给模型推理。
"""

from __future__ import annotations

import re
from math import gcd
from typing import List, Optional


def _parse_expr(sympy, expression: str):
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application, parse_expr, standard_transformations)
    if not re.fullmatch(r"[0-9A-Za-z_+\-*/^().,\s]+", expression):
        raise ValueError("unsupported")
    return parse_expr(
        expression,
        transformations=standard_transformations + (implicit_multiplication_application,),
    )


def _latex_to_sympy(expression: str) -> str:
    value = expression.strip().replace("$", "").replace("\\left", "").replace("\\right", "")
    value = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", value)
    value = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", value)
    value = re.sub(r"\\(sin|cos|tan|log|ln|exp)", r"\1", value)
    value = (value.replace(r"\pi", "pi").replace(r"\infty", "oo").replace("^", "**"))
    value = value.replace("{", "(").replace("}", ")")
    return value


def hints_for(problem: str) -> List[str]:
    """返回题目的 sympy 确定性计算提示。"""
    import sympy
    hints: List[str] = []

    # 同余方程 ax ≡ b (mod m)
    cong = re.search(r"(-?\d+)\s*\*?\s*x\s*≡\s*(-?\d+)\s*\(?\s*mod\s*(\d+)", problem)
    if cong:
        coef, const, mod = map(int, cong.groups())
        d = gcd(coef, mod)
        if const % d == 0 and d == 1:
            sol = (pow(coef % mod, -1, mod) * const) % mod
            hints.append(f"SymPy 同余解: x={sol} (mod {mod})")

    # 模幂 a^b mod m
    mp = re.search(r"(-?\d+)\s*\^\s*(\d+)\s*mod\s*(\d+)", problem)
    if mp:
        base, exp, mod = map(int, mp.groups())
        if mod:
            hints.append(f"SymPy 模幂: {pow(base, exp, mod)}")

    # 算术计算
    arith = re.search(r"(?:计算|求值|calculate|evaluate)\s*([0-9+\-*/^().,\s]+?)[。？?]?$", problem)
    if arith and not re.search(r"积分|导数|极限|方程", problem):
        try:
            r = _parse_expr(sympy, arith.group(1))
            hints.append(f"SymPy 计算: {r}")
        except Exception:
            pass

    # 方程求解
    if re.search(r"方程|求解|equation|solve|roots?", problem, re.IGNORECASE):
        eqs = re.findall(r"([0-9xyzXYZ][0-9A-Za-z_+\-*/^().,\s]{0,120}=[0-9A-Za-z_+\-*/^().,\s]{1,120})", problem)
        for eq in eqs:
            if "=" not in eq:
                continue
            left, right = eq.split("=", 1)
            var = re.search(r"\b([xyz])\b", left + right)
            if var:
                try:
                    expr = f"({_latex_to_sympy(left)})-({_latex_to_sympy(right)})"
                    sols = sympy.solve(_parse_expr(sympy, expr), sympy.Symbol(var.group(1)))
                    if sols:
                        hints.append(f"SymPy 方程解: {var.group(1)}={sols}")
                    break
                except Exception:
                    continue

    # 导数
    dm = re.search(r"(?:f\(x\)|y)\s*=\s*([^，。；;]+?)\s*(?:的)?(?:导数|求导)", problem)
    if dm:
        try:
            r = sympy.diff(_parse_expr(sympy, _latex_to_sympy(dm.group(1))), sympy.Symbol("x"))
            hints.append(f"SymPy 导数: {r}")
        except Exception:
            pass

    # 定积分
    di = re.search(r"\\int_\{?([^}^\s]+)\}?\^\{?([^}^\s]+)\}?\s*(.+?)\s*d([A-Za-z])", problem)
    if di:
        try:
            r = sympy.integrate(
                _parse_expr(sympy, _latex_to_sympy(di.group(3))),
                (sympy.Symbol(di.group(4)), _parse_expr(sympy, _latex_to_sympy(di.group(1))),
                 _parse_expr(sympy, _latex_to_sympy(di.group(2)))),
            )
            hints.append(f"SymPy 定积分: {r}")
        except Exception:
            pass

    return hints
