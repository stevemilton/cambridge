"""Betfair Exchange — READ-ONLY client (find markets + live odds, never bets).

Powers the dashboard's "Import from Betfair" panel: search markets, read the
best-back odds, convert to a probability you can log against. It calls only the
read endpoints — login, listMarketCatalogue, listMarketBook. There is no
order-placement code here on purpose; betting stays gated until the journal
proves an edge.

Stdlib only (urllib) — no `requests` needed. Credentials come from the
environment and are never written anywhere:
    BETFAIR_APP_KEY, BETFAIR_USERNAME, BETFAIR_PASSWORD

The network transport is injectable so the parsing/merging logic is unit-tested
without hitting Betfair. The live calls themselves need your key to verify.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Callable

from .. import mathx

LOGIN_ENDPOINT = "https://identitysso.betfair.com/api/login"
BETTING_ENDPOINT = "https://api.betfair.com/exchange/betting/json-rpc/v1"
SOCCER_EVENT_TYPE = "1"


def _urllib_post(url: str, headers: dict, body: bytes) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode())


class BetfairReadClient:
    def __init__(self, app_key: str, username: str, password: str,
                 transport: Callable[[str, dict, bytes], dict] | None = None):
        self.app_key = app_key
        self.username = username
        self.password = password
        self.transport = transport or _urllib_post
        self.token: str | None = None

    @classmethod
    def from_env(cls) -> "BetfairReadClient | None":
        key = os.environ.get("BETFAIR_APP_KEY")
        user = os.environ.get("BETFAIR_USERNAME")
        pw = os.environ.get("BETFAIR_PASSWORD")
        if not (key and user and pw):
            return None
        return cls(key, user, pw)

    # ---- auth -------------------------------------------------------------

    def login(self) -> None:
        headers = {
            "X-Application": self.app_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        body = urllib.parse.urlencode({"username": self.username,
                                       "password": self.password}).encode()
        resp = self.transport(LOGIN_ENDPOINT, headers, body)
        if resp.get("status") != "SUCCESS" or not resp.get("token"):
            raise RuntimeError(f"Betfair login failed: {resp.get('error') or resp.get('status')}")
        self.token = resp["token"]

    def _rpc(self, method: str, params: dict) -> Any:
        if not self.token:
            self.login()
        headers = {
            "X-Application": self.app_key,
            "X-Authentication": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"jsonrpc": "2.0", "method": f"SportsAPING/v1.0/{method}",
                   "params": params, "id": 1}
        resp = self.transport(BETTING_ENDPOINT, headers, json.dumps(payload).encode())
        if resp.get("error"):
            raise RuntimeError(f"Betfair {method} error: {resp['error']}")
        return resp.get("result", [])

    # ---- read: markets + odds --------------------------------------------

    def search_markets(self, query: str, max_results: int = 8,
                       event_type: str = SOCCER_EVENT_TYPE) -> list[dict]:
        """Find markets matching `query` and attach each runner's best-back odds.

        Returns: [{marketId, title, runners: [{selectionId, name, odds, prob}]}].
        """
        catalogue = self._rpc("listMarketCatalogue", {
            "filter": {"textQuery": query, "eventTypeIds": [event_type]},
            "marketProjection": ["RUNNER_DESCRIPTION", "EVENT", "COMPETITION"],
            "maxResults": int(max_results),
            "sort": "FIRST_TO_START",
        })
        market_ids = [m["marketId"] for m in catalogue]
        books = self._rpc("listMarketBook", {
            "marketIds": market_ids,
            "priceProjection": {"priceData": ["EX_BEST_OFFERS"]},
        }) if market_ids else []

        best_back = self._best_back_map(books)
        out = []
        for m in catalogue:
            event = (m.get("event") or {}).get("name", "")
            title = f"{event} — {m['marketName']}".strip(" —")
            runners = []
            for r in m.get("runners", []):
                price = best_back.get(m["marketId"], {}).get(r["selectionId"])
                runners.append({
                    "selectionId": r["selectionId"],
                    "name": r.get("runnerName", str(r["selectionId"])),
                    "odds": price,
                    "prob": round(mathx.odds_to_prob(price), 4) if price else None,
                })
            out.append({"marketId": m["marketId"], "title": title, "runners": runners})
        return out

    @staticmethod
    def _best_back_map(books: list[dict]) -> dict[Any, dict]:
        """marketId -> {selectionId -> best available back price}."""
        result: dict[Any, dict] = {}
        for b in books:
            sel = {}
            for r in b.get("runners", []):
                offers = (r.get("ex") or {}).get("availableToBack") or []
                if offers:
                    sel[r["selectionId"]] = offers[0]["price"]
            result[b["marketId"]] = sel
        return result
