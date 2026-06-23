"""Stage 4 — Execution.

    @auto_mode
    def execute(signal):
        if verify_signal(signal):
            broker.send_orders(signal, max_position=0.02)
            state.write("active_trades", signal)

Only verified signals reach this stage. The broker connector places the orders
and enforces the position cap as a last line of defence. The loop never asks for
permission — auto mode runs hands-off.
"""

from __future__ import annotations

from ..connectors import BrokerConnector
from ..state import State


def execute(state: State, broker: BrokerConnector) -> list[dict]:
    verified = state.read("verified_signals", default=[])
    data = state.read("latest_data", default={})
    placed: list[dict] = []
    for signal in verified:
        symbol = signal["symbol"]
        last_price = data.get(symbol, {}).get("prices", [100.0])[-1]
        pos = broker.send_orders(signal, price=last_price)
        if pos:
            placed.append({
                "symbol": pos.symbol, "side": pos.side,
                "weight": pos.weight, "entry_price": pos.entry_price,
            })
            state.append(f"EXECUTE: {pos.side} {pos.symbol} @ {pos.entry_price} "
                         f"weight={pos.weight:.2%}")
    state.write("active_trades", placed)
    return placed
