"""utils/deps.py — LangGraph configurable 依赖注入容器。

图内节点通过 get_deps(config) 取共享依赖（client、skill 加载器、时间预算、
Python 执行器等），保持节点函数纯函数形态，方便测试与复用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Deps:
    client: Any = None
    skills_loader: Any = None
    python_executor: Any = None
    time_budget: Any = None
    logger: Any = None


def get_deps(config: dict) -> Deps:
    """从 LangGraph configurable 中取依赖容器。"""
    if not isinstance(config, dict):
        return Deps()
    deps = config.get("configurable", {}).get("deps")
    return deps if isinstance(deps, Deps) else Deps()
