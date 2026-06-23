"""Forecasting journal — prove (or kill) an edge before risking a penny.

The cheapest possible edge test: log your probability for real upcoming markets
alongside the current market price, and when they resolve, score *your* Brier
against the *market's*. Beat the crowd over enough markets and you have evidence
of an edge — the same gate the loop's verifier enforces, run by hand on real
markets first. No Betfair, no API, no money.

Storage is a plain JSON file so it's portable and inspectable.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from . import mathx

MIN_SAMPLES = 20  # below this, a Brier comparison is noise, not evidence


def parse_prob(s: Any) -> float:
    """Accept '0.7', '70', or '70%' -> 0.7. Percent sign forces /100."""
    text = str(s).strip()
    pct = text.endswith("%")
    v = float(text.rstrip("%").strip())
    if pct or v > 1:
        v /= 100.0
    return mathx.clamp01(v)


def parse_outcome(s: Any) -> int:
    text = str(s).strip().lower()
    if text in ("yes", "y", "1", "true", "t"):
        return 1
    if text in ("no", "n", "0", "false", "f"):
        return 0
    raise ValueError(f"outcome must be yes/no (got {s!r})")


class Journal:
    def __init__(self, path: str, today: "callable | None" = None):
        self.path = path
        self._today = today or (lambda: date.today().isoformat())
        self.data = {"forecasts": [], "counter": 0}
        if os.path.exists(self.path):
            with open(self.path) as fh:
                self.data = json.load(fh)

    # ---- mutations --------------------------------------------------------

    def add(self, question: str, your_prob: Any, market_price: Any,
            category: str = "", notes: str = "") -> dict:
        self.data["counter"] += 1
        entry = {
            "id": f"F{self.data['counter']:03d}",
            "question": question,
            "your_prob": round(parse_prob(your_prob), 4),
            "market_price": round(parse_prob(market_price), 4),
            "category": category,
            "notes": notes,
            "created": self._today(),
            "status": "open",
            "outcome": None,
        }
        self.data["forecasts"].append(entry)
        self._save()
        return entry

    def resolve(self, fid: str, outcome: Any) -> dict:
        entry = self._get(fid)
        entry["outcome"] = parse_outcome(outcome)
        entry["status"] = "resolved"
        entry["resolved_on"] = self._today()
        self._save()
        return entry

    def remove(self, fid: str) -> None:
        self.data["forecasts"] = [f for f in self.data["forecasts"] if f["id"] != fid]
        self._save()

    def list(self, status: str | None = None) -> list[dict]:
        return [f for f in self.data["forecasts"] if status is None or f["status"] == status]

    # ---- the point: score your edge --------------------------------------

    def score(self) -> dict:
        resolved = self.list("resolved")
        n = len(resolved)
        if n == 0:
            return {"resolved": 0, "verdict": "No resolved forecasts yet — log some and resolve them."}

        you = [f["your_prob"] for f in resolved]
        mkt = [f["market_price"] for f in resolved]
        out = [f["outcome"] for f in resolved]
        your_brier = mathx.brier_score(you, out)
        market_brier = mathx.brier_score(mkt, out)

        beats_market = your_brier < market_brier
        beats_baseline = your_brier < 0.25
        enough = n >= MIN_SAMPLES

        return {
            "resolved": n,
            "your_brier": round(your_brier, 4),
            "market_brier": round(market_brier, 4),
            "edge_vs_market": round(market_brier - your_brier, 4),  # positive = you win
            "baseline_brier": 0.25,
            "beats_market": beats_market,
            "beats_baseline": beats_baseline,
            "enough_samples": enough,
            "calibration": self._calibration(resolved),
            "by_category": self._by_category(resolved),
            "verdict": self._verdict(n, enough, beats_market, beats_baseline,
                                     your_brier, market_brier),
        }

    def _verdict(self, n, enough, beats_market, beats_baseline, yb, mb) -> str:
        if not enough:
            return (f"Keep logging — need ~{MIN_SAMPLES} resolved markets before the "
                    f"result means anything (have {n}).")
        if beats_market and beats_baseline:
            return (f"You're beating the market over {n} markets (you {yb} vs market {mb}). "
                    f"That's real evidence of an edge — worth automating.")
        if beats_baseline:
            return (f"Calibrated but NOT beating the market price ({yb} vs {mb}). The crowd is "
                    f"as good or better here — no tradeable edge yet.")
        return (f"Not beating the 0.25 baseline ({yb}) — no edge in this set. Try a different "
                f"niche or sharpen the signal.")

    def _calibration(self, resolved: list[dict]) -> list[dict]:
        bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
        out = []
        for lo, hi in bins:
            grp = [f for f in resolved if lo <= f["your_prob"] < hi]
            if grp:
                out.append({
                    "bucket": f"{int(lo*100)}-{int(min(hi,1)*100)}%",
                    "n": len(grp),
                    "you_said": round(mathx.mean([f["your_prob"] for f in grp]), 3),
                    "actually_happened": round(mathx.mean([f["outcome"] for f in grp]), 3),
                })
        return out

    def _by_category(self, resolved: list[dict]) -> dict:
        cats: dict[str, list[dict]] = {}
        for f in resolved:
            cats.setdefault(f["category"] or "(uncategorised)", []).append(f)
        return {
            c: {"n": len(g),
                "your_brier": round(mathx.brier_score([f["your_prob"] for f in g],
                                                      [f["outcome"] for f in g]), 4),
                "market_brier": round(mathx.brier_score([f["market_price"] for f in g],
                                                        [f["outcome"] for f in g]), 4)}
            for c, g in cats.items()
        }

    # ---- helpers ----------------------------------------------------------

    def _get(self, fid: str) -> dict:
        for f in self.data["forecasts"]:
            if f["id"] == fid:
                return f
        raise KeyError(f"no forecast {fid!r}")

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as fh:
            json.dump(self.data, fh, indent=2)
