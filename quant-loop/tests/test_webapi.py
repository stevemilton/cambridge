"""Tests for the dashboard's request-dispatch layer (no sockets)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantloop.journal import Journal
from quantloop.webapi import dispatch


def _journal():
    return Journal(os.path.join(tempfile.mkdtemp(), "forecasts.json"), today=lambda: "2026-01-01")


def test_add_list_resolve_score_flow():
    j = _journal()
    st, e = dispatch("POST", "/api/forecasts",
                     {"question": "Q?", "your_prob": "70", "market_price": "55"}, j)
    assert st == 200 and e["id"] == "F001"

    st, body = dispatch("GET", "/api/forecasts", None, j)
    assert st == 200 and len(body["forecasts"]) == 1

    st, e = dispatch("POST", "/api/forecasts/F001/resolve", {"outcome": "yes"}, j)
    assert st == 200 and e["outcome"] == 1

    st, score = dispatch("GET", "/api/score", None, j)
    assert st == 200 and score["resolved"] == 1


def test_add_with_odds():
    j = _journal()
    st, e = dispatch("POST", "/api/forecasts",
                     {"question": "WC?", "your_prob": "60", "market_price": "2.0", "odds": True}, j)
    assert st == 200 and e["market_price"] == 0.5   # 2.0 odds -> 50%


def test_delete_and_bad_requests():
    j = _journal()
    dispatch("POST", "/api/forecasts", {"question": "Q", "your_prob": "5", "market_price": "5"}, j)
    st, _ = dispatch("DELETE", "/api/forecasts/F001", None, j)
    assert st == 200 and j.list() == []

    st, _ = dispatch("POST", "/api/forecasts", {"question": "missing fields"}, j)
    assert st == 400
    st, _ = dispatch("GET", "/api/nope", None, j)
    assert st == 404


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all webapi tests passed")
