# quant-loop — a reference autonomous quant trading loop

> *"I don't prompt Claude anymore. I have loops running that prompt Claude and
> figuring out what to do. My job is to write loops."*

A small, runnable reference implementation of **loop engineering** applied to a
quant trading system. It turns the *six universal pieces* of a working agentic
loop into real code, then wires them around the *five-stage* trading cycle —
data in, signals out, verified, executed, risk-monitored, lessons written back,
then around again.

The whole thing is **deterministic and dependency-free** (Python standard library
only), so you can watch the loop run end to end without an API key, a broker, or
a data feed. Real models, brokers, and feeds plug in behind the same interfaces.

```bash
python3 run.py             # 6 full cycles, synchronous (the simplest view)
python3 run.py --engine    # the event-driven automation flavour
python3 run.py --goal 1.5  # /goal: iterate until verified Sharpe >= 1.5
python3 run.py --stress    # force a drawdown breach: kill switch + lesson write-back
python3 run.py --claude    # run the maker/checker on real Claude models (see below)
python3 run.py --pm --cycles 12   # the prediction-market loop (estimate P(YES), Brier-verified)
python3 tests/test_loop.py && python3 tests/test_pipeline.py && python3 tests/test_prediction.py
```

By default everything runs on `LocalAgent` (offline, deterministic). Add
`--claude` to run the maker on **Claude Sonnet** and the checker on **Claude
Opus** — `pip install anthropic` and set `ANTHROPIC_API_KEY` first. The model
makes the *decision* (direction, trend-vs-revert, lookback; pass/fail verdict);
the deterministic backtest in `quantloop/mathx.py` computes the numbers — an LLM
shouldn't do arithmetic on a price series. See `quantloop/agent.py::ClaudeAgent`.

## Demo vs daemon

The commands above are **bounded** — they run a handful of cycles on a simulated
clock and exit. To run **continuously** (the "keeps running after the laptop is
closed" part of the article), use `--serve`:

```bash
python3 run.py --serve                                    # fast clock — local smoke test
python3 run.py --serve --tick 1m --ingest-every 1h --risk-every 1m   # production cadence
```

`--serve` loops forever against the wall clock, persists its state across
restarts, and shuts down cleanly on Ctrl-C / SIGTERM (it finishes the current
cycle first). To run it on a server (Hetzner or any Linux box) under systemd or
Docker, see [`deploy/`](deploy/README.md).

> **It is still a demo until you wire real connectors.** `--serve` runs against a
> *simulated* market and a *mock* broker — safe to leave on, but not trading
> anything real. [`CONNECTORS.md`](CONNECTORS.md) is the exact guide to swapping
> in a real data feed and broker (with provider options), in safe stages.

## Prediction markets (`--pm`)

There's a second loop better suited to an LLM maker: **prediction markets**,
where each market is a natural-language question priced as a probability that
resolves to a known YES/NO. `python3 run.py --pm` runs it. What changes:

- **maker** estimates P(YES) and trades only the *gap* to the market price —
  reading the question is the edge, which is exactly what `ClaudeAgent` is for
  (a price-momentum model has nothing to offer here).
- **verifier** grades the maker on *resolved* markets with a **Brier score** —
  real ground truth, not a noisy price Sharpe — and only passes if the maker is
  calibrated *and* beats the market's own forecast.
- **resolution = labelled feedback**, so the lessons file learns from
  unambiguous outcomes.

It runs offline on the simulated `SimPredictionMarketConnector` (markets that
carry a question, a drifting price, and a resolution). To go live on a UK-legal
venue, [`BETFAIR.md`](BETFAIR.md) maps the loop onto Betfair Exchange (back/lay
odds ↔ probability) with a connector skeleton in
`quantloop/connectors/betfair.py`.

### Step 0: prove the edge first (`forecast.py`)

A loop only deserves capital once you've shown you can forecast a niche better
than the market. The **forecasting journal** measures that for £0 — no venue, no
money:

```bash
python3 forecast.py add "Will Film X open #1?" 70% 55% --category box-office
python3 forecast.py resolve F001 yes
python3 forecast.py score      # YOUR Brier vs the MARKET's — the honest verdict
```

It scores your probability forecasts against the market's over real, resolved
markets — the same Brier gate the loop's verifier enforces, run by hand first.
See [`JOURNAL.md`](JOURNAL.md). Most niches won't pass; finding the one that does
is the actual work.

## The six pieces

| # | Piece | Where it lives | What it does |
|---|-------|----------------|--------------|
| 1 | **Automation** | `quantloop/loop.py` | The heartbeat. `@loop(interval=…)` reruns on a cadence; `@loop(trigger=…)` reruns on an event; `@goal(check=…)` reruns until an *externally checkable* condition is true. |
| 2 | **Skill** | `quantloop/skills.py`, `skills/*.md` | A `SKILL.md` procedure manual the worker reads each run — rules + a "lessons learned" log it can append to, so intent compounds. |
| 3 | **State file** | `quantloop/state.py`, `state/STATE.md` | Markdown journal + JSON blobs that survive between runs. The worker forgets; the file does not. |
| 4 | **Verifier** | `quantloop/verifier.py` | The maker/checker split. A *separate* agent grades each signal on out-of-sample data against thresholds it cannot argue with. |
| 5 | **Worktrees** | `quantloop/worktrees.py` | Real `git worktree` isolation so parallel agents don't collide (falls back to plain dirs off-repo). |
| 6 | **Connectors** | `quantloop/connectors/` | Hands in the real world: a market-data feed in, a broker out. Simulated here; MCP in production. |

## The five stages

Each stage is its own sub-loop, communicating only through the state file
(stage N writes a blob, stage N+1 reads it):

```
ingest  ──>  signal  ──>  verify  ──>  execute  ──>  risk  ──┐
  ▲          (maker)      (checker)   (auto)      (kill switch)│
  └──────────────────────  lessons written back  ─────────────┘
```

1. **`stages/ingest.py`** — pull market data on a cadence, write `latest_data`.
2. **`stages/signal.py`** — the *maker*: fit on a training window, propose a
   signal, hand the held-out track record forward. It never judges itself.
3. **`stages/verify.py`** — the *checker*: a different agent recomputes Sharpe,
   max-drawdown, and a Newey-West t-stat on the out-of-sample window and applies
   fixed thresholds. Fail → the signal is killed here.
4. **`stages/execute.py`** — only verified signals reach the broker; the position
   cap is enforced at the connector, not just the agent.
5. **`stages/risk.py`** — a parallel monitor; on a drawdown breach it flattens
   the book **and writes the incident back into `alpha_research.md`** as a new
   rule. That write-back is what makes the system self-improving.

## Why the maker and the checker are different agents

The worker that wrote the signal is the worst judge of whether it is real alpha
or noise. So `Pipeline` constructs two agents and a `Verifier` that only ever
sees the out-of-sample returns — never the maker's reasoning. The `claude`
backend points the checker at a *stronger* model than the maker (Opus checks,
Sonnet makes); different architectures catch different errors, the same logic
ensemble methods use. See `quantloop/agent.py::ClaudeAgent`.

## Stop conditions you can trust

A loop without a real stopping condition fails quietly — the worker claims it is
"done", the loop exits, and a bad trade sits open. Every stop condition here is a
*measured number*, never the worker's own claim:

- `--goal 1.5` exits only when the **verifier-measured** Sharpe clears 1.5.
- the risk monitor flattens only when **measured drawdown** exceeds the limit.
- `@goal` is bounded by `max_iterations` so it can never spin forever.

## Plugging in the real world

| Replace | With | How |
|---------|------|-----|
| `LocalAgent` | `ClaudeAgent` | Already implemented — run `Pipeline(backend="claude")` or `python3 run.py --claude` (Sonnet maker, Opus checker). |
| `MarketDataConnector` | your data vendor | Keep the `fetch()` return shape; back it with an MCP connector. |
| `BrokerConnector` | your broker/exchange | Keep `send_orders` / `get_positions` / `close_all`; back it with an MCP connector. |
| virtual clock | cron / webhook | Run `engine.run(real_time=True)`, or trigger one `pipeline.run_once()` per fire. |

## Layout

```
quant-loop/
├── run.py                     # entrypoint (synchronous / --engine / --goal / --stress)
├── quantloop/
│   ├── loop.py                # 1. automation (the loop engine + decorators)
│   ├── skills.py              # 2. skill loader + lesson write-back
│   ├── state.py               # 3. state file (journal + JSON handoffs)
│   ├── verifier.py            # 4. maker/checker verifier
│   ├── worktrees.py           # 5. git-worktree isolation
│   ├── connectors/            # 6. market data + broker
│   ├── agent.py               # maker/checker workers (LocalAgent, ClaudeAgent)
│   ├── mathx.py               # pure-Python returns/Sharpe/drawdown/Newey-West
│   ├── stages/                # the five trading stages
│   └── pipeline.py            # wires all six pieces around the five stages
├── skills/                    # SKILL.md templates (the loop works on a copy)
└── tests/                     # loop-engine and pipeline tests
```

> This is a teaching reference for the loop architecture, not a trading system.
> The simulated market and risk model are intentionally simple. Do not point it
> at real capital.
