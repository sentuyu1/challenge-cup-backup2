"""nodes/input_node.py — 初始化节点。"""

from __future__ import annotations


def input_node(state: dict, config) -> dict:
    return {"idx": state.get("idx", -1)}
