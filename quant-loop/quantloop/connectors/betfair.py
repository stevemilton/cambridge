"""Betfair Exchange connector — SKELETON for going live (UK-legal).

This maps the Betfair Exchange API onto the same two surfaces the prediction
loop already uses (`SimPredictionMarketConnector` / `PredictionBroker`), so you
swap it in without touching the loop:

    market data -> step()  returning (open markets, newly-resolved)
    broker      -> place() / settle() / drawdown() / close_all()

It is intentionally a template: the network calls are sketched and marked TODO.
You supply a Betfair account, an application key, and a login (session token or
cert login for bots), and verify the exact request shapes against the current
Betfair docs before trusting it with money. Start with tiny stakes.

Key translation: Betfair quotes **decimal odds**; this loop speaks
**probability**. They are reciprocals — `prob = 1 / odds`, `odds = 1 / prob` —
so a back price of 2.0 is a 50% implied probability. The helpers below do the
conversion; the rest of the loop never sees odds.

Docs: https://developer.betfair.com/ (Exchange "betting" API, JSON-RPC).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import mathx

BETTING_ENDPOINT = "https://api.betfair.com/exchange/betting/json-rpc/v1"
LOGIN_ENDPOINT = "https://identitysso.betfair.com/api/login"          # interactive
CERT_LOGIN_ENDPOINT = "https://identitysso-cert.betfair.com/api/certlogin"  # bots


def odds_to_prob(odds: float) -> float:
    """Decimal odds -> implied probability (2.0 -> 0.5)."""
    return mathx.clamp01(1.0 / odds) if odds and odds > 1.0 else 0.0


def prob_to_odds(prob: float) -> float:
    """Probability -> decimal odds (0.5 -> 2.0)."""
    p = mathx.clamp01(prob)
    return 1.0 / p


@dataclass
class BetfairConnector:
    """Read open markets and their YES prices (back odds -> probability)."""
    app_key: str
    session_token: str
    market_filter: dict = field(default_factory=dict)  # event types / competitions to follow
    _session: Any = field(default=None, init=False)

    def _headers(self) -> dict[str, str]:
        return {
            "X-Application": self.app_key,
            "X-Authentication": self.session_token,
            "Content-Type": "application/json",
        }

    def _rpc(self, method: str, params: dict) -> Any:
        """One JSON-RPC call to the betting endpoint."""
        import requests  # local import so the offline reference needs no deps
        body = {"jsonrpc": "2.0", "method": f"SportsAPING/v1.0/{method}",
                "params": params, "id": 1}
        r = requests.post(BETTING_ENDPOINT, json=body, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()["result"]

    def step(self) -> tuple[list[dict], list[dict]]:
        """Return (open market states, newly-resolved states).

        TODO:
          1. listMarketCatalogue(filter=self.market_filter) -> market ids + runners.
          2. listMarketBook(marketIds=...) -> best back/lay prices per runner.
             Build each open market state:
               {"symbol": marketId, "question": marketName,
                "market_price": odds_to_prob(best_back_odds_of_YES_runner),
                "signal": <your research probability for this event>,
                "prices": [...recent...]}
          3. Detect settled markets (status == "CLOSED") since the last poll and
             emit resolved records:
               {"symbol": marketId, "market_price": <entry prob>,
                "signal": <entry signal>, "outcome": 1 if YES runner won else 0}
             Persist entry-time price/signal yourself (Betfair won't replay them).
        """
        raise NotImplementedError(
            "Wire listMarketCatalogue + listMarketBook here; convert back odds with "
            "odds_to_prob(). See the TODO and BETFAIR.md."
        )


@dataclass
class BetfairBroker:
    """Place and settle real bets. Same interface as PredictionBroker."""
    app_key: str
    session_token: str
    capital: float = 1_000.0       # your exchange balance (in your currency)
    max_position: float = 0.02
    positions: dict[str, Any] = field(default_factory=dict)
    realized_pnl: float = field(default=0.0, init=False)

    def place(self, signal: dict, price: float):
        """Back the YES or NO runner at the current price.

        TODO: placeOrders(marketId, instructions=[{selectionId, side:"BACK",
        orderType:"LIMIT", limitOrder:{size, price: prob_to_odds(price), ...}}]).
        side="yes" -> back the YES runner; side="no" -> back the NO runner (or lay
        YES, depending on how you model the two outcomes). Stake = weight*capital.
        Record entry price for later settlement grading.
        """
        raise NotImplementedError("Wire placeOrders here (back/lay). See BETFAIR.md.")

    def get_positions(self) -> list:
        return list(self.positions.values())

    def settle(self, resolved: list[dict]) -> float:
        """Realise P&L from cleared markets.

        TODO: poll listClearedOrders (or your own settlement) for the markets in
        `resolved`, add the profit/loss to realized_pnl, and drop the positions.
        Betfair reports realised P&L per cleared bet — use it directly rather than
        recomputing payoff from odds.
        """
        raise NotImplementedError("Wire listClearedOrders here. See BETFAIR.md.")

    def drawdown(self, prices: dict[str, float]) -> float:
        raise NotImplementedError("Mark open bets to current odds; see PredictionBroker.")

    def close_all(self, prices: dict[str, float]) -> int:
        """Kill switch: cancel unmatched bets and/or cash out matched ones.

        TODO: cancelOrders for unmatched; for matched positions, place an
        offsetting lay/back to flatten (Betfair has no single "close" call).
        """
        raise NotImplementedError("Wire cancelOrders / offsetting bets. See BETFAIR.md.")
