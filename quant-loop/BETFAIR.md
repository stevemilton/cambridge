# Going live on Betfair Exchange (UK)

Betfair is the UK-legal home of "prediction markets": back/lay odds *are*
implied probabilities, every market settles to a known result, and there's a
mature API. The venue-agnostic prediction loop is already built and tested
(`--pm`); going live means filling in one connector + one broker.

> ⚠️ Real money and UK gambling-regulated. Run with **tiny stakes** first, and
> only after you've watched the loop run on the simulator. There is no paper
> environment — your edge has to be real, and on liquid markets it usually isn't.

## The one concept: odds ↔ probability

Betfair quotes **decimal odds**; the loop speaks **probability**. They're
reciprocals: `prob = 1 / odds` (back price 2.0 = 50%). `quantloop/connectors/
betfair.py` has `odds_to_prob()` / `prob_to_odds()` — the loop never sees odds.

## What to fill in

`quantloop/connectors/betfair.py` is a skeleton with the exact API calls marked
`TODO`. You implement four things:

| Loop surface | Betfair API call | Notes |
|---|---|---|
| `BetfairConnector.step()` — list open markets + prices | `listMarketCatalogue` → market ids/runners; `listMarketBook` → best back/lay | Convert the YES runner's back odds with `odds_to_prob()`. |
| `step()` — detect resolved markets | `listMarketBook` status `CLOSED` (or `listClearedOrders`) | Emit `{symbol, market_price, signal, outcome}`; persist the **entry-time** price/signal yourself — Betfair won't replay them, and the verifier grades the entry forecast (see below). |
| `BetfairBroker.place()` — bet | `placeOrders` (BACK/LAY, LIMIT) | `side="yes"` → back the YES runner; stake = `weight * capital`, price = `prob_to_odds(entry_price)`. |
| `BetfairBroker.settle()` — realise P&L | `listClearedOrders` | Use Betfair's reported profit/loss per cleared bet directly. |

## The `signal` — this is your actual edge

In the simulator, `signal` is a synthetic "research" estimate. Live, **`signal`
is whatever independent probability you can produce** for each event — a poll
aggregate, a model, a news read, or (with `--claude`) the LLM maker reading the
market question. The maker trades the gap between `signal`-informed estimate and
the market price; with no real `signal`, you have no edge and the verifier will
(correctly) keep you flat. Wiring a genuine signal source is the real work, not
the API plumbing.

## Entry-time grading (why the loop trades at all)

The verifier grades the maker on **resolved** markets using the price/signal
*at the time you'd have bet* — not the near-settled price just before
resolution. Liquid Betfair markets converge to the truth by settlement, so
grading on settlement prices would always say "the market beats you." Snapshot
each market's price + your signal when you first act on it, carry that snapshot
to settlement, and report it in the resolved record (the skeleton's `step()`
TODO notes this). This is exactly what `SimPredictionMarketConnector` does.

## Auth

1. Create a Betfair account; apply for an **Application Key** (developer portal).
2. Log in for a **session token**: interactive `POST identitysso.betfair.com/api/login`,
   or **cert login** (`identitysso-cert.betfair.com/api/certlogin`) for an
   unattended bot. Put both in env vars; the daemon's `.env` is the place.
3. Every betting call sends `X-Application: <app key>` and
   `X-Authentication: <session token>`. Session tokens expire — refresh them.

## Wiring it into the loop

```python
from quantloop.prediction import PredictionPipeline
from quantloop.connectors.betfair import BetfairConnector, BetfairBroker

pipe = PredictionPipeline(backend="claude")   # LLM maker reads the question
pipe.market = BetfairConnector(app_key=..., session_token=..., market_filter={...})
pipe.broker = BetfairBroker(app_key=..., session_token=..., capital=50, max_position=0.02)

engine = pipe.build_engine(tick="1m", interval="5m")   # poll every 5 min
engine.run(max_cycles=None, real_time=True)            # the daemon
```

Run it under systemd/Docker exactly as in `deploy/` — `python3 run.py --pm
--serve` once the connector is wired (point `--ingest-every` at your poll
cadence). Smarkets is the same pattern against their REST API if you prefer
lower commission.

> When you're ready to implement the TODOs for real, I can do it — but I'll
> verify each call against the live Betfair docs at that point rather than trust
> this skeleton's shapes, and you'll need to supply (or sandbox) credentials.
