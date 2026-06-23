"""Piece #4 — The verifier (the maker/checker split).

The worker that wrote the signal is the worst possible judge of whether it is
real alpha or noise. So a *separate* agent — different instructions, ideally a
different (stronger) model — grades it against thresholds it cannot argue with.
The checker never sees how the maker reasoned; that separation is the edge.

Every prop shop is structured this way: at Jane Street the trader who proposes a
trade does not approve it; at Citadel the researcher who builds the model does
not validate it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent import Agent
from .skills import Skill


# Default acceptance thresholds — the article's verification rules, made checkable.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "min_sharpe": 1.5,        # Sharpe ratio above 1.5
    "max_drawdown": 0.10,     # Max drawdown below 10 percent
    "min_tstat": 2.0,         # Newey-West t-stat above 2.0
}


@dataclass
class Verdict:
    passed: bool
    metrics: dict[str, float]
    checks: dict[str, bool]
    detail: dict[str, Any]

    def __bool__(self) -> bool:
        return self.passed


class Verifier:
    """Runs the checker agent against *out-of-sample* data the maker never saw."""

    def __init__(self, checker: Agent, skill: Skill,
                 thresholds: dict[str, float] | None = None):
        self.checker = checker
        self.skill = skill
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def verify(self, signal: dict, oos_returns: list[float]) -> Verdict:
        if signal.get("side") not in ("long", "short"):
            return Verdict(False, {}, {}, {"reason": signal.get("reason", "no actionable side")})
        result = self.checker.run_skill(
            self.skill,
            {"signal": signal, "oos_returns": oos_returns, "thresholds": self.thresholds},
        )
        return Verdict(
            passed=result["verdict"] == "pass",
            metrics=result.get("metrics", {}),
            checks=result.get("checks", {}),
            detail=result,
        )
