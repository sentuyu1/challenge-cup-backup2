"""nodes/reconciliation_node.py — 调解重试。

mismatch / 代回证伪后，决定是否重跑 solving 子图。控制重试轮数，
达到上限转语义仲裁。
"""

from __future__ import annotations

from config import CONFIG
from utils.deps import get_deps


def reconciliation_node(state: dict, config) -> dict:
    deps = get_deps(config)
    round_num = state.get("reconciliation_round", 0)
    trace = list(state.get("reconciliation_trace") or [])

    max_rounds = CONFIG["reconciliation_max_rounds"]

    # 已超轮数 → 仲裁兜底
    if round_num >= max_rounds:
        trace.append({"round": round_num, "decision": "exhausted→arbiter"})
        return {"reconciliation_round": round_num,
                "reconciliation_trace": trace,
                "next_node": "semantic_arbiter"}

    # 预算不足以再跑一次完整 solving → 仲裁兜底
    clock = deps.time_budget
    if clock and clock.fast_path():
        trace.append({"round": round_num, "decision": "budget_exhausted→arbiter"})
        return {"reconciliation_round": round_num,
                "reconciliation_trace": trace,
                "next_node": "semantic_arbiter"}

    # 生成换方法重试提示
    hint = state.get("reasoning_retry_hint") or (
        "上一次求解结果不一致或未通过验证。请更换解题方法重新独立推导，"
        "不要重复上一轮的错误思路。")
    trace.append({"round": round_num, "decision": "retry_solving"})
    return {
        "reconciliation_round": round_num + 1,
        "reconciliation_trace": trace,
        "reasoning_retry_hint": hint,
        "python_retry_hint": hint + "\n请用代码独立验证新结论。",
        "next_node": "solving",
    }
