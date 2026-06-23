"""Stage 3 — Verification (the checker).

    @checker
    def verify_signal(signal):
        result = claude.invoke(skill="backtest_verification_skill.md", signal=signal,
                               rules=["Sharpe > 1.5", "Max DD < 10%",
                                      "Newey-West t > 2.0", "OOS >= 2y"])
        return result.verdict

Each pending signal is graded by a separate agent against thresholds it cannot
argue with, using the out-of-sample track record the maker produced but never
judged. Pass -> the signal moves to execution. Fail -> it is killed here.
"""

from __future__ import annotations

from ..state import State
from ..verifier import Verifier


def verify_signal(state: State, verifier: Verifier) -> list[dict]:
    pending = state.read("pending_signals", default=[])
    verified: list[dict] = []
    for signal in pending:
        verdict = verifier.verify(signal, signal.get("oos_returns", []))
        if verdict:
            verified.append({**signal, "verification": verdict.detail})
            state.append(
                f"VERIFY: PASS {signal['symbol']} {signal['side']} "
                f"sharpe={verdict.metrics.get('sharpe')} "
                f"dd={verdict.metrics.get('max_drawdown')} "
                f"t={verdict.metrics.get('newey_west_t')}"
            )
        else:
            reason = verdict.detail.get("reason") or _failed_checks(verdict.checks)
            state.append(f"VERIFY: KILL {signal['symbol']} ({reason})")

    state.write("verified_signals", verified)
    return verified


def _failed_checks(checks: dict[str, bool]) -> str:
    failed = [name for name, ok in checks.items() if not ok]
    return "failed: " + ", ".join(failed) if failed else "rejected"
