"""utils/skill_excerpt.py — 按题目主题选取 skill 文档相关片段。

深度 skill 文档很长（几百到上千行），直接 [:3000] 截断开头会丢掉
后面的章节（如运筹学的动态规划、博弈论模块永远选不到）。
本模块按「## 章节」切分，用题目关键词打分，选最相关的片段。
"""

from __future__ import annotations

import re


def _tokens(text: str) -> set:
    """提取题目关键词（中文 2-3 字片段 + 英文词 + 数字）。"""
    tokens = set(re.findall(r"[A-Za-z]{2,}|\d+", text.lower()))
    for run in re.findall(r"[一-鿿]+", text):
        for width in (2, 3):
            for i in range(max(0, len(run) - width + 1)):
                tokens.add(run[i:i + width])
    return tokens


def select_skill_excerpt(skill_doc: str, problem: str, max_chars: int = 3000) -> str:
    """按题目主题选 skill 相关片段，总计不超过 max_chars。"""
    if not skill_doc or len(skill_doc) <= max_chars:
        return skill_doc

    # 按 ## 章节切分（保留标题）
    sections = re.split(r"(?m)(?=^#{1,2}\s)", skill_doc)
    if len(sections) <= 1:
        return skill_doc[:max_chars]

    query = _tokens(problem)

    def score_section(sec: str) -> int:
        # 标题匹配权重更高
        first_line = sec.split("\n", 1)[0]
        title_score = sum(3 for t in query if t in first_line)
        body_score = sum(1 for t in query if t in sec)
        return title_score + body_score

    scored = sorted(((score_section(s), s) for s in sections), key=lambda x: -x[0])

    # 开头（领域概述）+ 高分章节，按顺序拼接
    result = []
    total = 0
    for score, sec in scored:
        if not sec.strip():
            continue
        if total + len(sec) > max_chars:
            remaining = max_chars - total
            if remaining > 200:
                result.append(sec[:remaining])
            break
        result.append(sec)
        total += len(sec)

    # 若选出的太少，回退到开头
    if total < max_chars * 0.3:
        return skill_doc[:max_chars]
    return "\n".join(result)
