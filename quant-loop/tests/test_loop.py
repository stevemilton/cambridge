"""Tests for the loop engine — the automation piece."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantloop.loop import LoopEngine, parse_interval


def test_parse_interval():
    assert parse_interval("30s") == 30
    assert parse_interval("5m") == 300
    assert parse_interval("1h") == 3600
    assert parse_interval("2d") == 172800
    assert parse_interval(45) == 45.0


def test_interval_task_fires_on_cadence():
    engine = LoopEngine(tick="1m", logger=lambda _: None)
    hits = []

    @engine.loop(interval="3m")
    def beat():
        hits.append(engine.now)

    engine.run(max_cycles=9)
    # tick is 1m, interval 3m -> fires at now=0, 180, 360 (cycles 1, 4, 7)
    assert hits == [0, 180, 360], hits


def test_trigger_task_fires_on_event():
    engine = LoopEngine(tick="1m", logger=lambda _: None)
    fired = []

    @engine.loop(interval="1m")
    def producer():
        engine.emit("ping")

    @engine.loop(trigger="ping")
    def consumer():
        fired.append(engine.now)

    engine.run(max_cycles=4)
    # producer emits each cycle; consumer fires the *next* cycle.
    assert len(fired) >= 2


def test_goal_stops_when_condition_verified():
    engine = LoopEngine(tick="1m", logger=lambda _: None)
    progress = {"n": 0}

    def reached():
        return progress["n"] >= 3

    @engine.goal(check=reached, max_iterations=10)
    def work():
        progress["n"] += 1

    engine.run(max_cycles=20)
    assert progress["n"] == 3  # stops the moment the checked condition is met


def test_unbounded_run_honours_stop():
    # max_cycles=None runs forever; stop() must end it cleanly (the daemon path).
    engine = LoopEngine(tick="1s", logger=lambda _: None)
    hits = {"n": 0}

    @engine.loop(interval="1s")
    def beat():
        hits["n"] += 1
        if hits["n"] >= 5:
            engine.stop()

    engine.run(max_cycles=None, real_time=False)
    assert hits["n"] == 5


def test_goal_respects_max_iterations():
    engine = LoopEngine(tick="1m", logger=lambda _: None)
    runs = {"n": 0}

    @engine.goal(check=lambda: False, max_iterations=5)
    def never_done():
        runs["n"] += 1

    engine.run(max_cycles=50)
    assert runs["n"] == 5  # never exits on a false claim; bounded by max_iterations


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all loop tests passed")
