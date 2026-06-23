"""Tests for the prediction-market loop (estimate P(YES), Brier-verified)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantloop.mathx import brier_score, clamp01
from quantloop.prediction import PredictionPipeline
from quantloop.connectors.prediction_market import PredictionBroker, SimPredictionMarketConnector


def _pipe():
    return PredictionPipeline(state_dir=os.path.join(tempfile.mkdtemp(), "state"), seed=7)


def test_brier_and_clamp():
    assert brier_score([1, 1], [1, 1]) == 0.0
    assert brier_score([0.5, 0.5], [1, 0]) == 0.25
    assert 0 < clamp01(2.0) < 1 and 0 < clamp01(-1.0) < 1


def test_market_resolves_with_outcomes():
    conn = SimPredictionMarketConnector(seed=3)
    seen_resolved = 0
    for _ in range(10):
        open_markets, resolved = conn.step()
        assert len(open_markets) == conn.n_open          # pool is refilled
        for r in resolved:
            assert r["outcome"] in (0, 1)                 # ground truth attached
            seen_resolved += 1
    assert seen_resolved > 0                              # markets do resolve


def test_full_cycle_records_state():
    pipe = _pipe()
    s = pipe.run_once()
    assert s["cycle"] == 1 and s["open"] > 0
    text = pipe.state.journal_text()
    for stage in ("INGEST", "SIGNAL", "VERIFY", "RISK"):
        assert stage in text


def test_maker_beats_market_and_trades_once_verified():
    pipe = _pipe()
    verified_any = placed_any = False
    for _ in range(12):
        s = pipe.run_once()
        verified_any = verified_any or s["verified"]
        placed_any = placed_any or s["placed"] > 0
    # With an informative signal the maker should pass verification and trade.
    assert verified_any and placed_any


def test_only_trades_when_verified():
    pipe = _pipe()
    for _ in range(12):
        s = pipe.run_once()
        if s["placed"] > 0:
            assert s["verified"]              # never trade on an unverified maker


def test_broker_settles_yes_win():
    b = PredictionBroker(capital=1_000_000, max_position=0.02)
    b.place({"symbol": "M1", "side": "yes", "size": 0.02}, price=0.40)
    realized = b.settle([{"symbol": "M1", "outcome": 1}])   # YES at 0.40 wins
    assert realized > 0 and not b.get_positions()


def test_broker_settles_loss():
    b = PredictionBroker(capital=1_000_000, max_position=0.02)
    b.place({"symbol": "M2", "side": "yes", "size": 0.02}, price=0.40)
    realized = b.settle([{"symbol": "M2", "outcome": 0}])   # YES loses -> -stake
    assert realized < 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all prediction tests passed")
