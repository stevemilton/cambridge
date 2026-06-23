"""Piece #5 — The worktrees.

The moment you run more than one agent against the same files, they collide.
Git worktrees give each agent its own isolated working directory pointed at its
own branch — so signal research, backtesting, and risk monitoring run in
parallel without stepping on each other.

This is a thin wrapper over `git worktree`. It is best-effort: if git is
unavailable or we are not inside a repo, it falls back to plain isolated
directories so the reference still runs. Real isolation in production comes from
the actual `git worktree add`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from contextlib import contextmanager


def _git(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def _in_repo(path: str) -> bool:
    if shutil.which("git") is None:
        return False
    return _git("rev-parse", "--is-inside-work-tree", cwd=path).returncode == 0


@contextmanager
def worktree(name: str, base_dir: str = ".", root: str | None = None):
    """Yield an isolated working directory for one parallel agent.

    Uses a real `git worktree` + branch when possible; otherwise a plain temp
    directory. Cleaned up on exit either way.
    """
    repo = os.path.abspath(root or base_dir)
    target = os.path.abspath(os.path.join(base_dir, ".worktrees", name))
    branch = f"loop/{name}"

    if _in_repo(repo):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        added = _git("worktree", "add", "-B", branch, target, "HEAD", cwd=repo)
        real = added.returncode == 0
        try:
            yield target
        finally:
            if real:
                _git("worktree", "remove", "--force", target, cwd=repo)
                _git("branch", "-D", branch, cwd=repo)
    else:
        os.makedirs(target, exist_ok=True)
        try:
            yield target
        finally:
            shutil.rmtree(target, ignore_errors=True)
