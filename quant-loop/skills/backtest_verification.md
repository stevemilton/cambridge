# backtest_verification

## Goal
Independently grade a proposed signal on out-of-sample data the maker never saw.
Never trust the maker's own claim that a signal is real alpha. Compute every
metric from scratch and compare against fixed thresholds.

## Rules
- Sharpe ratio above 1.5
- Max drawdown below 10 percent
- Newey-West t-stat above 2.0
- Out of sample period at least 2 years (proxied here by the held-out window)

## Notes
- This skill is read by a *different* agent from the one that generated the
  signal — ideally a stronger model. The checker never sees the maker's reasoning.
- A failing signal is killed, not returned for "one more try" by the same maker.
