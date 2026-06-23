"""Tests for the five-stage pipeline and the maker/checker split."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantloop.mathx import max_drawdown, newey_west_tstat, sharpe
from quantloop.pipeline import Pipeline
from quantloop.skills import load_skill
from quantloop.verifier import Verifier
from quantloop.agent import LocalAgent


def _pipe():
    d = tempfile.mkdtemp()
    return Pipeline(state_dir=os.path.join(d, "state"), seed=7)


def test_full_cycle_runs_and_records_state():
    pipe = _pipe()
    summary = pipe.run_once()
    assert summary["cycle"] == 1
    # state journal exists and captured each stage
    text = pipe.state.journal_text()
    for stage in ("INGEST", "SIGNAL", "VERIFY", "RISK"):
        assert stage in text, f"{stage} missing from journal"


def test_only_verified_signals_get_executed():
    pipe = _pipe()
    pipe.run_once()
    verified = pipe.state.read("verified_signals", [])
    placed = pipe.state.read("active_trades", [])
    # every placed trade must correspond to a verified signal
    assert len(placed) <= len(verified)
    verified_syms = {s["symbol"] for s in verified}
    assert all(p["symbol"] in verified_syms for p in placed)


def test_position_cap_enforced_by_broker():
    pipe = _pipe()
    pipe.run_once()
    for pos in pipe.broker.get_positions():
        assert pos.weight <= pipe.max_position + 1e-9


def test_verifier_kills_a_bad_signal():
    skill = load_skill(os.path.join(os.path.dirname(__file__), "..", "skills",
                                    "backtest_verification.md"))
    verifier = Verifier(LocalAgent("checker"), skill)
    # a pure-loss return stream must fail every threshold
    bad = {"symbol": "X", "side": "long", "oos_returns": [-0.02] * 30}
    verdict = verifier.verify(bad, bad["oos_returns"])
    assert not verdict


def test_blackout_rule_skips_signal():
    pipe = _pipe()
    # force an FOMC day on the data connector
    pipe.data._t = 5  # _calendar_flags returns fomc=True when _t % 8 == 5
    pipe.run_once()
    signals = pipe.state.read("pending_signals", [])
    assert any(s.get("side") == "flat" and "FOMC" in s.get("reason", "") for s in signals)


def test_risk_monitor_writes_lesson_back():
    from quantloop.stages.risk import monitor_risk
    pipe = _pipe()
    before = len(pipe.alpha_skill.lessons)
    pipe.run_once()
    data = pipe.state.read("latest_data")
    # open a full long book directly, then crash the market so portfolio DD > 5%
    for sym in pipe.universe:
        pipe.broker.send_orders({"symbol": sym, "side": "long", "size": 0.02},
                                price=data[sym]["prices"][-1])
    for sym in data:
        data[sym]["prices"][-1] *= 0.05
    pipe.state.write("latest_data", data)
    killed = monitor_risk(pipe.state, pipe.broker, pipe.max_drawdown,
                          alpha_skill=pipe.alpha_skill)
    assert killed                                  # kill switch fired
    assert not pipe.broker.get_positions()         # book flattened
    assert len(pipe.alpha_skill.lessons) > before  # lesson written back to skill


def test_mathx_sanity():
    up = [0.01] * 50
    assert sharpe(up) > 0
    assert max_drawdown(up) == 0.0
    assert max_drawdown([0.1, -0.5, 0.1]) > 0.4
    assert newey_west_tstat([0.01] * 50) > 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all pipeline tests passed")
