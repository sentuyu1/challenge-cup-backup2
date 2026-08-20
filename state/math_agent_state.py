"""state/math_agent_state.py — 全图共享状态。

LangGraph 图内所有节点读写同一份 TypedDict 状态。并发写入的字段（如
双路并行产生的 node_timings）用 Annotated + operator.add 做 reducer 合并。
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, NotRequired, TypedDict


class MathAgentState(TypedDict):
    # ── 输入 ──
    problem: str
    metadata: Dict[str, Any]
    idx: int
    errors: Annotated[List[Dict], operator.add]

    # ── 分类 ──
    question_mode: NotRequired[str]      # computation/proof/choice/true_false/fill
    category: NotRequired[str]           # 18 领域之一
    difficulty: NotRequired[str]         # easy/medium/hard
    category_confidence: NotRequired[float]

    # ── 推理路 ──
    reasoning_result: NotRequired[Dict[str, Any]]   # analysis/steps/answer/validation_points
    reasoning_raw_response: NotRequired[str]
    reasoning_trace: NotRequired[List[Dict]]
    reasoning_attempts: NotRequired[int]
    reasoning_retry_hint: NotRequired[str]

    # ── Python 路 ──
    python_code: NotRequired[str]
    python_output: NotRequired[Dict[str, Any]]      # success/stdout/stderr/answer
    python_trace: NotRequired[List[Dict]]
    python_attempts: NotRequired[int]
    python_retry_hint: NotRequired[str]

    # ── 验证 ──
    validation_status: NotRequired[str]             # match/mismatch/uncertain 等
    validation_details: NotRequired[Dict[str, Any]]
    validated_answer: NotRequired[str]
    validation_history: NotRequired[Annotated[List[Dict], operator.add]]

    # ── 调解 ──
    reconciliation_round: NotRequired[int]
    reconciliation_trace: NotRequired[List[Dict]]

    # ── 裁决 ──
    critic_status: NotRequired[str]
    critic_trace: NotRequired[List[Dict]]
    critic_rounds: NotRequired[int]
    playoff_status: NotRequired[str]
    playoff_trace: NotRequired[List[Dict]]
    substitution_status: NotRequired[str]
    substitution_trace: NotRequired[List[Dict]]
    semantic_arbiter_status: NotRequired[str]
    semantic_arbiter_trace: NotRequired[List[Dict]]

    # ── 输出 ──
    final_response: NotRequired[str]
    answer_locked: NotRequired[bool]

    # ── 控制 ──
    branch_hint: NotRequired[str]       # 子图扇出携带的重试提示
    next_node: NotRequired[str]
    should_terminate: NotRequired[bool]

    # ── 观测（并发写入，reducer 合并）──
    node_timings: NotRequired[Annotated[List[Dict], operator.add]]


def create_initial_state(problem: str, metadata: Dict[str, Any]) -> MathAgentState:
    """构造 solve() 的初始状态。"""
    meta = metadata if isinstance(metadata, dict) else {}
    return MathAgentState(
        problem=str(problem or ""),
        metadata=meta,
        idx=int(meta.get("idx", -1)),
        errors=[],
        reasoning_attempts=0,
        python_attempts=0,
        reconciliation_round=0,
        critic_rounds=0,
        answer_locked=False,
        validation_history=[],
    )
