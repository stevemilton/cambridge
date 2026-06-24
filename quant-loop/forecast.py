#!/usr/bin/env python3
"""Forecasting journal CLI — prove your edge for £0 before wiring any venue.

Workflow:
    # Log a forecast on a real upcoming market (your probability + the market's):
    python3 forecast.py add "Will Film X open #1 at the box office?" 0.70 0.55 --category box-office
    python3 forecast.py add "Will Song Y hit the Top 10?" 35% 50% --category charts --notes "TikTok velocity stalling"

    python3 forecast.py list                 # see open + resolved
    python3 forecast.py resolve F001 yes     # when the market settles
    python3 forecast.py score                # YOUR Brier vs the MARKET's — the verdict

Probabilities accept 0.70, 70, or 70%. Outcomes accept yes/no (or 1/0).
The journal is a plain JSON file (forecasts.json) — back it up, inspect it, edit it.
"""

from __future__ import annotations

import argparse
import os

from quantloop.journal import Journal

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(HERE, "forecasts.json")


def _print_entry(e: dict) -> None:
    mark = {"open": "·", "resolved": "✓"}.get(e["status"], "?")
    out = "" if e["outcome"] is None else (" → YES" if e["outcome"] == 1 else " → NO")
    cat = f" [{e['category']}]" if e["category"] else ""
    print(f" {mark} {e['id']}  you {e['your_prob']:.0%} | mkt {e['market_price']:.0%}{out}{cat}  "
          f"{e['question']}")
    if e.get("notes"):
        print(f"      note: {e['notes']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Forecasting journal — prove an edge before betting")
    ap.add_argument("--file", default=DEFAULT_PATH, help="journal JSON path")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="log a new forecast")
    a.add_argument("question")
    a.add_argument("your_prob", help="your probability (0.70 / 70 / 70%%)")
    a.add_argument("market_price", help="the market's price (0.55 / 55 / 55%%), or decimal odds with --odds")
    a.add_argument("--odds", action="store_true",
                   help="read market_price as decimal odds (2.50 -> 40%%) — for football/Betfair")
    a.add_argument("--category", default="")
    a.add_argument("--notes", default="")

    li = sub.add_parser("list", help="list forecasts")
    li.add_argument("--status", choices=["open", "resolved"])

    r = sub.add_parser("resolve", help="mark a forecast's outcome")
    r.add_argument("id")
    r.add_argument("outcome", help="yes/no")

    rm = sub.add_parser("remove", help="delete a forecast")
    rm.add_argument("id")

    sub.add_parser("score", help="score your Brier vs the market's")

    args = ap.parse_args()
    j = Journal(args.file)

    if args.cmd == "add":
        market = args.market_price
        if args.odds:
            from quantloop.mathx import odds_to_prob
            market = odds_to_prob(float(args.market_price))
        e = j.add(args.question, args.your_prob, market, args.category, args.notes)
        extra = f" (from odds {args.market_price})" if args.odds else ""
        print(f"logged {e['id']}: you {e['your_prob']:.0%} vs market {e['market_price']:.0%}{extra}")
    elif args.cmd == "list":
        entries = j.list(args.status)
        if not entries:
            print("no forecasts yet — add one with `forecast.py add`")
        for e in entries:
            _print_entry(e)
    elif args.cmd == "resolve":
        e = j.resolve(args.id, args.outcome)
        print(f"resolved {e['id']} → {'YES' if e['outcome'] == 1 else 'NO'}")
    elif args.cmd == "remove":
        j.remove(args.id)
        print(f"removed {args.id}")
    elif args.cmd == "score":
        s = j.score()
        print("=" * 64)
        print(" Forecasting journal — edge check")
        print("=" * 64)
        if s["resolved"] == 0:
            print(" " + s["verdict"])
            return
        print(f" resolved markets : {s['resolved']}")
        print(f" your Brier       : {s['your_brier']}   (lower is better)")
        print(f" market Brier     : {s['market_brier']}")
        print(f" baseline (50/50) : {s['baseline_brier']}")
        print(f" edge vs market   : {s['edge_vs_market']:+}   (positive = you beat the crowd)")
        if s["calibration"]:
            print(" calibration (did your probabilities match reality?):")
            for c in s["calibration"]:
                print(f"   {c['bucket']:>8}: n={c['n']:<3} you≈{c['you_said']:.0%} "
                      f"actual={c['actually_happened']:.0%}")
        if len(s["by_category"]) > 1:
            print(" by category:")
            for cat, m in s["by_category"].items():
                print(f"   {cat:<18} n={m['n']:<3} you {m['your_brier']} vs mkt {m['market_brier']}")
        print("-" * 64)
        print(" " + s["verdict"])
        print("=" * 64)


if __name__ == "__main__":
    main()
