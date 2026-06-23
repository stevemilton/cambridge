"""Pure-Python quant math so the reference runs with zero dependencies.

Nothing here is novel; it is the minimum needed for an honest backtest:
returns, an OLS slope, Sharpe, max drawdown, and a Newey-West t-stat. Swap in
numpy/pandas/statsmodels in production — the interfaces are intentionally plain.
"""

from __future__ import annotations

import math
from typing import Sequence


def returns(prices: Sequence[float]) -> list[float]:
    """Simple period-over-period returns."""
    return [(prices[i] / prices[i - 1]) - 1.0 for i in range(1, len(prices))]


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def stdev(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def ols_slope(x: Sequence[float], y: Sequence[float]) -> float:
    """Slope of the least-squares line y = a + b·x. Used as the signal's beta."""
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    x, y = x[:n], y[:n]
    mx, my = mean(x), mean(y)
    denom = sum((xi - mx) ** 2 for xi in x)
    if denom == 0:
        return 0.0
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / denom


def sharpe(rets: Sequence[float], periods_per_year: int = 252) -> float:
    """Annualised Sharpe ratio of a return stream (risk-free assumed 0)."""
    sd = stdev(rets)
    if sd == 0:
        return 0.0
    return (mean(rets) / sd) * math.sqrt(periods_per_year)


def max_drawdown(rets: Sequence[float]) -> float:
    """Largest peak-to-trough decline of the cumulative equity curve (>= 0)."""
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for r in rets:
        equity *= (1.0 + r)
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak)
    return worst


def newey_west_tstat(rets: Sequence[float], lags: int = 4) -> float:
    """Heteroskedasticity/autocorrelation-robust t-stat of the mean return.

    A plain t-stat overstates significance when returns are autocorrelated; the
    Newey-West correction is the standard guard a serious verifier applies.
    """
    n = len(rets)
    if n < 3:
        return 0.0
    m = mean(rets)
    e = [r - m for r in rets]
    gamma0 = sum(ei * ei for ei in e) / n
    var = gamma0
    for L in range(1, min(lags, n - 1) + 1):
        w = 1.0 - L / (lags + 1)
        cov = sum(e[t] * e[t - L] for t in range(L, n)) / n
        var += 2.0 * w * cov
    se = math.sqrt(var / n) if var > 0 else 0.0
    return m / se if se > 0 else 0.0
