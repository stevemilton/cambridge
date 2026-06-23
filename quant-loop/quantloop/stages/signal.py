"""Stage 2 — Signal generation (the maker).

    @loop(trigger="data_updated")
    def generate_signal():
        data = state.read("latest_data.parquet")
        signal = claude.run_skill("alpha_research", data)
        state.write("pending_signal.json", signal)

The maker reads the data and the alpha_research SKILL.md, then proposes a signal
per symbol. It fits only on a training window and hands the held-out track record
forward; it never grades itself. The split between this window and the verifier's
window is what keeps the maker/checker boundary honest.
"""

from __future__ import annotations

from ..agent import Agent
from ..skills import Skill
from ..state import State

TRAIN_FRACTION = 0.5


def generate_signal(state: State, maker: Agent, skill: Skill) -> list[dict]:
    data = state.read("latest_data", default={})
    signals: list[dict] = []
    for symbol, bars in data.items():
        prices = bars["prices"]
        split = max(6, int(len(prices) * TRAIN_FRACTION))
        context = {
            "symbol": symbol,
            "prices": prices[:split],          # in-sample (maker fits here)
            "volumes": bars["volumes"][:split],
            "test_prices": prices[split:],      # out-of-sample (handed to checker)
            "flags": bars.get("flags", {}),
        }
        signal = maker.run_skill(skill, context)
        signals.append(signal)

    state.write("pending_signals", signals)
    actionable = [s for s in signals if s.get("side") in ("long", "short")]
    skipped = [s for s in signals if s.get("side") == "flat"]
    state.append(
        f"SIGNAL: {len(actionable)} actionable, {len(skipped)} skipped "
        f"({', '.join(s['symbol'] + ':' + s.get('reason', 'flat') for s in skipped) or 'none'})"
    )
    return signals
