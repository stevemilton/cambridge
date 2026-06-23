"""Piece #3 — The state file.

A markdown/JSON file that survives between runs. The agent forgets; the file
does not. The worker reads it at the start of every run and writes back what
happened at the end. It sounds too dumb to matter. It is the spine of every
working loop.

This implementation keeps two things side by side in one directory:

  * STATE.md   — a human-readable, append-only journal (what happened, when)
  * <key>.json — structured blobs handed between stages (latest data, the
                 pending signal, active trades), so stage N+1 can read exactly
                 what stage N produced.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


class State:
    def __init__(self, directory: str, clock: "callable | None" = None):
        self.dir = directory
        os.makedirs(self.dir, exist_ok=True)
        self.journal = os.path.join(self.dir, "STATE.md")
        # Injectable clock so the journal is reproducible in tests/demos.
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
        if not os.path.exists(self.journal):
            self._write_journal("# STATE.md\n\nAutonomous quant loop — run journal.\n")

    # ---- structured blobs (stage handoffs) --------------------------------

    def write(self, key: str, value: Any) -> None:
        """Persist a structured blob other stages can read by key."""
        path = os.path.join(self.dir, f"{key}.json")
        with open(path, "w") as fh:
            json.dump(value, fh, indent=2, default=str)

    def read(self, key: str, default: Any = None) -> Any:
        """Read a structured blob written by an earlier stage."""
        path = os.path.join(self.dir, f"{key}.json")
        if not os.path.exists(path):
            return default
        with open(path) as fh:
            return json.load(fh)

    def has(self, key: str) -> bool:
        return os.path.exists(os.path.join(self.dir, f"{key}.json"))

    # ---- the journal (memory across runs) ---------------------------------

    def append(self, message: str) -> None:
        """Append a timestamped line to STATE.md — the loop's durable memory."""
        with open(self.journal, "a") as fh:
            fh.write(f"- `{self._clock()}` {message}\n")

    def journal_text(self) -> str:
        with open(self.journal) as fh:
            return fh.read()

    def _write_journal(self, text: str) -> None:
        with open(self.journal, "w") as fh:
            fh.write(text)
