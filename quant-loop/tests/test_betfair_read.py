"""Tests for the read-only Betfair client — parsing/merge logic, no network.

A fake transport returns canned login/catalogue/book responses, so we verify
that odds get merged onto runners and converted to probabilities correctly.
The live HTTP itself needs real credentials to verify.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantloop.connectors.betfair_read import BetfairReadClient


def _fake_transport():
    def transport(url, headers, body):
        if "login" in url:
            return {"status": "SUCCESS", "token": "tok123"}
        payload = __import__("json").loads(body)
        method = payload["method"]
        if method.endswith("listMarketCatalogue"):
            return {"result": [{
                "marketId": "1.234",
                "marketName": "Match Odds",
                "event": {"name": "Brazil v Croatia"},
                "runners": [
                    {"selectionId": 11, "runnerName": "Brazil"},
                    {"selectionId": 22, "runnerName": "Croatia"},
                ],
            }]}
        if method.endswith("listMarketBook"):
            return {"result": [{
                "marketId": "1.234",
                "runners": [
                    {"selectionId": 11, "ex": {"availableToBack": [{"price": 2.0, "size": 100}]}},
                    {"selectionId": 22, "ex": {"availableToBack": [{"price": 4.0, "size": 50}]}},
                ],
            }]}
        return {"result": []}
    return transport


def test_search_merges_odds_and_probs():
    c = BetfairReadClient("key", "user", "pw", transport=_fake_transport())
    markets = c.search_markets("World Cup")
    assert len(markets) == 1
    m = markets[0]
    assert m["title"] == "Brazil v Croatia — Match Odds"
    runners = {r["name"]: r for r in m["runners"]}
    assert runners["Brazil"]["odds"] == 2.0 and runners["Brazil"]["prob"] == 0.5
    assert runners["Croatia"]["odds"] == 4.0 and runners["Croatia"]["prob"] == 0.25


def test_login_failure_raises():
    def bad(url, headers, body):
        return {"status": "FAIL", "error": "INVALID_USERNAME_OR_PASSWORD"}
    c = BetfairReadClient("key", "user", "pw", transport=bad)
    try:
        c.search_markets("x")
        assert False, "should have raised"
    except RuntimeError as e:
        assert "login failed" in str(e).lower()


def test_from_env_requires_all_three(monkeypatch=None):
    for k in ("BETFAIR_APP_KEY", "BETFAIR_USERNAME", "BETFAIR_PASSWORD"):
        os.environ.pop(k, None)
    assert BetfairReadClient.from_env() is None
    os.environ["BETFAIR_APP_KEY"] = "k"
    os.environ["BETFAIR_USERNAME"] = "u"
    os.environ["BETFAIR_PASSWORD"] = "p"
    try:
        assert BetfairReadClient.from_env() is not None
    finally:
        for k in ("BETFAIR_APP_KEY", "BETFAIR_USERNAME", "BETFAIR_PASSWORD"):
            os.environ.pop(k, None)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all betfair_read tests passed")
