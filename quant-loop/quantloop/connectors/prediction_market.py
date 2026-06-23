"""Prediction-market connectors — the venue-agnostic core.

A prediction market is a *question* priced as a probability (0..1) that resolves
to a known YES/NO outcome. That resolution is what makes these markets the best
fit for this loop: every market becomes a labelled example the verifier can
grade and the skill can learn from.

This module provides:

  * SimPredictionMarketConnector — binary markets with a hidden true probability,
    a noisy traded price, a public `signal` (your "research"), and a resolution.
    Lets the whole prediction loop run offline and deterministically.
  * PredictionBroker — buys YES/NO contracts and settles them on resolution.

A real venue (Betfair, Smarkets, Polymarket) implements the same two surfaces:
`step()` returning open markets + newly-resolved ones, and the broker's
place/settle/drawdown. See `BETFAIR.md` for the mapping (odds <-> probability).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .. import mathx


@dataclass
class Market:
    id: str
    question: str
    p_true: float            # hidden ground-truth probability
    price: float             # observable market price (YES), 0..1
    signal: float            # public estimate of p_true — the maker's "research"
    entry_price: float       # decision-time price (when you'd bet) — near 50/50
    age: int = 0
    horizon: int = 4         # resolves after this many steps
    history: list[float] = field(default_factory=list)

    def state(self) -> dict[str, Any]:
        """Live view of an OPEN market — current price, for trading."""
        return {
            "symbol": self.id,
            "question": self.question,
            "market_price": round(self.price, 4),
            "signal": round(self.signal, 4),
            "prices": [round(p, 4) for p in self.history],
        }

    def resolved_record(self, outcome: int) -> dict[str, Any]:
        """Grading view of a RESOLVED market — the *entry-time* forecast vs truth.

        Calibration is judged on the forecast you could have made when you bet
        (market still near 50/50, your research signal the edge), not on the
        near-settled price the market drifts to just before resolution.
        """
        return {
            "symbol": self.id,
            "question": self.question,
            "market_price": round(self.entry_price, 4),
            "signal": round(self.signal, 4),
            "outcome": outcome,
        }


@dataclass
class SimPredictionMarketConnector:
    n_open: int = 6
    seed: int = 7
    signal_noise: float = 0.10   # how informative `signal` is (lower = sharper edge)
    price_noise: float = 0.06
    _rng: random.Random = field(init=False)
    _t: int = field(default=0, init=False)
    _open: dict[str, Market] = field(default_factory=dict, init=False)
    _next_id: int = field(default=0, init=False)
    resolved: list[dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        while len(self._open) < self.n_open:
            self._spawn()

    def step(self) -> tuple[list[dict], list[dict]]:
        """Advance one period. Returns (open market states, newly-resolved states).

        Newly-resolved states carry the final price, signal, and the realised
        `outcome` (1/0) — the ground truth the verifier and broker need.
        """
        self._t += 1
        newly_resolved: list[dict] = []
        for mid in list(self._open):
            m = self._open[mid]
            # Price random-walks, drifting mildly toward truth (a semi-efficient market).
            m.price = mathx.clamp01(m.price + 0.25 * (m.p_true - m.price)
                                    + self._rng.gauss(0, self.price_noise))
            m.history.append(m.price)
            m.age += 1
            if m.age >= m.horizon:
                outcome = 1 if self._rng.random() < m.p_true else 0
                rec = m.resolved_record(outcome)
                newly_resolved.append(rec)
                self.resolved.append(rec)
                del self._open[mid]
        while len(self._open) < self.n_open:
            self._spawn()
        return [m.state() for m in self._open.values()], newly_resolved

    def resolved_history(self, n: int = 40) -> list[dict]:
        """Recent resolved markets (with outcomes) for the verifier to grade against."""
        return self.resolved[-n:]

    def _spawn(self) -> None:
        p_true = round(self._rng.uniform(0.15, 0.85), 4)
        signal = mathx.clamp01(p_true + self._rng.gauss(0, self.signal_noise))
        price = mathx.clamp01(0.5 + self._rng.gauss(0, 0.1))  # market starts near 50/50
        mid = f"MKT-{self._next_id:04d}"
        self._next_id += 1
        # Staggered horizons so markets resolve steadily, not in batches.
        horizon = self._rng.randint(2, 5)
        self._open[mid] = Market(id=mid, question=f"Will event {mid} occur?",
                                 p_true=p_true, price=price, signal=signal,
                                 entry_price=price, horizon=horizon, history=[price])


@dataclass
class Position:
    market_id: str
    side: str        # "yes" | "no"
    weight: float    # fraction of capital staked
    entry_price: float  # YES price at entry


@dataclass
class PredictionBroker:
    capital: float = 1_000_000.0
    max_position: float = 0.02
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = field(default=0.0, init=False)
    _equity_peak: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._equity_peak = self.capital

    def place(self, signal: dict, price: float) -> Position | None:
        if signal.get("side") not in ("yes", "no"):
            return None
        weight = min(float(signal.get("size", self.max_position)), self.max_position)
        pos = Position(signal["symbol"], signal["side"], weight, price)
        self.positions[signal["symbol"]] = pos
        return pos

    def get_positions(self) -> list[Position]:
        return list(self.positions.values())

    def settle(self, resolved: list[dict]) -> float:
        """Realise P&L for any open position whose market just resolved.

        Buying YES at price p pays (1-p)/p per unit stake on a win, -1 on a loss;
        buying NO at (1-p) pays p/(1-p) on a win, -1 on a loss.
        """
        realized = 0.0
        for rec in resolved:
            pos = self.positions.pop(rec["symbol"], None)
            if pos is None:
                continue
            p = mathx.clamp01(pos.entry_price)
            won = (rec["outcome"] == 1) if pos.side == "yes" else (rec["outcome"] == 0)
            if won:
                ret = (1 - p) / p if pos.side == "yes" else p / (1 - p)
            else:
                ret = -1.0
            realized += ret * pos.weight * self.capital
        self.realized_pnl += realized
        self._equity_peak = max(self._equity_peak, self.capital + self.realized_pnl)
        return realized

    def drawdown(self, prices: dict[str, float]) -> float:
        """Peak-to-trough drawdown of realised + marked-to-market equity (>= 0)."""
        unrealized = 0.0
        for pos in self.positions.values():
            q = mathx.clamp01(prices.get(pos.market_id, pos.entry_price))
            p = mathx.clamp01(pos.entry_price)
            move = (q - p) / p if pos.side == "yes" else (p - q) / (1 - p)
            unrealized += move * pos.weight * self.capital
        equity = self.capital + self.realized_pnl + unrealized
        if self._equity_peak <= 0:
            return 0.0
        return max(0.0, (self._equity_peak - equity) / self._equity_peak)

    def close_all(self, prices: dict[str, float]) -> int:
        n = len(self.positions)
        self.positions.clear()
        return n
