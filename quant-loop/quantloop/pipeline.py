"""Wiring the six pieces around the five-stage cycle.

This is the whole system in one place:

    automation (LoopEngine) ── fires the cycle on a cadence
    skills      ───────────── alpha_research (maker) + backtest_verification (checker)
    state       ───────────── handoffs between stages + the run journal
    verifier    ───────────── a *separate* checker agent grades each signal
    connectors  ───────────── market data in, broker out
    worktrees   ───────────── available for running stages in parallel isolation

    data flows in -> signals get generated -> signals get verified ->
    verified signals get executed -> risk gets monitored -> lessons get written
    back -> then it starts over.

`run_once()` runs one full trading cycle synchronously (the natural data
dependency). `build_engine()` instead expresses the same stages as the article's
automations — an interval ingest that emits `data_updated`, trigger-driven
signal/verify/execute, and a parallel risk monitor — so you can watch the
event-driven loop tick.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable

from .agent import Agent, ClaudeAgent, LocalAgent
from .connectors import BrokerConnector, MarketDataConnector
from .loop import LoopEngine
from .skills import Skill, load_skill
from .state import State
from .stages import execute, generate_signal, ingest, monitor_risk, verify_signal
from .verifier import Verifier

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")


@dataclass
class Pipeline:
    universe: list[str] = field(default_factory=lambda: ["BTC-PERP", "ETH-PERP", "SOL-PERP"])
    state_dir: str = "state"
    capital: float = 1_000_000.0
    max_position: float = 0.02
    max_drawdown: float = 0.05
    lookback: int = 180
    seed: int = 7
    skills_dir: str = SKILLS_DIR
    backend: str = "local"  # "local" (offline, deterministic) or "claude" (real models)
    maker_model: str = "claude-sonnet-4-6"   # cheaper model proposes
    checker_model: str = "claude-opus-4-8"   # stronger model verifies
    log: Callable[[str], None] = print

    def __post_init__(self) -> None:
        self._cycle = 0
        self.state = State(self.state_dir, clock=self._stamp)
        self.data = MarketDataConnector(self.universe, seed=self.seed)
        self.broker = BrokerConnector(capital=self.capital, max_position=self.max_position)

        # Maker and checker are deliberately *different* agent instances. With the
        # "claude" backend the checker runs a stronger model than the maker
        # (Opus checks, Sonnet makes) — the article's ensemble logic, made real.
        if self.backend == "claude":
            self.maker: Agent = ClaudeAgent(self.maker_model)
            self.checker: Agent = ClaudeAgent(self.checker_model)
        elif self.backend == "local":
            self.maker = LocalAgent(name="maker")
            self.checker = LocalAgent(name="checker")
        else:
            raise ValueError(f"unknown backend {self.backend!r} (use 'local' or 'claude')")

        # Operate on a working copy of the skills under state/ so the loop's
        # self-improvement (lessons written back) persists across runs without
        # mutating the source-controlled templates in skills/.
        self.work_skills_dir = self._sync_working_skills()
        self.alpha_skill: Skill = load_skill(
            os.path.join(self.work_skills_dir, "alpha_research.md"))
        self.verify_skill: Skill = load_skill(
            os.path.join(self.work_skills_dir, "backtest_verification.md"))
        self.verifier = Verifier(self.checker, self.verify_skill)

    # ---- one full cycle (used by the simple demo and tests) ----------------

    def run_once(self) -> dict[str, Any]:
        self._cycle += 1
        ingest(self.state, self.data, lookback=self.lookback)
        generate_signal(self.state, self.maker, self.alpha_skill)
        verify_signal(self.state, self.verifier)
        placed = execute(self.state, self.broker)
        killed = monitor_risk(self.state, self.broker, self.max_drawdown,
                              alpha_skill=self.alpha_skill, on=self._stamp_date())
        return {
            "cycle": self._cycle,
            "verified": len(self.state.read("verified_signals", [])),
            "placed": len(placed),
            "open_positions": len(self.broker.get_positions()),
            "kill_switch": killed,
        }

    def run(self, cycles: int = 5) -> list[dict[str, Any]]:
        summaries = []
        for _ in range(cycles):
            s = self.run_once()
            summaries.append(s)
            self.log(f"[cycle {s['cycle']:>2}] verified={s['verified']} placed={s['placed']} "
                     f"open={s['open_positions']} kill={s['kill_switch']}")
        return summaries

    # ---- the event-driven automation flavour -------------------------------

    def build_engine(self, tick: str = "1m") -> LoopEngine:
        """Express the five stages as the article's automations on a LoopEngine.

        Ingest is the heartbeat; it emits `data_updated`. Signal/verify/execute are
        trigger-driven and chain via events. Risk is a parallel interval monitor.
        """
        engine = LoopEngine(tick=tick, logger=self.log)

        @engine.loop(interval=tick, name="ingest")
        def _ingest():
            self._cycle += 1
            ingest(self.state, self.data, lookback=self.lookback)
            engine.emit("data_updated")

        @engine.loop(trigger="data_updated", name="signal")
        def _signal():
            generate_signal(self.state, self.maker, self.alpha_skill)
            engine.emit("signal_ready")

        @engine.loop(trigger="signal_ready", name="verify")
        def _verify():
            verify_signal(self.state, self.verifier)
            engine.emit("signal_verified")

        @engine.loop(trigger="signal_verified", name="execute")
        def _execute():
            execute(self.state, self.broker)

        @engine.loop(interval=tick, name="risk")
        def _risk():
            monitor_risk(self.state, self.broker, self.max_drawdown,
                         alpha_skill=self.alpha_skill, on=self._stamp_date())

        return engine

    # ---- a /goal example: iterate until a *checkable* Sharpe is reached -----

    def research_goal_engine(self, target_sharpe: float = 1.5,
                             max_iterations: int = 25) -> LoopEngine:
        """`/goal`: keep generating until the verified Sharpe clears a threshold.

        The stop condition is graded by the verifier, never by the maker's claim
        of being done — the article's core warning about loops that exit quietly.
        """
        engine = LoopEngine(tick="1m", logger=self.log)
        best = {"sharpe": float("-inf")}

        def reached() -> bool:
            return best["sharpe"] >= target_sharpe

        @engine.goal(check=reached, max_iterations=max_iterations, name="alpha_search")
        def _search():
            ingest(self.state, self.data, lookback=self.lookback)
            generate_signal(self.state, self.maker, self.alpha_skill)
            verified = verify_signal(self.state, self.verifier)
            for sig in verified:
                m = sig.get("verification", {}).get("metrics", {})
                best["sharpe"] = max(best["sharpe"], m.get("sharpe", float("-inf")))

        engine._best = best  # expose for inspection in the demo/tests
        return engine

    def _sync_working_skills(self) -> str:
        work = os.path.join(self.state_dir, "skills")
        os.makedirs(work, exist_ok=True)
        for fname in ("alpha_research.md", "backtest_verification.md", "risk_management.md"):
            src = os.path.join(self.skills_dir, fname)
            dst = os.path.join(work, fname)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copyfile(src, dst)
        return work

    # ---- deterministic clock so journals/lessons are reproducible ----------

    def _stamp(self) -> str:
        return f"cycle-{self._cycle:03d}"

    def _stamp_date(self) -> date:
        return date(2026, 1, 1) + timedelta(days=self._cycle)
