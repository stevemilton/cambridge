"""Simulated broker connector.

Replaces `broker.send_orders(...)`, `broker.get_positions()`, and
`broker.close_all()` from the article. It tracks positions, marks them to a
supplied price, and reports drawdown so the risk loop has a real number to act
on. The position cap is enforced here too — the connector is the last line of
defence, not just the agent.

In production this is an MCP connector to your real broker/exchange. The
difference between a loop that *suggests* trades and one that *places* them is
exactly this object.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Position:
    symbol: str
    side: str          # "long" | "short"
    weight: float      # fraction of capital
    entry_price: float


@dataclass
class BrokerConnector:
    capital: float = 1_000_000.0
    max_position: float = 0.02
    positions: dict[str, Position] = field(default_factory=dict)
    _equity_peak: float = field(default=0.0, init=False)
    realized_pnl: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._equity_peak = self.capital

    def send_orders(self, signal: dict, price: float) -> Position | None:
        """Open a position from a verified signal, clamped to the position cap."""
        if signal.get("side") not in ("long", "short"):
            return None
        weight = min(float(signal.get("size", self.max_position)), self.max_position)
        pos = Position(signal["symbol"], signal["side"], weight, price)
        self.positions[signal["symbol"]] = pos
        return pos

    def get_positions(self) -> list[Position]:
        return list(self.positions.values())

    def mark(self, prices: dict[str, float]) -> float:
        """Mark open positions to market and return current total equity."""
        unrealized = 0.0
        for pos in self.positions.values():
            px = prices.get(pos.symbol, pos.entry_price)
            move = (px - pos.entry_price) / pos.entry_price
            direction = 1.0 if pos.side == "long" else -1.0
            unrealized += direction * move * pos.weight * self.capital
        equity = self.capital + self.realized_pnl + unrealized
        self._equity_peak = max(self._equity_peak, equity)
        return equity

    def drawdown(self, prices: dict[str, float]) -> float:
        """Current peak-to-trough drawdown of equity (>= 0)."""
        equity = self.mark(prices)
        if self._equity_peak <= 0:
            return 0.0
        return max(0.0, (self._equity_peak - equity) / self._equity_peak)

    def close_all(self, prices: dict[str, float]) -> int:
        """Flatten everything (the kill switch). Returns count closed."""
        n = len(self.positions)
        equity = self.mark(prices)
        self.realized_pnl = equity - self.capital
        self.positions.clear()
        return n
