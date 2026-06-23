#!/usr/bin/env python3
"""Run the autonomous quant trading loop.

Examples
--------
    python3 run.py                 # 6 full cycles, synchronous (the simple demo)
    python3 run.py --engine        # the event-driven automation flavour
    python3 run.py --goal 1.5      # /goal: iterate until verified Sharpe >= 1.5
    python3 run.py --cycles 20      # more cycles

After any run, read state/STATE.md to see the loop's durable memory, and
skills/alpha_research.md to see any lessons the risk monitor wrote back.
"""

from __future__ import annotations

import argparse
import os
import shutil

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


def main() -> None:
    ap = argparse.ArgumentParser(description="Autonomous quant trading loop")
    ap.add_argument("--cycles", type=int, default=6, help="number of trading cycles")
    ap.add_argument("--engine", action="store_true", help="run the event-driven LoopEngine")
    ap.add_argument("--goal", type=float, metavar="SHARPE",
                    help="run a /goal loop until verified Sharpe reaches SHARPE")
    ap.add_argument("--stress", action="store_true",
                    help="force a drawdown breach to show the kill switch + lesson write-back")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    pipe = Pipeline(state_dir=_fresh_state_dir(), seed=args.seed)

    print("=" * 70)
    print(" Autonomous quant trading loop — six pieces, five stages")
    print("=" * 70)
    print(f" universe : {', '.join(pipe.universe)}")
    print(f" skills   : alpha_research (maker), backtest_verification (checker)")
    print(f" limits   : position {pipe.max_position:.0%}, drawdown kill {pipe.max_drawdown:.0%}")
    print("-" * 70)

    if args.stress:
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
