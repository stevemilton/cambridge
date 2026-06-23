#!/usr/bin/env python3
"""Run the autonomous quant trading loop.

Examples
--------
    python3 run.py                 # 6 full cycles, synchronous (the simple demo)
    python3 run.py --engine        # the event-driven automation flavour
    python3 run.py --goal 1.5      # /goal: iterate until verified Sharpe >= 1.5
    python3 run.py --cycles 20      # more cycles
    python3 run.py --serve         # run forever (fast clock, for a local smoke test)
    python3 run.py --serve --tick 1m --ingest-every 1h --risk-every 1m   # production cadence

After any run, read state/STATE.md to see the loop's durable memory, and
state/skills/alpha_research.md to see any lessons the risk monitor wrote back.
`--serve` persists that state across restarts; the other modes start fresh.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal

from quantloop.pipeline import Pipeline
from quantloop.stages.risk import monitor_risk

HERE = os.path.dirname(os.path.abspath(__file__))


def stress_demo(pipe: Pipeline) -> None:
    """Force a drawdown breach to show the kill switch and the lesson write-back.

    A 2%-capped book can only lose its gross exposure, so a realistic 5% trigger
    needs the leverage real funds run. Here we simply shock an open book hard to
    exercise the mechanism: flatten on breach, then write the incident back into
    alpha_research.md so the constraint binds the next run.
    """
    pipe.run_once()  # one normal cycle to get live data
    data = pipe.state.read("latest_data")
    for sym in pipe.universe:  # open a full long book directly
        px = data[sym]["prices"][-1]
        pipe.broker.send_orders({"symbol": sym, "side": "long", "size": 0.02}, price=px)
    print(f" opened {len(pipe.broker.get_positions())} positions; applying -95% shock...")
    for sym in data:  # crash the market
        data[sym]["prices"][-1] *= 0.05
    pipe.state.write("latest_data", data)

    before = len(pipe.alpha_skill.lessons)
    killed = monitor_risk(pipe.state, pipe.broker, pipe.max_drawdown,
                          alpha_skill=pipe.alpha_skill, on=pipe._stamp_date())
    print(f" kill switch fired: {killed}; open positions now: {len(pipe.broker.get_positions())}")
    print(f" lessons in alpha_research skill: {before} -> {len(pipe.alpha_skill.lessons)}")


def _fresh_state_dir() -> str:
    """Start each demo from a clean slate: empty journal and a fresh skill copy."""
    d = os.path.join(HERE, "state")
    if os.path.isdir(d):
        shutil.rmtree(d)
    return d


def serve_forever(pipe: Pipeline, tick: str, ingest_interval: str, risk_interval: str) -> None:
    """Run the loop continuously against the wall clock until SIGINT/SIGTERM.

    This is the daemon: it never exits on its own. Point a process manager
    (systemd, Docker `restart: always`) at `python3 run.py --serve` and it keeps
    running — and keeps its memory — across restarts, because the state dir is
    persisted (not wiped). Stop with Ctrl-C locally or `systemctl stop` on a box.
    """
    pipe.log = lambda msg: print(msg, flush=True)  # flush so journalctl shows logs live
    engine = pipe.serve(tick=tick, ingest_interval=ingest_interval, risk_interval=risk_interval)

    def _shutdown(signum, _frame):
        print(f"\n[run] received signal {signum}; finishing current cycle then exiting")
        engine.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f" mode     : SERVE (continuous) — tick={tick}, ingest every {ingest_interval}, "
          f"risk every {risk_interval}")
    print(f" stop with: Ctrl-C  (or `systemctl stop quant-loop` on a server)")
    print("-" * 70)
    engine.run(max_cycles=None, real_time=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Autonomous quant trading loop")
    ap.add_argument("--cycles", type=int, default=6, help="number of trading cycles")
    ap.add_argument("--engine", action="store_true", help="run the event-driven LoopEngine")
    ap.add_argument("--goal", type=float, metavar="SHARPE",
                    help="run a /goal loop until verified Sharpe reaches SHARPE")
    ap.add_argument("--stress", action="store_true",
                    help="force a drawdown breach to show the kill switch + lesson write-back")
    ap.add_argument("--claude", action="store_true",
                    help="use real Claude models (Sonnet maker, Opus checker); needs anthropic + API key")
    ap.add_argument("--serve", action="store_true",
                    help="run continuously against the wall clock (the daemon); persists state")
    ap.add_argument("--tick", default="2s", help="serve: engine heartbeat granularity (e.g. 1m)")
    ap.add_argument("--ingest-every", default="6s", help="serve: data-pull cadence (e.g. 1h)")
    ap.add_argument("--risk-every", default="2s", help="serve: risk-check cadence (e.g. 1m)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    backend = "claude" if args.claude else "local"
    # The daemon persists state across restarts; demos start from a clean slate.
    state_dir = os.path.join(HERE, "state") if args.serve else _fresh_state_dir()
    pipe = Pipeline(state_dir=state_dir, seed=args.seed, backend=backend)

    print("=" * 70)
    print(" Autonomous quant trading loop — six pieces, five stages")
    print("=" * 70)
    print(f" universe : {', '.join(pipe.universe)}")
    print(f" backend  : {backend}" + (f" (maker={pipe.maker_model}, checker={pipe.checker_model})"
                                       if backend == "claude" else " (offline, deterministic)"))
    print(f" skills   : alpha_research (maker), backtest_verification (checker)")
    print(f" limits   : position {pipe.max_position:.0%}, drawdown kill {pipe.max_drawdown:.0%}")
    print("-" * 70)

    if args.serve:
        serve_forever(pipe, tick=args.tick, ingest_interval=args.ingest_every,
                      risk_interval=args.risk_every)
    elif args.stress:
        stress_demo(pipe)
    elif args.goal is not None:
        engine = pipe.research_goal_engine(target_sharpe=args.goal)
        engine.run(max_cycles=30)
        print("-" * 70)
        print(f" best verified Sharpe found: {engine._best['sharpe']:.3f} "
              f"(target {args.goal})")
    elif args.engine:
        engine = pipe.build_engine(tick="1m")
        engine.run(max_cycles=args.cycles)
    else:
        pipe.run(cycles=args.cycles)

    print("-" * 70)
    print(f" journal  : {os.path.relpath(pipe.state.journal, HERE)}")
    print(f" lessons  : {os.path.relpath(pipe.alpha_skill.path, HERE)} "
          f"(working copy; risk monitor writes lessons here)")
    print("=" * 70)


if __name__ == "__main__":
    main()
