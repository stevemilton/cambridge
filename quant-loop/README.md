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
python3 tests/test_loop.py && python3 tests/test_pipeline.py   # the tests
```

By default everything runs on `LocalAgent` (offline, deterministic). Add
`--claude` to run the maker on **Claude Sonnet** and the checker on **Claude
Opus** — `pip install anthropic` and set `ANTHROPIC_API_KEY` first. The model
makes the *decision* (direction, trend-vs-revert, lookback; pass/fail verdict);
the deterministic backtest in `quantloop/mathx.py` computes the numbers — an LLM
shouldn't do arithmetic on a price series. See `quantloop/agent.py::ClaudeAgent`.

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
