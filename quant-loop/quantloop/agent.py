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

import json
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
        if skill.name.startswith("pm_estimate"):
            return self._pm_estimate(skill, context)
        if skill.name.startswith("pm_verification"):
            return self._pm_verify(skill, context)
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

    # ---- prediction-market maker: estimate P(YES), trade the gap ----------

    def _pm_estimate(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        symbol = context["symbol"]
        price = float(context["market_price"])
        signal = float(context.get("signal", price))  # public "research" estimate
        cap = _rule_position_cap(skill.rules, default=0.02)
        margin = 0.05

        # Blend the market price with the (more informative) research signal.
        fair = mathx.clamp01(0.35 * price + 0.65 * signal)
        edge = fair - price
        side = "yes" if edge > margin else "no" if edge < -margin else "flat"
        return {
            "symbol": symbol,
            "side": side,
            "prob_estimate": round(fair, 4),
            "market_price": round(price, 4),
            "edge": round(edge, 4),
            "size": cap,
            "skill": skill.name,
        }

    # ---- prediction-market checker: grade calibration on resolved markets --

    def _pm_verify(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        estimates = context["estimates"]      # maker's P(YES) on resolved markets
        outcomes = context["outcomes"]        # ground truth, 1/0
        prices = context["market_prices"]     # the market's own forecast
        thr = context["thresholds"]

        n = len(outcomes)
        maker_brier = mathx.brier_score(estimates, outcomes)
        market_brier = mathx.brier_score(prices, outcomes)
        checks = {
            "sample": n >= thr["min_samples"],
            "brier": maker_brier <= thr["max_brier"],
            "beats_market": (market_brier - maker_brier) >= thr["min_edge_vs_market"],
        }
        return {
            "verdict": "pass" if all(checks.values()) else "fail",
            "metrics": {"maker_brier": round(maker_brier, 4),
                        "market_brier": round(market_brier, 4), "samples": n},
            "checks": checks,
            "skill": skill.name,
        }


class ClaudeAgent:
    """A real Claude-backed worker — identical interface to LocalAgent.

    The division of labour is deliberate: the *model* makes the judgement call
    (which way to trade, whether a track record is real alpha) and the
    *deterministic backtest* computes the numbers. An LLM should not be asked to
    do arithmetic on a price series; it should reason about regime and risk. So:

      * maker  — Claude reads the alpha_research skill + a feature summary and
        returns a strategy decision (direction, trend-vs-revert, lookback). The
        code then backtests that exact rule to produce the out-of-sample track
        record it hands forward. The model never sees, and never grades, that
        record.
      * checker — Claude reads the backtest_verification skill + the metrics the
        code measured on the held-out window and returns a verdict. It is a
        *different* ClaudeAgent (different model, different system prompt) and
        only ever sees the out-of-sample numbers, never the maker's reasoning.

    Wire two of these into Pipeline (`maker=ClaudeAgent("claude-sonnet-4-6")`,
    `checker=ClaudeAgent("claude-opus-4-8")`) to run the loop on real models;
    everything downstream is unchanged. Requires `pip install anthropic` and
    ANTHROPIC_API_KEY (or pass api_key=).
    """

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None,
                 max_tokens: int = 2048):
        self.model = model
        self._api_key = api_key
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - exercised only without the dep
                raise RuntimeError(
                    "ClaudeAgent needs `pip install anthropic` and an API key. "
                    "Use LocalAgent for the offline reference run."
                ) from exc
            self._client = (anthropic.Anthropic(api_key=self._api_key)
                            if self._api_key else anthropic.Anthropic())
        return self._client

    def run_skill(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        if skill.name.startswith("alpha_research"):
            return self._alpha_research(skill, context)
        if skill.name.startswith("backtest_verification"):
            return self._verify(skill, context)
        if skill.name.startswith("pm_estimate"):
            return self._pm_estimate(skill, context)
        if skill.name.startswith("pm_verification"):
            return self._pm_verify(skill, context)
        raise ValueError(f"ClaudeAgent has no procedure for skill {skill.name!r}")

    # ---- maker: the model decides; the code backtests --------------------

    def _alpha_research(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        symbol = context["symbol"]
        train_prices = context["prices"]
        test_prices = context.get("test_prices", [])
        flags = context.get("flags", {})
        max_position = _rule_position_cap(skill.rules, default=0.02)

        blackout = _blackout_reason(skill.rules, flags)
        if blackout:
            return {"symbol": symbol, "side": "flat", "reason": blackout, "skill": skill.name}

        rets = mathx.returns(train_prices)
        if len(rets) < 6:
            return {"symbol": symbol, "side": "flat", "reason": "insufficient history"}

        features = {
            "symbol": symbol,
            "recent_returns": [round(r, 5) for r in rets[-10:]],
            "mean_return": round(mathx.mean(rets), 6),
            "volatility": round(mathx.stdev(rets), 6),
            "momentum_5": round(mathx.mean(rets[-5:]), 6),
            "autocorr_beta": round(mathx.ols_slope(rets[:-1], rets[1:]), 5),
            "max_position": max_position,
        }
        decision = self._json_call(
            system=skill.raw,
            user=("Decide how to trade this instrument for the next period. "
                  "Features (price returns):\n" + json.dumps(features, indent=2)),
            schema={
                "type": "object",
                "properties": {
                    "side": {"type": "string", "enum": ["long", "short", "flat"]},
                    "mode": {"type": "string", "enum": ["trend", "revert"]},
                    "lookback": {"type": "integer"},
                    "rationale": {"type": "string"},
                },
                "required": ["side", "mode", "lookback", "rationale"],
                "additionalProperties": False,
            },
        )

        if decision.get("side") == "flat":
            return {"symbol": symbol, "side": "flat",
                    "reason": decision.get("rationale", "model declined"), "skill": skill.name}

        # The model chose the rule; the code applies it to the held-out window.
        mode = decision["mode"]
        lookback = max(1, min(int(decision["lookback"]), 20))
        insample, oos = _backtest_parametric(rets, mathx.returns(test_prices), mode, lookback)
        return {
            "symbol": symbol,
            "side": decision["side"],
            "size": max_position,
            "mode": mode,
            "lookback": lookback,
            "rationale": decision.get("rationale", ""),
            "insample_sharpe": round(insample, 3),
            "oos_returns": [round(x, 6) for x in oos],
            "skill": skill.name,
        }

    # ---- checker: the code measures; the model judges --------------------

    def _verify(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        oos_rets = context["oos_returns"]
        thresholds = context["thresholds"]
        metrics = {
            "sharpe": round(mathx.sharpe(oos_rets), 4),
            "max_drawdown": round(mathx.max_drawdown(oos_rets), 4),
            "newey_west_t": round(mathx.newey_west_tstat(oos_rets), 4),
        }
        verdict = self._json_call(
            system=skill.raw,
            user=("Grade this signal strictly against the thresholds. "
                  "It must pass ALL of them.\n"
                  f"Measured out-of-sample metrics: {json.dumps(metrics)}\n"
                  f"Thresholds: {json.dumps(thresholds)}"),
            schema={
                "type": "object",
                "properties": {
                    "verdict": {"type": "string", "enum": ["pass", "fail"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["verdict", "reasoning"],
                "additionalProperties": False,
            },
        )
        # Ground the verdict with the code's own threshold checks for transparency.
        checks = {
            "sharpe": metrics["sharpe"] >= thresholds["min_sharpe"],
            "max_drawdown": metrics["max_drawdown"] <= thresholds["max_drawdown"],
            "newey_west_t": metrics["newey_west_t"] >= thresholds["min_tstat"],
        }
        return {
            "verdict": verdict["verdict"],
            "reasoning": verdict.get("reasoning", ""),
            "metrics": metrics,
            "checks": checks,
            "skill": skill.name,
        }

    # ---- prediction market: the model's real edge is reading the question --

    def _pm_estimate(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        price = float(context["market_price"])
        cap = _rule_position_cap(skill.rules, default=0.02)
        margin = 0.05
        est = self._json_call(
            system=skill.raw,
            user=("Estimate the probability this event resolves YES.\n"
                  f"Question: {context.get('question')}\n"
                  f"Market price (its implied probability): {price}\n"
                  f"Background research signal: {context.get('signal')}\n"
                  "Reason about the event, then give your probability."),
            schema={
                "type": "object",
                "properties": {
                    "probability": {"type": "number"},
                    "reasoning": {"type": "string"},
                },
                "required": ["probability", "reasoning"],
                "additionalProperties": False,
            },
        )
        fair = mathx.clamp01(float(est["probability"]))
        edge = fair - price
        side = "yes" if edge > margin else "no" if edge < -margin else "flat"
        return {
            "symbol": context["symbol"], "side": side,
            "prob_estimate": round(fair, 4), "market_price": round(price, 4),
            "edge": round(edge, 4), "size": cap,
            "rationale": est.get("reasoning", ""), "skill": skill.name,
        }

    def _pm_verify(self, skill: Skill, context: dict[str, Any]) -> dict[str, Any]:
        estimates, outcomes = context["estimates"], context["outcomes"]
        prices, thr = context["market_prices"], context["thresholds"]
        n = len(outcomes)
        maker_brier = mathx.brier_score(estimates, outcomes)
        market_brier = mathx.brier_score(prices, outcomes)
        verdict = self._json_call(
            system=skill.raw,
            user=("Decide whether to trust this maker's forecasts. It must clear "
                  "ALL thresholds.\n"
                  f"Maker Brier: {maker_brier:.4f}  Market Brier: {market_brier:.4f}  "
                  f"Resolved samples: {n}\n"
                  f"Thresholds: {json.dumps(thr)}"),
            schema={
                "type": "object",
                "properties": {
                    "verdict": {"type": "string", "enum": ["pass", "fail"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["verdict", "reasoning"],
                "additionalProperties": False,
            },
        )
        checks = {
            "sample": n >= thr["min_samples"],
            "brier": maker_brier <= thr["max_brier"],
            "beats_market": (market_brier - maker_brier) >= thr["min_edge_vs_market"],
        }
        return {
            "verdict": verdict["verdict"], "reasoning": verdict.get("reasoning", ""),
            "metrics": {"maker_brier": round(maker_brier, 4),
                        "market_brier": round(market_brier, 4), "samples": n},
            "checks": checks, "skill": skill.name,
        }

    # ---- the one place that talks to the API ----------------------------

    def _json_call(self, system: str, user: str, schema: dict) -> dict:
        """One structured-output Messages call; returns the parsed JSON object."""
        resp = self._get_client().messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if resp.stop_reason == "refusal":  # Fable/Opus safety classifier path
            raise RuntimeError(f"model refused: {getattr(resp, 'stop_details', None)}")
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        return json.loads(text)


def _backtest_parametric(train_rets: list[float], test_rets: list[float],
                         mode: str, lookback: int) -> tuple[float, list[float]]:
    """Backtest a simple trend/revert rule the maker chose. Pure, no model calls.

    Returns (in-sample Sharpe, out-of-sample realised returns). The rule bets in
    the direction of the recent mean (trend) or against it (revert).
    """
    def decide(history: list[float]) -> int:
        if len(history) < lookback:
            return 0
        recent = mathx.mean(history[-lookback:])
        signal = 1 if recent > 0 else -1
        return signal if mode == "trend" else -signal

    insample = [decide(train_rets[:i]) * train_rets[i] for i in range(1, len(train_rets))]
    oos: list[float] = []
    window = list(train_rets)
    for r in test_rets:
        oos.append(decide(window) * r)
        window.append(r)
    return mathx.sharpe(insample), oos


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
