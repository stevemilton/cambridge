"""Pure request-dispatch logic for the dashboard — no sockets, so it's testable.

`dispatch(method, path, body, journal)` maps an HTTP request to a Journal
operation and returns `(status, json-able result)`. dashboard.py wraps this in a
stdlib HTTP server; tests call it directly.
"""

from __future__ import annotations

from typing import Any

from . import mathx
from .journal import Journal


def dispatch(method: str, path: str, body: dict | None, journal: Journal) -> tuple[int, Any]:
    body = body or {}
    parts = [p for p in path.split("/") if p]   # e.g. ["api","forecasts","F001","resolve"]

    if method == "GET" and path == "/api/forecasts":
        return 200, {"forecasts": journal.list()}

    if method == "GET" and path == "/api/score":
        return 200, journal.score()

    if method == "POST" and path == "/api/forecasts":
        try:
            market = body["market_price"]
            if body.get("odds"):
                market = mathx.odds_to_prob(float(market))
            entry = journal.add(body["question"], body["your_prob"], market,
                                body.get("category", ""), body.get("notes", ""))
            return 200, entry
        except (KeyError, ValueError) as exc:
            return 400, {"error": f"bad add: {exc}"}

    if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "forecasts"] \
            and parts[3] == "resolve":
        try:
            return 200, journal.resolve(parts[2], body["outcome"])
        except (KeyError, ValueError) as exc:
            return 400, {"error": f"bad resolve: {exc}"}

    if method == "DELETE" and len(parts) == 3 and parts[:2] == ["api", "forecasts"]:
        journal.remove(parts[2])
        return 200, {"ok": True}

    return 404, {"error": "not found"}
