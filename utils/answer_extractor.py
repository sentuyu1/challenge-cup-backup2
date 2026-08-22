"""utils/answer_extractor.py — 答案提取。

判分正确性的核心：从 LLM 输出中精确提取最终答案。分层策略：
  1. 四章节解析（## 最终答案）
  2. boxed / 答案标记 / 结论捞回（散文兜底）
  3. 噪声/残片/占位符清洗
"""

from __future__ import annotations

import re
from typing import List, Optional

from utils.answer_cleanliness import (
    clean_answer, is_noise_answer, is_placeholder_answer,
    looks_incomplete_answer, looks_like_latex_fragment, strip_cot_prefix)


def extract_boxed(text: str) -> str:
    """提取 \\boxed{...} 内的答案，支持嵌套花括号。"""
    idx = text.find("\\boxed{")
    if idx < 0:
        return ""
    start = idx + len("\\boxed{")
    depth, pos = 1, start
    while pos < len(text) and depth > 0:
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
        pos += 1
    return text[start:pos - 1].strip() if depth == 0 else ""


def _reject_bad_answer(answer: str) -> str:
    """占位符、LaTeX 残片、不完整、噪声答案一律返回空串。"""
    return clean_answer(answer)


# 行是否携带答案信息：等式 / 数学式 / 数字 / 结论词
_PAYLOAD_LINE_RE = re.compile(
    r"[=$]|\d|拒绝|接受|显著|结论|因此|所以|故|建议|选择|综上|存在|唯一|收敛|成立")
_ENUM_ITEM_RE = re.compile(r"^\s*(?:\d+\s*[.、)]|[-*•①②③④⑤])")


def _strip_bullet(line: str) -> str:
    return line.lstrip("-*•①②③④⑤ ").strip()


def _form_key(part: str) -> str:
    """同一段答案的书写形态归一键（剥排版外壳，不动内容）。"""
    text = str(part or "")
    text = re.sub(r"\\boxed\s*\{([^{}]*)\}", r"\1", text)
    text = text.replace("$", "")
    text = re.sub(r"\\[\[\]]|\\displaystyle|\\left|\\right|\\,|\\;|\\!", "", text)
    return re.sub(r"\s+", "", text)


def _is_restatement(key: str, earlier: str) -> bool:
    """key 是否只是把 earlier 换个写法重说一遍（去变量=前缀后相同）。"""
    if not key or not earlier:
        return False
    if key == earlier:
        return True
    stripped = re.sub(r"^[A-Za-z]\w*(?:\([^()]*\))?=", "", earlier)
    return bool(stripped) and stripped != earlier and stripped == key


def _join_parts(parts: List[str]) -> str:
    """用全角分号连接各行，同一答案换个写法重说一遍时只保留第一次。"""
    cleaned = [p.rstrip("；; ").strip() for p in parts if p and p.strip("；; ")]
    kept, keys = [], []
    for part in cleaned:
        key = _form_key(part)
        if any(_is_restatement(key, e) for e in keys):
            continue
        kept.append(part)
        keys.append(key)
    return "；".join(kept)


def _rhs_of_top_level_eq(line: str) -> str:
    """行内最后一个"顶层" '=' 的右侧内容（LaTeX 感知，不切进公式内部）。"""
    depth, in_math, pos = 0, False, -1
    for i, ch in enumerate(line):
        if ch == "$":
            in_math = not in_math
        elif ch in "{([":
            depth += 1
        elif ch in "})]":
            depth = max(0, depth - 1)
        elif ch == "=" and depth == 0 and not in_math:
            pos = i
    return line[pos + 1:].strip() if pos >= 0 else ""


def _distill_answer(text: str) -> str:
    """从「## 最终答案」章节提炼简洁答案（分层策略）。"""
    text = strip_cot_prefix(text or "")
    if is_placeholder_answer(text):
        return ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 1. 枚举节（≥2 个编号项）→ 全部条目整体保留
    enum_items = [l for l in lines if _ENUM_ITEM_RE.match(l)]
    if len(enum_items) >= 2 and len(text) <= 1600:
        kept = [_strip_bullet(l) for l in lines
                if _ENUM_ITEM_RE.match(l) or _PAYLOAD_LINE_RE.search(l)]
        joined = _join_parts(kept)
        if joined and not looks_like_latex_fragment(joined):
            return joined

    # 2. 多行短节 → 保留所有信息行（等式行 + 结论行）
    eq_lines = [_strip_bullet(l) for l in lines if "=" in l]
    if 2 <= len(lines) <= 8 and len(text) <= 900 and eq_lines \
            and all(len(l) <= 200 for l in lines):
        kept = [_strip_bullet(l) for l in lines if _PAYLOAD_LINE_RE.search(l)]
        joined = _join_parts(kept)
        if kept and not looks_like_latex_fragment(joined):
            return joined
    if len(eq_lines) >= 3:
        conclusion_extra = [_strip_bullet(l) for l in lines
                            if "=" not in l and re.search(r"拒绝|接受|显著|结论|建议|选择|综上", l)]
        joined = _join_parts(eq_lines + conclusion_extra)
        if len(joined) <= 1600 and not looks_like_latex_fragment(joined):
            return joined

    # 3. boxed 结论（多个 boxed 用分号连接）
    boxes = re.findall(r"\\boxed\s*\{((?:[^{}]|\{[^{}]*\})*)\}", text)
    if boxes:
        answer = _reject_bad_answer(_join_parts([b.strip() for b in boxes]))
        if answer:
            return answer

    # 4. 短节 → 最后一行
    if len(text) <= 80:
        return _reject_bad_answer(lines[-1] if lines else text)

    # 5. 显式"答案是X"
    for pat in (r"答案[是为：:]\s*(.+?)(?:\n|$)", r"answer\s*[:is]+\s*(.+?)(?:\n|$)"):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            answer = _reject_bad_answer(m.group(1))
            if answer:
                return answer

    # 6. 行尾顶层 '=' 右值
    eq_line = next((l for l in reversed(lines) if "=" in l), "")
    if eq_line:
        answer = _reject_bad_answer(_rhs_of_top_level_eq(eq_line))
        if answer:
            return answer
        answer = _reject_bad_answer(_strip_bullet(eq_line))
        if answer:
            return answer

    # 7. 首个信息行，最后兜底整节
    for cand in ([l for l in lines if _PAYLOAD_LINE_RE.search(l)][:1]
                 + ([lines[0]] if lines else [])
                 + ([text] if len(text) <= 600 else [])):
        answer = _reject_bad_answer(cand)
        if answer:
            return answer
    return ""


def salvage_conclusion(text: str) -> str:
    """结论捞回：无章节标题时，从散文中捞回结论句（因此/所以/综上）。"""
    text = strip_cot_prefix(text or "")
    if not text:
        return ""
    # 优先 boxed
    boxed = extract_boxed(text)
    if boxed:
        return _reject_bad_answer(boxed)
    # 结论词后面的结论
    patterns = [
        r"(?:因此|所以|故|综上|综上所述|最终|答案)[，,：:]?\s*(.+?)(?:\n|$)",
        r"(?:hence|therefore|thus|finally|answer)[，,：:]?\s*(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            cand = m.group(1).strip()
            if cand and len(cand) < 300 and not is_noise_answer(cand):
                answer = _reject_bad_answer(cand)
                if answer:
                    return answer
    # 最后一行（含等号优先）
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in reversed(lines):
        if "=" in line or _PAYLOAD_LINE_RE.search(line):
            answer = _reject_bad_answer(_strip_bullet(line))
            if answer:
                return answer
    return ""


def parse_reasoning_output(response: str) -> dict:
    """解析四章节结构化的推理输出。"""
    response = strip_cot_prefix(response or "")
    result = {"analysis": "", "steps": [], "answer": "", "validation_points": []}

    m = re.search(r"##\s*问题分析\s*(.*?)(?=##|$)", response, re.DOTALL)
    if m:
        result["analysis"] = m.group(1).strip()

    m = re.search(r"##\s*详细解题步骤\s*(.*?)(?=##\s*最终答案|$)", response, re.DOTALL)
    if m:
        sec = m.group(1)
        for sm in re.finditer(
                r"(?:步骤|Step)\s*(\d+)\s*[：:]\s*(.*?)(?=(?:步骤|Step)\s*\d+\s*[：:]|$)",
                sec, re.DOTALL | re.IGNORECASE):
            result["steps"].append({
                "step_num": int(sm.group(1)),
                "description": sm.group(2).strip(),
            })

    # 【最终答案】标记（折叠桌式第一行强约束），优先于 ## 最终答案 章节
    m = re.search(r"【\s*最终答案\s*】\s*[:：]?\s*(.+?)(?=\n\s*\n|\n\s*【|\Z)", response, re.DOTALL)
    if m and m.group(1).strip():
        result["answer"] = _distill_answer(m.group(1))
    else:
        m = re.search(r"##\s*最终答案\s*(.*?)(?=##|$)", response, re.DOTALL)
        if m:
            result["answer"] = _distill_answer(m.group(1))

    m = re.search(r"##\s*关键验证点\s*(.*?)(?=##|$)", response, re.DOTALL)
    if m:
        result["validation_points"] = re.findall(r"-\s*(.+)", m.group(1))

    # 兜底：模型没写章节标题但推理出了结论
    if not result["answer"]:
        result["answer"] = salvage_conclusion(response)

    return result


def extract_final_answer(text: str) -> str:
    """综合提取最终答案（多层兜底）。"""
    text = strip_cot_prefix(text or "")
    ans = extract_boxed(text)
    if ans and not is_placeholder_answer(ans):
        return ans
    for pat in (r"(?:最终答案|答案为?|answer\s*[:：]?)\s*(.+?)(?:\n|$)",
                r"(?:所以|因此|故|综上)\s*(.+?)(?:\n|$)"):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            r = m.group(1).strip()
            if r and len(r) < 500 and not is_placeholder_answer(r):
                return r
    return salvage_conclusion(text)
