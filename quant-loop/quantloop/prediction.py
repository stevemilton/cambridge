"""The prediction-market loop — the same six pieces, five stages, new substrate.

What changes vs the price loop, and why it fits better:

  * signal (maker): estimate P(YES) and trade only the gap to the market price.
    The maker reading the *question* is the edge — exactly the ClaudeAgent's
    strength, where a price-momentum model has nothing to offer.
  * verify (checker): grade the maker on *resolved* markets with a Brier score —
    real ground truth, not a noisy price Sharpe. Pass only if the maker is
    calibrated AND beats the market's own forecast.
  * execute / risk: buy YES/NO contracts; settle them on resolution; on a
    drawdown breach, flatten and write the lesson back to the skill.

Everything else (LoopEngine, State, skills, the daemon) is reused unchanged.
Swap SimPredictionMarketConnector for a BetfairConnector to go live — see
BETFAIR.md.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable

from .agent import Agent, ClaudeAgent, LocalAgent
from .connectors.prediction_market import PredictionBroker, SimPredictionMarketConnector
from .loop import LoopEngine
from .skills import Skill, load_skill
from .state import State

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

# Acceptance thresholds for the maker's calibration on resolved markets.
DEFAULT_THRESHOLDS = {
    "min_samples": 8,           # need a track record before trusting it
    "max_brier": 0.24,          # better than the 0.25 always-50/50 baseline
    "min_edge_vs_market": 0.0,  # must beat the market's own Brier
}


@dataclass
class PredictionPipeline:
    state_dir: str = "state"
    capital: float = 1_000_000.0
    max_position: float = 0.02
    max_drawdown: float = 0.05
    seed: int = 7
    skills_dir: str = SKILLS_DIR
    backend: str = "local"
    maker_model: str = "claude-sonnet-4-6"
    checker_model: str = "claude-opus-4-8"
    thresholds: dict = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    log: Callable[[str], None] = print

    def __post_init__(self) -> None:
        self._cycle = 0
        self.state = State(self.state_dir, clock=self._stamp)
        self.market = SimPredictionMarketConnector(seed=self.seed)
        self.broker = PredictionBroker(capital=self.capital, max_position=self.max_position)

        if self.backend == "claude":
            self.maker: Agent = ClaudeAgent(self.maker_model)
            self.checker: Agent = ClaudeAgent(self.checker_model)
        elif self.backend == "local":
            self.maker = LocalAgent(name="maker")
            self.checker = LocalAgent(name="checker")
        else:
            raise ValueError(f"unknown backend {self.backend!r} (use 'local' or 'claude')")

        self.work_skills_dir = self._sync_working_skills()
        self.estimate_skill: Skill = load_skill(
            os.path.join(self.work_skills_dir, "pm_estimate.md"))
        self.verify_skill: Skill = load_skill(
            os.path.join(self.work_skills_dir, "pm_verification.md"))

    # ---- one full cycle ---------------------------------------------------

    def run_once(self) -> dict[str, Any]:
        self._cycle += 1
        open_markets, newly_resolved = self.market.step()
        self.state.write("open_markets", open_markets)
        self.state.append(f"INGEST: {len(open_markets)} open markets, "
                          f"{len(newly_resolved)} resolved this cycle")

        # Maker proposes a position per open market.
        signals = [self.maker.run_skill(self.estimate_skill, m) for m in open_markets]
        actionable = [s for s in signals if s.get("side") in ("yes", "no")]
        self.state.append(f"SIGNAL: {len(actionable)} actionable of {len(signals)} markets")

        # Checker grades the maker on resolved history (ground truth).
        verified_ok, verdict = self._verify_maker()
        if verified_ok:
            self.state.append(f"VERIFY: PASS maker_brier={verdict['metrics']['maker_brier']} "
                              f"vs market={verdict['metrics']['market_brier']} "
                              f"(n={verdict['metrics']['samples']})")
        else:
            self.state.append(f"VERIFY: KILL all signals ({_fail_reason(verdict)})")

        # Execute only if the maker is currently trusted.
        placed = 0
        if verified_ok:
            prices = {m["symbol"]: m["market_price"] for m in open_markets}
            for sig in actionable:
                pos = self.broker.place(sig, price=prices[sig["symbol"]])
                if pos:
                    placed += 1
                    self.state.append(f"EXECUTE: {pos.side.upper()} {pos.market_id} "
                                      f"@ {pos.entry_price} (est {sig['prob_estimate']}, "
                                      f"edge {sig['edge']:+})")

        # Settle resolved markets, then check risk.
        settled = self.broker.settle(newly_resolved)
        if newly_resolved:
            self.state.append(f"SETTLE: realised {settled:+.0f} on "
                              f"{len(newly_resolved)} resolution(s)")
        killed = self._monitor_risk(open_markets)

        return {
            "cycle": self._cycle,
            "open": len(open_markets),
            "resolved": len(newly_resolved),
            "verified": verified_ok,
            "placed": placed,
            "settled_pnl": round(settled, 0),
            "open_positions": len(self.broker.get_positions()),
            "kill_switch": killed,
        }

    def run(self, cycles: int = 8) -> list[dict[str, Any]]:
        out = []
        for _ in range(cycles):
            s = self.run_once()
            out.append(s)
            self.log(f"[cycle {s['cycle']:>2}] open={s['open']} resolved={s['resolved']} "
                     f"verified={s['verified']} placed={s['placed']} "
                     f"pnl={s['settled_pnl']:+.0f} kill={s['kill_switch']}")
        equity = self.broker.capital + self.broker.realized_pnl
        self.log(f"[final] realised P&L {self.broker.realized_pnl:+.0f} "
                 f"(equity {equity:,.0f})")
        return out

    def build_engine(self, tick: str = "1m", interval: str | None = None) -> LoopEngine:
        """Run the prediction loop on the LoopEngine (for --serve continuous mode)."""
        engine = LoopEngine(tick=tick, logger=self.log)

        @engine.loop(interval=interval or tick, name="prediction_cycle")
        def _cycle():
            self.run_once()

        return engine

    # ---- the verifier: grade the maker on resolved markets ----------------

    def _verify_maker(self) -> tuple[bool, dict]:
        history = self.market.resolved_history(n=40)
        if len(history) < self.thresholds["min_samples"]:
            return False, {"metrics": {"samples": len(history)},
                           "checks": {"sample": False}, "verdict": "fail"}
        estimates, outcomes, prices = [], [], []
        for rec in history:
            est = self.maker.run_skill(self.estimate_skill, rec)
            estimates.append(est["prob_estimate"])
            outcomes.append(rec["outcome"])
            prices.append(rec["market_price"])
        verdict = self.checker.run_skill(self.verify_skill, {
            "estimates": estimates, "outcomes": outcomes,
            "market_prices": prices, "thresholds": self.thresholds,
        })
        return verdict["verdict"] == "pass", verdict

    # ---- risk: settle-aware drawdown + lesson write-back ------------------

    def _monitor_risk(self, open_markets: list[dict]) -> bool:
        prices = {m["symbol"]: m["market_price"] for m in open_markets}
        if not self.broker.get_positions():
            self.state.append("RISK: no open positions to monitor")
            return False
        dd = self.broker.drawdown(prices)
        if dd > self.max_drawdown:
            n = self.broker.close_all(prices)
            self.state.append(f"RISK: drawdown {dd:.2%} > {self.max_drawdown:.0%} — "
                              f"KILL SWITCH, closed {n} position(s)")
            self.estimate_skill.append_lesson(
                lesson=f"Drawdown trigger hit at {dd:.2%}. All positions closed.",
                new_rule=f"Cap aggregate drawdown at {self.max_drawdown:.0%}; flatten on breach.",
                on=self._stamp_date())
            return True
        self.state.append(f"RISK: ok, drawdown {dd:.2%} within {self.max_drawdown:.0%} limit")
        return False

    # ---- working-copy skills + reproducible clock -------------------------

    def _sync_working_skills(self) -> str:
        work = os.path.join(self.state_dir, "skills")
        os.makedirs(work, exist_ok=True)
        for fname in ("pm_estimate.md", "pm_verification.md"):
            src, dst = os.path.join(self.skills_dir, fname), os.path.join(work, fname)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copyfile(src, dst)
        return work

    def _stamp(self) -> str:
        return f"pm-cycle-{self._cycle:03d}"

    def _stamp_date(self) -> date:
        return date(2026, 1, 1) + timedelta(days=self._cycle)


def _fail_reason(verdict: dict) -> str:
    failed = [k for k, ok in verdict.get("checks", {}).items() if not ok]
    return "failed: " + ", ".join(failed) if failed else "rejected"
