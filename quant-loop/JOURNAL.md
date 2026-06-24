# The forecasting journal — prove your edge for £0

Before any venue, any money, or any automation, answer one question: **can you
actually forecast a niche better than the market?** This tool measures it. Same
Brier gate the loop's verifier uses, run by hand on real markets.

## The loop

1. **Pick a niche you might have an edge in** (you chose marketing / virality —
   start with *high-cadence* markets so evidence builds in weeks, not years:
   box-office openings, music/streaming chart positions, "will X hit Y views").
2. **Log a forecast** on a real upcoming market — *your* probability and *the
   market's* current price:
   ```bash
   python3 forecast.py add "Will Film X open #1 this weekend?" 70% 55% --category box-office
   python3 forecast.py add "Will Song Y reach the Top 10?" 35% 50% --category charts --notes "TikTok velocity stalling"
   ```
   Football/Betfair markets are quoted in **decimal odds**, not probabilities —
   add `--odds` and paste them straight in (2.50 → 40%):
   ```bash
   python3 forecast.py add "Will Brazil beat Croatia?" 60% 2.10 --odds --category wc-match
   python3 forecast.py add "Will Mbappe be top scorer?" 22% 5.00 --odds --category wc-golden-boot
   ```

   > **Efficiency warning — pick your battles.** Big markets (World Cup match
   > results, the title race) are the sharpest on earth; you almost certainly
   > won't beat them, and a flat result there is the expected one. The edge — if
   > you have one — lives in the *soft* markets: novelty/"specials", player buzz,
   > longshots, and anything cultural rather than sporting. Tag them as separate
   > categories so `score` shows you where (if anywhere) you actually beat the market.
3. **Resolve it** when the market settles:
   ```bash
   python3 forecast.py resolve F001 yes
   ```
4. **Score yourself** any time:
   ```bash
   python3 forecast.py score
   ```

## Reading the score

- **your Brier vs market Brier** — lower is better. If yours is consistently
  below the market's, you're forecasting better than the crowd.
- **edge vs market** — positive means you're winning. This is the number.
- **calibration** — when you said "70%", did it happen ~70% of the time? Tells
  you *how* you're wrong (over- or under-confident), not just *that* you are.
- **by category** — maybe you have an edge in box-office but not charts. Lean
  into where the edge is real.
- **the verdict** — it won't flatter you. Under ~20 resolved markets it says
  "keep logging"; a tiny sample beating the market is luck, not edge.

## What "done" looks like

After ~20–30 resolved markets in a niche:
- **Beating the market + calibrated** → you have evidence of a real edge. *Now*
  it's worth wiring Betfair and letting the loop bet it (small).
- **Calibrated but not beating the market** → the crowd is as sharp as you here.
  No tradeable edge — try a different niche.
- **Not beating 50/50** → no edge in this set. Don't risk money on it.

This is the discipline the whole system rests on: **the loop only deserves your
capital once the journal says the edge is real.** Most niches won't pass — that's
the point. Finding the one that does is the work.

> The journal (`forecasts.json`) stays local and is git-ignored — it's your
> private track record.
