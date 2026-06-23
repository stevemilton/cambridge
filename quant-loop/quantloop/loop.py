"""Piece #1 — The automation.

The heartbeat of every working loop. A loop is a recursive goal: you define a
purpose, the engine iterates against it, and it keeps running until a real,
*externally checkable* stopping condition is met. The agent forgets between
runs; the loop does not.

Two flavours, exactly as described in the article:

    @engine.loop(interval="1h")     # reruns on a cadence regardless of state
    @engine.loop(trigger="event")   # reruns whenever another task emits `event`
    @engine.goal(check=fn, ...)     # keeps going until `fn(...)` is verifiably True

`@goal` is the important one: its stop condition is graded by a separate function,
never by the task's own claim that it is "done". A loop without a real stopping
condition fails quietly — the worker emits a completion signal believing a
half-done job is finished, the loop exits, and the bad trade sits open.

To keep the reference demonstrable, the engine runs on a *virtual clock*: each
cycle advances time by `tick`. Set `real_time=True` to sleep against the wall
clock instead (what you would do in production behind cron / a webhook).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


_INTERVAL_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd])\s*$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_interval(spec: str | float | int) -> float:
    """Parse an interval like '30s', '5m', '1h', '1d' into seconds.

    A bare number is treated as seconds. Used so loop schedules read the way
    they do in the article (`interval="1h"`).
    """
    if isinstance(spec, (int, float)):
        return float(spec)
    m = _INTERVAL_RE.match(spec)
    if not m:
        raise ValueError(f"unrecognised interval: {spec!r} (use e.g. '30s', '5m', '1h', '1d')")
    value, unit = m.groups()
    return float(value) * _UNIT_SECONDS[unit]


@dataclass
class Task:
    name: str
    fn: Callable[[], object]
    kind: str  # "interval" | "trigger" | "goal"
    interval: Optional[float] = None      # seconds, for interval/goal tasks
    trigger: Optional[str] = None         # event name, for trigger tasks
    check: Optional[Callable[[], bool]] = None  # stop condition, for goal tasks
    max_iterations: Optional[int] = None  # safety bound for goal tasks
    next_run: float = 0.0
    runs: int = 0
    done: bool = False


class LoopEngine:
    """A tiny scheduler that fires tasks on a cadence, on events, or toward a goal.

    It is deliberately small: the value of loop engineering is not a clever
    scheduler, it is the *shape* — automations that fire without you typing,
    checked by conditions you can trust.
    """

    def __init__(self, tick: str | float = "1m", logger: Optional[Callable[[str], None]] = None):
        self.tick = parse_interval(tick)
        self.now = 0.0
        self.tasks: list[Task] = []
        self._pending_events: list[str] = []
        self._log = logger or (lambda msg: print(msg))

    # ---- registration (the decorators) -----------------------------------

    def loop(self, interval: str | float | None = None, trigger: str | None = None,
             name: str | None = None):
        """Register a task that reruns on a cadence (`interval`) or on an `event`."""
        if (interval is None) == (trigger is None):
            raise ValueError("loop() needs exactly one of `interval` or `trigger`")

        def decorator(fn):
            task = Task(
                name=name or fn.__name__,
                fn=fn,
                kind="interval" if interval is not None else "trigger",
                interval=parse_interval(interval) if interval is not None else None,
                trigger=trigger,
            )
            self.tasks.append(task)
            return fn

        return decorator

    def goal(self, check: Callable[[], bool], interval: str | float = "1m",
             max_iterations: int = 100, name: str | None = None):
        """Register a task that reruns until `check()` returns True.

        `check` is the verifier of the stopping condition. It must be answerable
        by something other than the worker's own claim — a measured Sharpe, a
        passing test suite, a drawdown threshold.
        """
        def decorator(fn):
            task = Task(
                name=name or fn.__name__,
                fn=fn,
                kind="goal",
                interval=parse_interval(interval),
                check=check,
                max_iterations=max_iterations,
            )
            self.tasks.append(task)
            return fn

        return decorator

    # ---- events ------------------------------------------------------------

    def emit(self, event: str) -> None:
        """Fire an event; trigger-tasks listening for it run on the next cycle."""
        self._pending_events.append(event)

    # ---- the run loop ------------------------------------------------------

    def run(self, max_cycles: int = 50, real_time: bool = False) -> None:
        """Advance the loop. Stops when all goals are met or `max_cycles` is hit."""
        for cycle in range(1, max_cycles + 1):
            events, self._pending_events = self._pending_events, []
            self._step(cycle, events)

            if self._all_goals_done():
                self._log(f"[engine] all goals satisfied after {cycle} cycle(s); loop exits cleanly")
                return

            self.now += self.tick
            if real_time:
                time.sleep(self.tick)

        self._log(f"[engine] reached max_cycles={max_cycles}; stopping")

    def _step(self, cycle: int, events: list[str]) -> None:
        for task in self.tasks:
            if task.done:
                continue
            if task.kind == "interval" and self.now >= task.next_run:
                self._fire(task)
                task.next_run = self.now + (task.interval or 0)
            elif task.kind == "trigger" and task.trigger in events:
                self._fire(task)
            elif task.kind == "goal" and self.now >= task.next_run:
                self._run_goal(task)
                task.next_run = self.now + (task.interval or 0)

    def _fire(self, task: Task) -> None:
        task.runs += 1
        task.fn()

    def _run_goal(self, task: Task) -> None:
        # Check the condition *before* working: an already-satisfied goal never runs.
        if task.check and task.check():
            task.done = True
            self._log(f"[goal:{task.name}] stop condition already met; nothing to do")
            return
        self._fire(task)
        if task.check and task.check():
            task.done = True
            self._log(f"[goal:{task.name}] stop condition verified after {task.runs} iteration(s)")
        elif task.max_iterations and task.runs >= task.max_iterations:
            task.done = True
            self._log(f"[goal:{task.name}] hit max_iterations={task.max_iterations} without success")

    def _all_goals_done(self) -> bool:
        goals = [t for t in self.tasks if t.kind == "goal"]
        return bool(goals) and all(t.done for t in goals)
