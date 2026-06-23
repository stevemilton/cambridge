"""quantloop — a reference implementation of loop engineering for quant trading.

This package turns the six universal pieces of a working agentic loop into runnable
code, then wires them around the five-stage quant trading cycle:

    The six pieces                       The five stages
    --------------                       ---------------
    1. Automation   -> loop.py           1. Ingest   -> stages/ingest.py
    2. Skill        -> skills.py         2. Signal   -> stages/signal.py
    3. State file   -> state.py          3. Verify   -> stages/verify.py
    4. Verifier     -> verifier (verify) 4. Execute  -> stages/execute.py
    5. Worktrees    -> worktrees.py      5. Risk     -> stages/risk.py
    6. Connectors   -> connectors/

The whole system is deterministic and runs with zero external dependencies so the
loop can be demonstrated end to end. Real LLMs, brokers, and data feeds plug in
behind the same interfaces (see quantloop.agent and quantloop.connectors).
"""

from .loop import LoopEngine, parse_interval
from .state import State
from .skills import Skill, load_skill
from .agent import Agent, LocalAgent, ClaudeAgent

__all__ = [
    "LoopEngine",
    "parse_interval",
    "State",
    "Skill",
    "load_skill",
    "Agent",
    "LocalAgent",
    "ClaudeAgent",
]

__version__ = "0.1.0"
