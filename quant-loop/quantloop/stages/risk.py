"""Stage 5 — Risk monitoring (the kill switch).

    @loop(interval="1m")
    def monitor_risk():
        positions = broker.get_positions()
        if drawdown(positions) > 0.05:
            broker.close_all()
            state.append("STATE.md", "Drawdown trigger hit. All positions closed.")

Runs in its own (parallel) sub-loop the entire time. It enforces the drawdown
rule without negotiation and — crucially — writes the lesson back into the
alpha_research skill so the constraint binds the next run. That write-back is the
self-improving step.
"""

from __future__ import annotations

from datetime import date

from ..connectors import BrokerConnector
from ..skills import Skill
from ..state import State


def monitor_risk(state: State, broker: BrokerConnector, max_drawdown: float = 0.05,
                 alpha_skill: Skill | None = None, on: date | None = None) -> bool:
    data = state.read("latest_data", default={})
    prices = {sym: bars["prices"][-1] for sym, bars in data.items()}
    if not broker.get_positions():
        state.append("RISK: no open positions to monitor")
        return False

    dd = broker.drawdown(prices)
    if dd > max_drawdown:
        n = broker.close_all(prices)
        state.append(f"RISK: drawdown {dd:.2%} > {max_drawdown:.0%} — KILL SWITCH, "
                     f"closed {n} position(s)")
        # Write the lesson back to the skill so the loop improves itself.
        if alpha_skill is not None:
            alpha_skill.append_lesson(
                lesson=f"Drawdown trigger hit at {dd:.2%}. All positions closed.",
                new_rule=f"Cap aggregate drawdown at {max_drawdown:.0%}; flatten on breach.",
                on=on,
            )
        return True

    state.append(f"RISK: ok, drawdown {dd:.2%} within {max_drawdown:.0%} limit")
    return False
