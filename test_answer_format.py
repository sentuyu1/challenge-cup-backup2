"""test_answer_format.py — 答案格式功能测试（raw string 避免转义）。"""

import sys

sys.path.insert(0, ".")

from utils.answer_cleanliness import (
    clean_answer, is_noise_answer, looks_like_latex_fragment, strip_cot_prefix)
from utils.answer_extractor import _distill_answer, salvage_conclusion
from utils.answer_matcher import match_computation


def main():
    # 1. CoT 剥离
    assert "2*pi" in strip_cot_prefix("Thinking Process: 先分析\n## 最终答案\n2*pi")
    assert "答案：5" in strip_cot_prefix("<think>...</think>答案：5")
    print("✅ CoT 剥离")

    # 2. 结论捞回
    assert "42" in salvage_conclusion("经过推导，因此 x = 42 是唯一解。")
    print("✅ 结论捞回")

    # 3. 答案清洗
    assert is_noise_answer("答案如下所示")
    assert is_noise_answer("答案如下：")
    assert not is_noise_answer("2*pi")
    assert looks_like_latex_fragment(r"\frac{\pi(")
    assert clean_answer("答案是：") == ""
    print("✅ 答案清洗")

    # 4. 结构化字段匹配（字段顺序不同）
    is_match, conf, reason, method = match_computation(
        "f_Z(z)=1/2; P(Z>1)=1/4", "P(Z>1)=0.25; f_Z(z)=0.5")
    assert is_match, f"字段顺序不同应匹配，实际 {reason}"
    print("✅ 结构化字段匹配")

    # 5. 改写去重（K=2278125 后又 boxed 2278125）
    d = _distill_answer("$$K=2278125$$\n\\boxed{2278125}")
    print(f"   改写去重结果: {d!r}")
    # 结果应该只含一个 2278125
    assert d.count("2278125") == 1, f"应去重，实际 {d!r}"
    print("✅ 改写去重")

    print("\n全部答案格式测试通过")


if __name__ == "__main__":
    main()
