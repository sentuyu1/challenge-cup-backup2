"""utils/answer_extractor.py — 答案提取。

从 LLM 输出中提取最终答案，处理四章节格式、\\boxed、LaTeX、多问项。
判分只认最终答案是否正确，提取质量直接决定得分。
"""

from __future__ import annotations

import re
from typing import List, Optional


def extract_boxed(text: str) -> str:
    """提取 \\boxed{...} 内的答案，支持嵌套花括号。"""
    idx = text.find("\\boxed{")
    if idx < 0:
        return ""
    start = idx + len("\\boxed{")
    depth = 1
    pos = start
    while pos < len(text) and depth > 0:
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
        pos += 1
    return text[start:pos - 1].strip() if depth == 0 else ""


def _is_placeholder(text: str) -> bool:
    """占位符/空答案检测。"""
    t = (text or "").strip().lower()
    if not t:
        return True
    for bad in ("[result]", "[answer]", "答案", "略", "无", "none", "null", "占位"):
        if t == bad:
            return True
    return False


def parse_reasoning_output(response: str) -> dict:
    """解析四章节结构化的推理输出。

    返回 {"analysis", "steps", "answer", "validation_points"}。
    """
    result = {"analysis": "", "steps": [], "answer": "", "validation_points": []}

    # 问题分析
    m = re.search(r"##\s*问题分析\s*(.*?)(?=##|$)", response, re.DOTALL)
    if m:
        result["analysis"] = m.group(1).strip()

    # 详细解题步骤
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

    # 最终答案
    m = re.search(r"##\s*最终答案\s*(.*?)(?=##|$)", response, re.DOTALL)
    if m:
        result["answer"] = _distill_answer(m.group(1).strip())

    # 关键验证点
    m = re.search(r"##\s*关键验证点\s*(.*?)(?=##|$)", response, re.DOTALL)
    if m:
        result["validation_points"] = re.findall(r"-\s*(.+)", m.group(1))

    # 兜底：模型没写章节标题但给出了答案
    if not result["answer"]:
        result["answer"] = extract_final_answer(response)

    return result


def _distill_answer(text: str) -> str:
    """从「## 最终答案」章节提炼简洁答案。"""
    text = (text or "").strip()
    if _is_placeholder(text):
        return ""

    # 1. 多个 boxed 结论（枚举/多问）
    boxes = re.findall(r"\\boxed\s*\{((?:[^{}]|\{[^{}]*\})*)\}", text)
    if boxes:
        joined = "；".join(b.strip() for b in boxes if b.strip())
        if joined and not _is_placeholder(joined):
            return joined

    # 2. 短节直接返回最后一行
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(text) <= 120 and lines:
        return lines[-1]

    # 3. 显式"答案"标记
    m = re.search(r"(?:答案|answer|result)\s*[是为：:]\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 4. 保留所有信息行（多问项）
    if len(lines) >= 2:
        info = [l for l in lines if re.search(r"[=$]|结论|拒绝|接受|显著|选择|综上|存在|唯一|收敛|成立|\d", l)]
        if info:
            joined = "；".join(info)
            if len(joined) <= 800:
                return joined

    return lines[-1] if lines else ""


def extract_final_answer(text: str) -> str:
    """综合提取最终答案（多层兜底）。"""
    # 1. boxed
    ans = extract_boxed(text)
    if ans and not _is_placeholder(ans):
        return ans

    # 2. 中文/英文答案标记
    for pat in (
            r"(?:最终答案|答案为?|answer\s*[:：]?)\s*(.+?)(?:\n|$)",
            r"(?:所以|因此|故|综上)\s*(.+?)(?:\n|$)"):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            r = m.group(1).strip()
            if r and len(r) < 500 and not _is_placeholder(r):
                return r

    # 3. 最后非空行
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines[-1][:500] if lines else ""
