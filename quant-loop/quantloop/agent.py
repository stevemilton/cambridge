"""The worker behind the loop.

Stages don't call an LLM directly; they call an `Agent` and hand it a Skill plus
context. That keeps the maker/checker boundary clean and lets you swap the model
per role (a stronger model for the checker, a cheaper one for the maker — the
same logic ensemble methods use to catch different kinds of error).

`LocalAgent` is a deterministic stand-in that actually computes signals and
backtests, so the whole loop runs offline with no API key. `ClaudeAgent` shows
where a real model plugs in behind the identical interface.
"""

from __future__ import annotations

from typing import Any, Protocol

from . import mathx
from .skills import Skill


class Agent(Protocol):
    def run_skill(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        ...


class LocalAgent:
    """Deterministic worker: real (if simple) quant logic, no network needed.

    It honours the structured rules it can parse out of the skill — e.g. position
    caps and "skip on FOMC / near earnings" blackout flags — so the SKILL.md is
    not decoration: editing the rules changes what this agent does.
    """

    def __init__(self, name: str = "local"):
        self.name = name

    def run_skill(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        if skill.name.startswith("alpha_research"):
            return self._alpha_research(skill, context)
        if skill.name.startswith("backtest_verification"):
            return self._verify(skill, context)
        raise ValueError(f"LocalAgent has no procedure for skill {skill.name!r}")

    # ---- maker: generate a signal -----------------------------------------

    def _alpha_research(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        symbol = context["symbol"]
        train_prices = context["prices"]          # in-sample only
        test_prices = context.get("test_prices", [])  # held out from fitting
        flags = context.get("flags", {})
        max_position = _rule_position_cap(skill.rules, default=0.02)

        # Honour blackout rules read from the skill *before* doing any work.
        blackout = _blackout_reason(skill.rules, flags)
        if blackout:
            return {"symbol": symbol, "side": "flat", "reason": blackout, "skill": skill.name}

        # Fit a regression of next-period return on this-period return using ONLY
        # the training window — the article's "linear regression on price/volume".
        rets = mathx.returns(train_prices)
        if len(rets) < 6:
            return {"symbol": symbol, "side": "flat", "reason": "insufficient history"}
        beta = mathx.ols_slope(rets[:-1], rets[1:])

        def rule(history: list[float]) -> int:
            # Direction = sign of (mean-reversion/momentum blend) from fitted beta.
            if len(history) < 5:
                return 0
            score = beta * history[-1] + mathx.mean(history[-5:])
            return 1 if score > 0 else -1

        side = {1: "long", -1: "short", 0: "flat"}[rule(rets)]

        # Produce the out-of-sample track record by walking the held-out window.
        # The maker GENERATES this record; it does not get to judge it — that is
        # the checker's job. (Returns the realised P&L of following the rule.)
        oos = mathx.returns(test_prices) if test_prices else []
        oos_returns: list[float] = []
        window = list(rets)
        for r in oos:
            direction = rule(window)
            oos_returns.append(direction * r)
            window.append(r)

        return {
            "symbol": symbol,
            "side": side,
            "beta": round(beta, 6),
            "size": max_position,
            "insample_sharpe": round(mathx.sharpe([rule(rets[:i + 1]) * rets[i]
                                                   for i in range(1, len(rets))]), 3),
            "oos_returns": [round(x, 6) for x in oos_returns],
            "skill": skill.name,
        }

    # ---- checker: independently verify a signal ---------------------------

    def _verify(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        oos_rets = context["oos_returns"]   # out-of-sample, never seen by the maker
        thresholds = context["thresholds"]

        sharpe = mathx.sharpe(oos_rets)
        mdd = mathx.max_drawdown(oos_rets)
        tstat = mathx.newey_west_tstat(oos_rets)

        checks = {
            "sharpe": (sharpe, sharpe >= thresholds["min_sharpe"]),
            "max_drawdown": (mdd, mdd <= thresholds["max_drawdown"]),
            "newey_west_t": (tstat, tstat >= thresholds["min_tstat"]),
        }
        passed = all(ok for _, ok in checks.values())
        return {
            "verdict": "pass" if passed else "fail",
            "metrics": {k: round(v, 4) for k, (v, _) in checks.items()},
            "checks": {k: ok for k, (_, ok) in checks.items()},
            "skill": skill.name,
        }


class ClaudeAgent:
    """Where a real model plugs in — identical interface to LocalAgent.

    Left as a thin, dependency-guarded adapter so the reference still runs with
    no `anthropic` package or API key installed. In production the maker and the
    checker would each be a ClaudeAgent with a different model and system prompt.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        self.model = model
        self._api_key = api_key

    def run_skill(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "ClaudeAgent needs the `anthropic` package and an API key. "
                "Use LocalAgent for the offline reference run."
            ) from exc
        raise NotImplementedError(
            "Wire your prompt here: send `skill.raw` as the system prompt and "
            "`context` as the user message, then parse the model's JSON reply."
        )


def _rule_position_cap(rules: list[str], default: float) -> float:
    for rule in rules:
        m = __import__("re").search(r"(\d+(?:\.\d+)?)\s*percent", rule.lower())
        if m and "position" in rule.lower():
            return float(m.group(1)) / 100.0
    return default


def _blackout_reason(rules: list[str], flags: dict[str, Any]) -> str | None:
    text = " ".join(rules).lower()
    if flags.get("fomc") and "fomc" in text:
        return "blackout: FOMC announcement day (per skill rules)"
    if flags.get("near_earnings") and "earnings" in text:
        return "blackout: within earnings window (per skill rules)"
    return None
