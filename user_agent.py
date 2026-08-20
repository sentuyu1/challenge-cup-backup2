"""user_agent.py — 竞赛入口（LangGraph 图架构）。

平台加载约定：
  from user_agent import ReasoningAgent
  agent = ReasoningAgent(client=platform_client)
  result = agent.solve(problem, metadata)   # {"final_response": str, "trace": list}
"""

from __future__ import annotations

from typing import Any, Dict

from langgraph_math_agent import MathAgentGraph
from state.math_agent_state import create_initial_state
from utils.logger import get_logger
from utils.skills_loader import SkillsLoader


class ReasoningAgent:
    """基于 LangGraph 图架构的数学智能体。"""

    def __init__(self, client, *args, **kwargs):
        self.client = client
        self.logger = get_logger("ReasoningAgent")
        self.skills_loader = SkillsLoader()
        self.graph = MathAgentGraph(client=client, skills_loader=self.skills_loader)
        self.logger.info("ReasoningAgent 初始化完成")

    def solve(self, problem: str, metadata: dict) -> dict:
        meta = metadata if isinstance(metadata, dict) else {}
        idx = meta.get("idx", -1)
        try:
            initial = create_initial_state(str(problem or ""), meta)
            final_state = self.graph.run(initial)
            return {
                "final_response": final_state.get("final_response", "无法生成答案"),
                "trace": self._build_trace(final_state),
            }
        except Exception as exc:  # noqa: BLE001 - 任何异常都要返回非空答案
            self.logger.error(f"解题 {idx} 出错: {exc}")
            return {
                "final_response": "解题过程中出现错误，无法给出完整答案。",
                "trace": [{"step": "error", "content": str(exc), "idx": idx}],
            }

    @staticmethod
    def _build_trace(state: dict) -> list:
        trace = []
        if state.get("category"):
            trace.append({
                "step": "classification",
                "category": state.get("category"),
                "question_mode": state.get("question_mode", "computation"),
                "difficulty": state.get("difficulty", "medium"),
                "confidence": state.get("category_confidence", 0.0),
            })
        rr = state.get("reasoning_result")
        if rr:
            trace.append({
                "step": "reasoning",
                "answer": rr.get("answer", ""),
                "steps_count": len(rr.get("steps", [])),
                "attempts": state.get("reasoning_attempts", 0),
            })
        po = state.get("python_output")
        if po:
            trace.append({
                "step": "python_verification",
                "success": po.get("success", False),
                "answer": po.get("answer", ""),
                "verification_status": po.get("verification_status", ""),
            })
        if state.get("validation_details"):
            trace.append({
                "step": "validation",
                "status": state.get("validation_status"),
                "reason": state["validation_details"].get("reason", ""),
            })
        if state.get("substitution_trace"):
            trace.append({
                "step": "substitution_check",
                "status": state.get("substitution_status", ""),
            })
        if state.get("playoff_trace"):
            trace.append({
                "step": "playoff",
                "status": state.get("playoff_status", ""),
            })
        if state.get("critic_trace"):
            trace.append({
                "step": "critic_audit",
                "status": state.get("critic_status", ""),
            })
        if state.get("semantic_arbiter_trace"):
            trace.append({
                "step": "semantic_arbitration",
                "status": state.get("semantic_arbiter_status", ""),
            })
        if state.get("final_response"):
            trace.append({
                "step": "coordination",
                "response_length": len(state["final_response"]),
            })
        if state.get("_time_budget"):
            trace.append({
                "step": "timing",
                "budget": state.get("_time_budget", {}),
            })
        return trace
