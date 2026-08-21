"""test_diagnose.py — 诊断答案格式优化是否误杀正确答案。"""

import sys

sys.path.insert(0, ".")

from utils.answer_cleanliness import (
    clean_answer, is_noise_answer, looks_like_latex_fragment, strip_cot_prefix)
from utils.answer_extractor import _distill_answer, extract_final_answer, salvage_conclusion


def check(name, got, expect_ok):
    """expect_ok=True 表示期望得到非空答案；False 表示期望被拒（空）。"""
    ok = bool(got) == expect_ok
    tag = "✅" if ok else "❌"
    print(f"{tag} {name}: {got!r} （期望{'非空' if expect_ok else '空'}）")
    return ok


def main():
    passed = 0
    total = 0

    # ── 正确答案不应该被误杀 ──
    cases = [
        ("boxed 数字", "\\boxed{15}", True),
        ("boxed 公式", "\\boxed{2^{n+1}-1}", True),
        ("LaTeX 分数", "\\frac{2}{5}", True),
        ("LaTeX 表达式", "$a_n = 2^{n+1} - 1$", True),
        ("多问答案", "f_Z(z)=1/2; P(Z>1)=1/4", True),
        ("区间", "[3.2, 5.8]", True),
        ("判断-是", "正确", True),
        ("判断-否", "错误", True),
        ("枚举", "共有 4 种：x=1、x=2、x=3、x=4", True),
        ("负分数", "-3/4", True),
        ("根式", "\\sqrt{2}", True),
        ("含单位", "5 个", True),
        ("矩阵", "[[1,0],[0,1]]", True),
    ]
    for name, text, expect in cases:
        total += 1
        if check(f"clean({name})", clean_answer(text), expect):
            passed += 1

    # ── 含 CoT 的响应，剥离后应保留答案 ──
    total += 1
    r = strip_cot_prefix("Thinking Process: 先分析...\n## 最终答案\n2*pi")
    if check("CoT剥离后", r, True) and "2*pi" in r:
        passed += 1

    # ── 结论捞回 ──
    total += 1
    if check("结论捞回", salvage_conclusion("经过推导，因此 x = 42。"), True):
        passed += 1

    # ── _distill_answer 不应误杀 ──
    total += 1
    if check("distill多行", _distill_answer("K = 2278125\n答案：2278125"), True):
        passed += 1

    print(f"\n诊断结果：{passed}/{total} 通过")
    if passed < total:
        print("⚠️ 发现误杀，答案格式优化有 bug")


if __name__ == "__main__":
    main()
