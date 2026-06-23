"""The five stages of the quant trading cycle.

Each stage is its own sub-loop with its own skill, state, and (where it matters)
its own verifier. They communicate only through the State file — stage N writes
a blob, stage N+1 reads it — so any stage can be run, tested, or replaced in
isolation.

    1. ingest   — pull market data on a cadence            (stages/ingest.py)
    2. signal   — generate alpha from the data             (stages/signal.py)
    3. verify   — independently grade the signal           (stages/verify.py)
    4. execute  — place only what passed verification       (stages/execute.py)
    5. risk     — monitor drawdown, flatten on breach       (stages/risk.py)
"""

from .ingest import ingest
from .signal import generate_signal
from .verify import verify_signal
from .execute import execute
from .risk import monitor_risk

__all__ = ["ingest", "generate_signal", "verify_signal", "execute", "monitor_risk"]
