"""graph/solving_subgraph.py — solving 子图（双路并行）。

用 LangGraph Send 从 START 扇出两条独立求解路径：
  - reasoning_agent：LLM 推理
  - python_agent：SymPy 计算
两路都汇入 cross_validator 做交叉验证。客观题（选择/判断/填空）
只扇出推理路，不启动昂贵的 Python 分支。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from nodes.reasoning_agent_node import is_objective_mode


def build_solving_subgraph():
    from nodes import cross_validator_node, python_agent_node, reasoning_agent_node
    from state.math_agent_state import MathAgentState

    sub = StateGraph(MathAgentState)
    sub.add_node("reasoning_agent", reasoning_agent_node)
    sub.add_node("python_agent", python_agent_node)
    sub.add_node("cross_validator", cross_validator_node)

    def fan_out(state, config):
        reasoning_send = Send(
            "reasoning_agent",
            {**state, "branch_hint": state.get("reasoning_retry_hint")},
        )
        if is_objective_mode(state.get("question_mode", "computation")):
            return [reasoning_send]
        return [
            reasoning_send,
            Send("python_agent", {**state, "branch_hint": state.get("python_retry_hint")}),
        ]

    sub.add_conditional_edges(START, fan_out, ["reasoning_agent", "python_agent"])
    sub.add_edge("reasoning_agent", "cross_validator")
    sub.add_edge("python_agent", "cross_validator")
    sub.add_edge("cross_validator", END)
    return sub.compile()
