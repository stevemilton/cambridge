"""Tests for the forecasting journal (edge-detection tool)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantloop.journal import Journal, parse_outcome, parse_prob
from quantloop.mathx import odds_to_prob, prob_to_odds


def _journal():
    return Journal(os.path.join(tempfile.mkdtemp(), "forecasts.json"),
                   today=lambda: "2026-01-01")


def test_parse_prob_forms():
    assert parse_prob("0.7") == 0.7
    assert parse_prob("70") == 0.7
    assert parse_prob("70%") == 0.7
    assert parse_prob("1%") == 0.01
    assert 0 < parse_prob("150") <= 1   # clamped


def test_parse_outcome():
    assert parse_outcome("yes") == 1 and parse_outcome("Y") == 1 and parse_outcome("1") == 1
    assert parse_outcome("no") == 0 and parse_outcome("0") == 0


def test_odds_conversion():
    # Decimal odds <-> probability, for football/Betfair-style inputs.
    assert odds_to_prob(2.0) == 0.5
    assert abs(odds_to_prob(2.5) - 0.4) < 1e-9
    assert abs(odds_to_prob(4.0) - 0.25) < 1e-9
    assert abs(prob_to_odds(0.5) - 2.0) < 1e-9


def test_add_resolve_roundtrip_persists():
    j = _journal()
    e = j.add("Will X happen?", "70%", "55%", category="box-office")
    assert e["id"] == "F001" and e["status"] == "open"
    j.resolve("F001", "yes")
    # reload from disk to confirm persistence
    j2 = Journal(j.path)
    assert j2.list("resolved")[0]["outcome"] == 1


def test_score_detects_an_edge():
    # Maker nails 8 markets the market priced at a coin-flip -> clear edge.
    j = _journal()
    for i in range(8):
        outcome = i % 2  # alternate
        your = 0.9 if outcome == 1 else 0.1   # confident and correct
        j.add(f"market {i}", your, 0.5)
        j.resolve(f"F{i+1:03d}", "yes" if outcome == 1 else "no")
    s = j.score()
    assert s["beats_market"] and s["beats_baseline"]
    assert s["your_brier"] < s["market_brier"]
    assert not s["enough_samples"]            # 8 < 20: honest "need more" gate
    assert "need" in s["verdict"].lower()


def test_score_no_edge_when_matching_market():
    j = _journal()
    for i in range(6):
        j.add(f"m{i}", 0.5, 0.5)               # no opinion, just the market
        j.resolve(f"F{i+1:03d}", "yes" if i % 2 else "no")
    s = j.score()
    assert not s["beats_market"]              # can't beat what you copied


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all journal tests passed")
