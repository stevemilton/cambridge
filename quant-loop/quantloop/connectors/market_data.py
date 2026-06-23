"""Simulated market-data connector.

Replaces `fetch_market_data(symbols, lookback)` from the article. It produces a
deterministic geometric-random-walk price/volume series per symbol so signals,
backtests, and the demo are reproducible. Calendar flags (FOMC days, earnings
windows) are emitted alongside the bars so the skill's blackout rules have
something to act on.

In production this is an MCP connector to your data vendor; the return shape is
all the rest of the system depends on.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketDataConnector:
    symbols: list[str]
    seed: int = 7
    drift: float = 0.0002
    vol: float = 0.01
    momentum: float = 0.18  # AR(1) coefficient: a real, learnable edge to find
    _t: int = field(default=0, init=False)
    _last_price: dict[str, float] = field(default_factory=dict, init=False)

    def fetch(self, lookback: int = 30) -> dict[str, dict[str, Any]]:
        """Return `lookback` bars of price/volume per symbol, plus calendar flags.

        Returns follow an AR(1) process (r_t = drift + phi*r_{t-1} + noise), so
        there is genuine, partially-predictable momentum for the maker to fit and
        the checker to validate. Not every window will clear the thresholds — that
        is the point of having a verifier.
        """
        out: dict[str, dict[str, Any]] = {}
        for sym in self.symbols:
            rng = random.Random(hash((self.seed, sym, self._t)) & 0xFFFFFFFF)
            start = self._last_price.get(sym, 100.0 + (hash(sym) % 50))
            prices, volumes = [], []
            price = start
            prev_ret = 0.0
            for _ in range(lookback):
                ret = self.drift + self.momentum * prev_ret + rng.gauss(0, self.vol)
                prev_ret = ret
                price = max(1.0, price * (1.0 + ret))
                prices.append(round(price, 4))
                volumes.append(round(1_000_000 * (1.0 + abs(rng.gauss(0, 0.3))), 0))
            self._last_price[sym] = price
            out[sym] = {
                "symbol": sym,
                "prices": prices,
                "volumes": volumes,
                "flags": self._calendar_flags(sym),
            }
        self._t += 1
        return out

    def _calendar_flags(self, symbol: str) -> dict[str, bool]:
        # Deterministic, sparse calendar events so blackout rules occasionally bind.
        return {
            "fomc": (self._t % 8) == 5,
            "near_earnings": (hash((symbol, self._t)) % 11) == 0,
        }
