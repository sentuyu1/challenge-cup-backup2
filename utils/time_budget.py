"""utils/time_budget.py — 单题墙钟预算。

竞赛的硬约束是时间（单题 20 分钟 + 全卷 6h），不是 token。每个 LLM 调用
前都必须先问预算「买不买得起」，可选阶段在软预算耗尽后降级为确定性兜底，
保证超时前一定输出答案而非被强杀。

三个 horizon：
  * total  — 平台硬限（1200s），永不下调
  * soft   — 可选工作的购买力上限（total - reserve，可被难度画像进一步收紧）
  * reserve— 硬限前预留，保证答案落盘
"""

from __future__ import annotations

import time
from threading import Lock

from config import CONFIG


class TimeBudget:
    """每道题一个预算对象，图内所有节点共享同一时钟。"""

    def __init__(
        self,
        total_seconds: float | None = None,
        reserve_seconds: float | None = None,
        fast_path_threshold: float | None = None,
        clock=time.monotonic,
    ) -> None:
        self.total = float(total_seconds if total_seconds is not None else CONFIG["problem_time_budget_s"])
        self.reserve = float(reserve_seconds if reserve_seconds is not None else CONFIG["time_reserve_s"])
        self.fast_path_threshold = float(
            fast_path_threshold if fast_path_threshold is not None else CONFIG["time_fast_path_threshold_s"]
        )
        self._clock = clock
        self._start = clock()
        self._lock = Lock()
        self._spend_log: list = []
        # 难度感知软预算：soft_total 是可选工作购买力，可被分类节点收紧。
        self.soft_total = self.total
        self.difficulty_profile = "default"
        # PaperPacer 全卷预算帽：由题间预算池给出，None 表示未启用。
        self.paper_cap: float | None = None
        # 单题 LLM 请求硬上限
        self._llm_calls = 0

    # ── 难度画像 ──
    def apply_difficulty_profile(self, difficulty: str) -> float:
        """按难度收紧软预算（只收紧不放宽）。"""
        profile = (difficulty or "").strip().lower()
        budgets = CONFIG.get("difficulty_soft_budgets") or {}
        target = budgets.get(profile)
        if isinstance(target, (int, float)) and target > 0:
            with self._lock:
                if float(target) < self.soft_total:
                    self.soft_total = float(target)
                    self.difficulty_profile = profile
        return self.soft_total

    def apply_paper_cap(self, cap_seconds: float | None) -> None:
        """PaperPacer 全卷预算帽：与难度软预算取 min。"""
        if isinstance(cap_seconds, (int, float)) and cap_seconds > 0:
            with self._lock:
                self.paper_cap = float(cap_seconds)
                if self.paper_cap < self.soft_total:
                    self.soft_total = self.paper_cap

    # ── 时钟读数 ──
    def now(self) -> float:
        return self._clock()

    def elapsed(self) -> float:
        return self._clock() - self._start

    def remaining(self) -> float:
        """可选工作剩余时间（可为负）。"""
        return self.soft_total - self.reserve - self.elapsed()

    def remaining_hard(self) -> float:
        """平台硬限剩余时间。"""
        return self.total - self.elapsed()

    def expired(self) -> bool:
        return self.remaining() <= 0

    def can_afford(self, seconds: float) -> bool:
        return self.remaining() >= float(seconds)

    def fast_path(self) -> bool:
        """剩余时间不足以再来一次完整 LLM 往返时返回 True。"""
        return self.remaining() < self.fast_path_threshold

    def timeout_for(self, ceiling: float | None) -> float | None:
        """把节点超时上限收紧到硬限允许的范围。"""
        allowed = max(1.0, self.remaining_hard())
        if ceiling is None:
            return allowed
        return min(float(ceiling), allowed)

    # ── 观测 ──
    def record(self, label: str, seconds: float) -> None:
        with self._lock:
            self._spend_log.append({"label": label, "seconds": round(float(seconds), 2)})

    def spend_log(self) -> list:
        with self._lock:
            return list(self._spend_log)

    # ── LLM 请求硬上限 ──
    def bump_llm_call(self) -> None:
        with self._lock:
            self._llm_calls += 1

    def llm_calls_exhausted(self) -> bool:
        cap = int(CONFIG.get("max_llm_calls_per_problem", 0) or 0)
        if cap <= 0:
            return False
        with self._lock:
            return self._llm_calls >= cap

    def llm_call_count(self) -> int:
        with self._lock:
            return self._llm_calls

    def snapshot(self) -> dict:
        return {
            "elapsed_s": round(self.elapsed(), 2),
            "remaining_s": round(self.remaining(), 2),
            "total_s": self.total,
            "soft_total_s": self.soft_total,
            "difficulty_profile": self.difficulty_profile,
            "reserve_s": self.reserve,
            "fast_path": self.fast_path(),
        }
