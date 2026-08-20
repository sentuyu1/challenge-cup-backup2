"""langgraph_math_agent.py — 主图构建。

图拓扑（对齐高分项目思想）：
  input → classifier → solving 子图 → 路由
    match     → substitute（中/难计算题代回核验）→ critic → coordinator
    mismatch   → playoff（确定性复算裁决）→ critic / reconciliation
    uncertain  → semantic_arbiter → coordinator
    reconciliation → solving（换方法重算，限轮次）或 semantic_arbiter
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from config import CONFIG
from state.math_agent_state import MathAgentState


def build_math_agent_graph():
    from graph.solving_subgraph import build_solving_subgraph
    from nodes import (
        classifier_node, coordinator_node, critic_node, input_node,
        playoff_node, reconciliation_node, semantic_arbiter_node, substitute_node,
    )

    g = StateGraph(MathAgentState)
    g.add_node("input", input_node)
    g.add_node("classifier", classifier_node)
    g.add_node("solving", build_solving_subgraph())
    g.add_node("substitute", substitute_node)
    g.add_node("playoff", playoff_node)
    g.add_node("critic", critic_node)
    g.add_node("reconciliation", reconciliation_node)
    g.add_node("semantic_arbiter", semantic_arbiter_node)
    g.add_node("coordinator", coordinator_node)

    g.add_edge(START, "input")
    g.add_edge("input", "classifier")
    g.add_edge("classifier", "solving")

    def route_after_solving(state, config):
        if state.get("should_terminate"):
            return "coordinator"
        status = state.get("validation_status", "")
        mode = state.get("question_mode", "computation")
        if status == "match":
            # 中/难计算题：匹配成功后再做一次代回核验（戳穿同源同错）
            if (CONFIG.get("enable_substitution_check", True)
                    and mode == "computation"
                    and state.get("difficulty", "medium") in ("medium", "hard")):
                return "substitute"
            return "critic"
        if status == "mismatch":
            if CONFIG.get("enable_playoff", True):
                return "playoff"
            return "reconciliation"
        return "semantic_arbiter"

    g.add_conditional_edges("solving", route_after_solving, {
        "substitute": "substitute", "critic": "critic", "playoff": "playoff",
        "reconciliation": "reconciliation", "semantic_arbiter": "semantic_arbiter",
        "coordinator": "coordinator",
    })

    # substitute / playoff / critic / reconciliation 都按 next_node 字段路由
    for node in ("substitute", "playoff", "critic", "reconciliation"):
        def make_route(n):
            def route(state, config):
                target = state.get("next_node", "coordinator")
                return target if target in ("coordinator", "reconciliation",
                                            "semantic_arbiter", "critic", "solving") \
                    else "coordinator"
            return route
        g.add_conditional_edges(node, make_route(node), {
            "coordinator": "coordinator", "reconciliation": "reconciliation",
            "semantic_arbiter": "semantic_arbiter", "critic": "critic",
            "solving": "solving",
        })

    g.add_conditional_edges("semantic_arbiter", lambda s, c: "coordinator", {
        "coordinator": "coordinator"})
    g.add_edge("coordinator", END)
    return g.compile()


class MathAgentGraph:
    def __init__(self, client, skills_loader=None, python_executor=None):
        self.app = build_math_agent_graph()
        self.client = client
        self.skills_loader = skills_loader
        self.python_executor = python_executor

    def run(self, initial_state, time_budget=None):
        from utils.deps import Deps
        from utils.logger import get_logger
        from utils.time_budget import TimeBudget

        clock = time_budget or TimeBudget()
        deps = Deps(
            client=self.client, skills_loader=self.skills_loader,
            python_executor=self.python_executor, time_budget=clock,
            logger=get_logger(),
        )
        final_state = self.app.invoke(
            initial_state, config={"configurable": {"deps": deps}})
        if isinstance(final_state, dict):
            final_state["_time_budget"] = clock.snapshot()
        return final_state
